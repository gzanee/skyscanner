import datetime
import json
import logging
import sys
from flask import Flask, Response, jsonify, render_template, request
from skyscanner import SkyScanner
from skyscanner.errors import GenericError
from skyscanner.types import Airport, SpecialTypes


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

app = Flask(__name__)
logger = logging.getLogger(__name__)


def build_scanner() -> SkyScanner:
    return SkyScanner(locale="it-IT", currency="EUR", market="IT")


def parse_date(date_str: str) -> datetime.datetime:
    return datetime.datetime.strptime(date_str, "%d/%m/%Y")


def airport_from_code(scanner: SkyScanner, code: str) -> Airport:
    return scanner.get_airport_by_code(code)


def normalize_carrier_name(name: str) -> str:
    if not name:
        return "N/A"
    lower_name = name.strip().lower()
    if "easyjet" in lower_name:
        return "easyJet"
    return name.strip()


def normalize_selected_locations(items):
    normalized = []
    for item in items or []:
        if isinstance(item, str):
            normalized.append({"code": item, "entity_type": "", "title": ""})
            continue
        if isinstance(item, dict):
            code = item.get("code") or item.get("skyId")
            if not code:
                continue
            entity_type = item.get("entityType") or item.get("entity_type") or ""
            title = item.get("title") or item.get("label") or ""
            normalized.append(
                {"code": code, "entity_type": entity_type, "title": title}
            )
    return normalized


def dedupe_codes(items):
    seen = set()
    codes = []
    for item in items:
        code = item.get("code")
        if not code or code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def extract_country_places(hierarchy, country_code):
    matches = {}

    def walk(node, current_country=None):
        if isinstance(node, dict):
            place_type = (
                node.get("placeType")
                or node.get("place_type")
                or node.get("type")
                or ""
            )
            sky_code = node.get("skyCode") or node.get("skyId") or node.get("id")
            name = node.get("name") or node.get("title") or node.get("placeName")
            country_id = (
                node.get("countryId") or node.get("countryCode") or node.get("country")
            )

            if "COUNTRY" in place_type and sky_code == country_code:
                current_country = country_code

            normalized_type = None
            if "CITY" in place_type:
                normalized_type = "CITY"
            elif "AIRPORT" in place_type:
                normalized_type = "AIRPORT"

            if normalized_type and sky_code:
                if country_id == country_code or current_country == country_code:
                    matches[sky_code] = {
                        "skyCode": sky_code,
                        "name": name or sky_code,
                        "type": normalized_type,
                    }

            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value, current_country)
        elif isinstance(node, list):
            for item in node:
                walk(item, current_country)

    walk(hierarchy)
    return list(matches.values())


def get_country_places(scanner: SkyScanner, country_code: str, country_name: str):
    try:
        hierarchy = scanner.get_flight_geo_hierarchy()
        places = extract_country_places(hierarchy, country_code)
        if places:
            return places
    except GenericError:
        pass

    query = country_name or country_code
    results = scanner.search_airports(query)
    return [
        {
            "skyCode": airport.skyId,
            "name": airport.title,
            "type": airport.entity_type,
        }
        for airport in results
        if airport.entity_type in {"CITY", "AIRPORT"}
        and (
            not country_name
            or country_name.lower() in (airport.subtitle or "").lower()
        )
    ]


def process_flight_response(
    flight_response,
    origin: Airport,
    city,
    depart_date,
    max_price,
    min_hour,
    max_hour,
    min_arrival_hour,
    max_arrival_hour,
    direct_only,
    same_day,
    voli_trovati,
    voli_keys,
):
    logged_carrier_payload = False
    voli_visti = set()
    for bucket in flight_response.json.get("itineraries", {}).get("buckets", []):
        for item in bucket.get("items", []):
            if item["id"] in voli_visti:
                continue
            voli_visti.add(item["id"])

            price = item.get("price", {}).get("raw", 999999)
            if price > max_price:
                continue

            leg = item.get("legs", [{}])[0]
            dep_str = leg.get("departure", "")
            arr_str = leg.get("arrival", "")
            if not dep_str or not arr_str:
                continue

            dep = datetime.datetime.fromisoformat(dep_str)
            arr = datetime.datetime.fromisoformat(arr_str)

            # Check departure time is within the selected range
            dep_minutes = dep.hour * 60 + dep.minute
            min_dep_minutes = min_hour * 60
            max_dep_minutes = max_hour * 60
            if dep_minutes < min_dep_minutes or dep_minutes > max_dep_minutes:
                continue

            # Check arrival time is within the selected range
            arr_minutes = arr.hour * 60 + arr.minute
            min_arr_minutes = min_arrival_hour * 60
            max_arr_minutes = max_arrival_hour * 60
            if arr_minutes < min_arr_minutes or arr_minutes > max_arr_minutes:
                continue

            if same_day and arr.date() != dep.date():
                continue

            stops = leg.get("stopCount", 0)
            if direct_only and stops > 0:
                continue

            duration = leg.get("durationInMinutes", 0)
            carriers = leg.get("carriers", {}).get("marketing", [])
            dest_info = leg.get("destination", {})
            origin_info = leg.get("origin", {})

            if carriers and not logged_carrier_payload:
                logger.info("Carrier payload sample: %s", carriers)
                logged_carrier_payload = True

            segments = leg.get("segments", [])
            stopovers = []
            if stops > 0 and len(segments) > 1:
                for seg_idx in range(len(segments) - 1):
                    seg = segments[seg_idx]
                    next_seg = segments[seg_idx + 1]

                    stop_dest = seg.get("destination", {})
                    stop_city = stop_dest.get("city", stop_dest.get("name", ""))
                    stop_code = stop_dest.get("displayCode", "")

                    seg_arr = seg.get("arrival", "")
                    next_dep = next_seg.get("departure", "")

                    layover_min = 0
                    if seg_arr and next_dep:
                        try:
                            arr_time = datetime.datetime.fromisoformat(seg_arr)
                            dep_time = datetime.datetime.fromisoformat(next_dep)
                            layover_min = int((dep_time - arr_time).total_seconds() / 60)
                        except ValueError:
                            pass

                    stopovers.append(
                        {
                            "città": stop_city,
                            "codice": stop_code,
                            "arrivo": datetime.datetime.fromisoformat(seg_arr).strftime("%H:%M")
                            if seg_arr
                            else "",
                            "partenza": datetime.datetime.fromisoformat(next_dep).strftime("%H:%M")
                            if next_dep
                            else "",
                            "attesa": f"{layover_min // 60}h {layover_min % 60:02d}min"
                            if layover_min > 0
                            else "",
                        }
                    )

            carrier_name = (
                normalize_carrier_name(carriers[0].get("name", "N/A"))
                if carriers
                else "N/A"
            )
            carrier_logo = carriers[0].get("logoUrl") if carriers else ""

            flight = {
                "città": dest_info.get("city", city["name"]),
                "paese": dest_info.get("country", city.get("country", "")),
                "codice_dest": dest_info.get("displayCode", city["skyCode"]),
                "codice_origine": origin_info.get("displayCode", origin.skyId),
                "prezzo": price,
                "partenza": dep.strftime("%H:%M"),
                "arrivo": arr.strftime("%H:%M"),
                "durata": f"{duration // 60}h {duration % 60:02d}min",
                "durata_min": duration,
                "scali": stops,
                "stopovers": stopovers,
                "compagnia": carrier_name,
                "logo_url": carrier_logo,
            }

            key = (
                f"{flight['codice_origine']}-{flight['codice_dest']}-"
                f"{flight['partenza']}-{carrier_name}"
            )
            if key in voli_keys:
                existing_idx = voli_keys[key]
                if flight["prezzo"] < voli_trovati[existing_idx]["prezzo"]:
                    voli_trovati[existing_idx] = flight
            else:
                voli_keys[key] = len(voli_trovati)
                voli_trovati.append(flight)
    voli_visti = set()
    for bucket in flight_response.json.get("itineraries", {}).get("buckets", []):
        for item in bucket.get("items", []):
            if item["id"] in voli_visti:
                continue
            voli_visti.add(item["id"])

            price = item.get("price", {}).get("raw", 999999)
            if price > max_price:
                continue

            leg = item.get("legs", [{}])[0]
            dep_str = leg.get("departure", "")
            arr_str = leg.get("arrival", "")
            if not dep_str or not arr_str:
                continue

            dep = datetime.datetime.fromisoformat(dep_str)
            arr = datetime.datetime.fromisoformat(arr_str)

            # Check departure time is within the selected range
            dep_minutes = dep.hour * 60 + dep.minute
            min_minutes = min_hour * 60
            max_minutes = max_hour * 60
            if dep_minutes < min_minutes or dep_minutes > max_minutes:
                continue

            if same_day and arr.date() != dep.date():
                continue

            stops = leg.get("stopCount", 0)
            if direct_only and stops > 0:
                continue

            duration = leg.get("durationInMinutes", 0)
            carriers = leg.get("carriers", {}).get("marketing", [])
            dest_info = leg.get("destination", {})
            origin_info = leg.get("origin", {})

            if carriers and not logged_carrier_payload:
                logger.info("Carrier payload sample: %s", carriers)
                logged_carrier_payload = True

            segments = leg.get("segments", [])
            stopovers = []
            if stops > 0 and len(segments) > 1:
                for seg_idx in range(len(segments) - 1):
                    seg = segments[seg_idx]
                    next_seg = segments[seg_idx + 1]

                    stop_dest = seg.get("destination", {})
                    stop_city = stop_dest.get("city", stop_dest.get("name", ""))
                    stop_code = stop_dest.get("displayCode", "")

                    seg_arr = seg.get("arrival", "")
                    next_dep = next_seg.get("departure", "")

                    layover_min = 0
                    if seg_arr and next_dep:
                        try:
                            arr_time = datetime.datetime.fromisoformat(seg_arr)
                            dep_time = datetime.datetime.fromisoformat(next_dep)
                            layover_min = int((dep_time - arr_time).total_seconds() / 60)
                        except ValueError:
                            pass

                    stopovers.append(
                        {
                            "città": stop_city,
                            "codice": stop_code,
                            "arrivo": datetime.datetime.fromisoformat(seg_arr).strftime("%H:%M")
                            if seg_arr
                            else "",
                            "partenza": datetime.datetime.fromisoformat(next_dep).strftime("%H:%M")
                            if next_dep
                            else "",
                            "attesa": f"{layover_min // 60}h {layover_min % 60:02d}min"
                            if layover_min > 0
                            else "",
                        }
                    )

            carrier_name = (
                normalize_carrier_name(carriers[0].get("name", "N/A"))
                if carriers
                else "N/A"
            )
            carrier_logo = carriers[0].get("logoUrl") if carriers else ""

            flight = {
                "città": dest_info.get("city", city["name"]),
                "paese": dest_info.get("country", city.get("country", "")),
                "codice_dest": dest_info.get("displayCode", city["skyCode"]),
                "codice_origine": origin_info.get("displayCode", origin.skyId),
                "prezzo": price,
                "partenza": dep.strftime("%H:%M"),
                "arrivo": arr.strftime("%H:%M"),
                "durata": f"{duration // 60}h {duration % 60:02d}min",
                "durata_min": duration,
                "scali": stops,
                "stopovers": stopovers,
                "compagnia": carrier_name,
                "logo_url": carrier_logo,
            }

            key = (
                f"{flight['codice_origine']}-{flight['codice_dest']}-"
                f"{flight['partenza']}-{carrier_name}"
            )
            if key in voli_keys:
                existing_idx = voli_keys[key]
                if flight["prezzo"] < voli_trovati[existing_idx]["prezzo"]:
                    voli_trovati[existing_idx] = flight
            else:
                voli_keys[key] = len(voli_trovati)
                voli_trovati.append(flight)


def search_everywhere_multi(
    scanner: SkyScanner,
    origin_list,
    depart_date,
    max_price,
    min_hour,
    max_hour,
    min_arrival_hour,
    max_arrival_hour,
    direct_only,
    same_day,
):
    origin_codes = [o.skyId for o in origin_list]
    all_countries = {}

    for origin in origin_list:
        response = scanner.get_flight_prices(
            origin=origin,
            destination=SpecialTypes.EVERYWHERE,
            depart_date=depart_date,
        )

        for r in response.json.get("everywhereDestination", {}).get("results", []):
            content = r.get("content", {})
            location = content.get("location", {})
            price = content.get("flightQuotes", {}).get("cheapest", {}).get(
                "rawPrice", 999999
            )
            if location.get("name") and location.get("skyCode") and price and price <= max_price:
                sky_code = location["skyCode"]
                if sky_code not in all_countries:
                    all_countries[sky_code] = {
                        "name": location["name"],
                        "skyCode": sky_code,
                    }

    countries = list(all_countries.values())

    all_cities = {}
    first_origin = origin_list[0]

    for country in countries:
        country_airports = scanner.search_airports(country["skyCode"])
        if not country_airports:
            continue
        country_entity = next(
            (a for a in country_airports if a.skyId == country["skyCode"]),
            country_airports[0],
        )

        country_response = scanner.get_flight_prices(
            origin=first_origin,
            destination=country_entity,
            depart_date=depart_date,
        )

        for r in country_response.json.get("countryDestination", {}).get("results", []):
            content = r.get("content", {})
            location = content.get("location", {})
            city_price = content.get("flightQuotes", {}).get("cheapest", {}).get(
                "rawPrice", 999999
            )
            if location.get("name") and location.get("skyCode") and city_price and city_price <= max_price:
                sky_code = location["skyCode"]
                if sky_code not in all_cities:
                    all_cities[sky_code] = {
                        "name": location["name"],
                        "skyCode": sky_code,
                        "country": country["name"],
                    }

    cities = list(all_cities.values())

    voli_trovati = []
    voli_keys = {}

    for city in cities:
        for origin in origin_list:
            city_airports = scanner.search_airports(city["skyCode"])
            if not city_airports:
                continue

            flight_response = scanner.get_flight_prices(
                origin=origin, destination=city_airports[0], depart_date=depart_date
            )

            process_flight_response(
                flight_response,
                origin,
                city,
                depart_date,
                max_price,
                min_hour,
                max_hour,
                min_arrival_hour,
                max_arrival_hour,
                direct_only,
                same_day,
                voli_trovati,
                voli_keys,
            )

    stats = {
        "paesi": len(countries),
        "città": len(cities),
        "partenze": ", ".join(origin_codes),
    }

    return voli_trovati, stats
    origin_codes = [o.skyId for o in origin_list]
    all_countries = {}

    for origin in origin_list:
        response = scanner.get_flight_prices(
            origin=origin,
            destination=SpecialTypes.EVERYWHERE,
            depart_date=depart_date,
        )

        for r in response.json.get("everywhereDestination", {}).get("results", []):
            content = r.get("content", {})
            location = content.get("location", {})
            price = content.get("flightQuotes", {}).get("cheapest", {}).get(
                "rawPrice", 999999
            )
            if location.get("name") and location.get("skyCode") and price and price <= max_price:
                sky_code = location["skyCode"]
                if sky_code not in all_countries:
                    all_countries[sky_code] = {
                        "name": location["name"],
                        "skyCode": sky_code,
                    }

    countries = list(all_countries.values())

    all_cities = {}
    first_origin = origin_list[0]

    for country in countries:
        country_airports = scanner.search_airports(country["skyCode"])
        if not country_airports:
            continue
        country_entity = next(
            (a for a in country_airports if a.skyId == country["skyCode"]),
            country_airports[0],
        )

        country_response = scanner.get_flight_prices(
            origin=first_origin,
            destination=country_entity,
            depart_date=depart_date,
        )

        for r in country_response.json.get("countryDestination", {}).get("results", []):
            content = r.get("content", {})
            location = content.get("location", {})
            city_price = content.get("flightQuotes", {}).get("cheapest", {}).get(
                "rawPrice", 999999
            )
            if location.get("name") and location.get("skyCode") and city_price and city_price <= max_price:
                sky_code = location["skyCode"]
                if sky_code not in all_cities:
                    all_cities[sky_code] = {
                        "name": location["name"],
                        "skyCode": sky_code,
                        "country": country["name"],
                    }

    cities = list(all_cities.values())

    voli_trovati = []
    voli_keys = {}

    for city in cities:
        for origin in origin_list:
            city_airports = scanner.search_airports(city["skyCode"])
            if not city_airports:
                continue

            flight_response = scanner.get_flight_prices(
                origin=origin, destination=city_airports[0], depart_date=depart_date
            )

            process_flight_response(
                flight_response,
                origin,
                city,
                depart_date,
                max_price,
                min_hour,
                max_hour,
                direct_only,
                same_day,
                voli_trovati,
                voli_keys,
            )

    stats = {
        "paesi": len(countries),
        "città": len(cities),
        "partenze": ", ".join(origin_codes),
    }

    return voli_trovati, stats


def search_specific_destinations(
    scanner: SkyScanner,
    origin_list,
    dest_list,
    depart_date,
    max_price,
    min_hour,
    max_hour,
    min_arrival_hour,
    max_arrival_hour,
    direct_only,
    same_day,
):
    origin_codes = [o.skyId for o in origin_list]
    dest_codes = [d.skyId for d in dest_list]

    voli_trovati = []
    voli_keys = {}

    for origin in origin_list:
        for dest in dest_list:
            flight_response = scanner.get_flight_prices(
                origin=origin, destination=dest, depart_date=depart_date
            )

            city_info = {"name": dest.title, "skyCode": dest.skyId, "country": ""}

            process_flight_response(
                flight_response,
                origin,
                city_info,
                depart_date,
                max_price,
                min_hour,
                max_hour,
                min_arrival_hour,
                max_arrival_hour,
                direct_only,
                same_day,
                voli_trovati,
                voli_keys,
            )

    stats = {
        "partenze": ", ".join(origin_codes),
        "destinazioni": ", ".join(dest_codes),
    }

    return voli_trovati, stats
    origin_codes = [o.skyId for o in origin_list]
    dest_codes = [d.skyId for d in dest_list]

    voli_trovati = []
    voli_keys = {}

    for origin in origin_list:
        for dest in dest_list:
            flight_response = scanner.get_flight_prices(
                origin=origin, destination=dest, depart_date=depart_date
            )

            city_info = {"name": dest.title, "skyCode": dest.skyId, "country": ""}

            process_flight_response(
                flight_response,
                origin,
                city_info,
                depart_date,
                max_price,
                min_hour,
                max_hour,
                direct_only,
                same_day,
                voli_trovati,
                voli_keys,
            )

    stats = {
        "partenze": ", ".join(origin_codes),
        "destinazioni": ", ".join(dest_codes),
    }

    return voli_trovati, stats


def sort_flights(flights, sort_key):
    if sort_key == "orario":
        return sorted(flights, key=lambda f: f.get("partenza", "00:00"))
    if sort_key == "durata":
        return sorted(flights, key=lambda f: f.get("durata_min", 0))
    return sorted(flights, key=lambda f: f.get("prezzo", 0))


def sse_event(payload):
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/airports")
def api_airports():
    query = request.args.get("query", "").strip()
    if len(query) < 2:
        return jsonify([])

    scanner = build_scanner()
    results = scanner.search_airports(query)

    return jsonify(
        [
            {
                "title": airport.title,
                "subtitle": airport.subtitle,
                "skyId": airport.skyId,
                "entityType": airport.entity_type,
            }
            for airport in results[:8]
        ]
    )


@app.route("/api/search/stream", methods=["POST"])
def api_search_stream():
    payload = request.get_json(silent=True) or {}

    origin_items = normalize_selected_locations(payload.get("origins", []))
    dest_items = normalize_selected_locations(payload.get("destinations", []))
    origin_codes = dedupe_codes(origin_items)
    dest_codes = dedupe_codes(dest_items)
    search_everywhere = payload.get("search_everywhere", False) or (
        "EVERYWHERE" in dest_codes or not dest_codes
    )

    if not origin_codes:
        return jsonify({"error": "Seleziona almeno un aeroporto di partenza."}), 400

    try:
        depart_date = parse_date(payload.get("depart_date", ""))
        max_price = float(payload.get("max_price", 0))
        min_hour = int(payload.get("min_hour", 0))
        max_hour = int(payload.get("max_hour", 24))
        min_arrival_hour = int(payload.get("min_arrival_hour", 0))
        max_arrival_hour = int(payload.get("max_arrival_hour", 24))
    except (TypeError, ValueError):
        return (
            jsonify(
                {
                    "error": "Controlla i valori inseriti. Formato data: GG/MM/AAAA.",
                }
            ),
            400,
        )

    direct_only = bool(payload.get("direct_only"))
    same_day = bool(payload.get("same_day", True))
    sort_key = payload.get("sort", "prezzo")

    def generate():
        scanner = build_scanner()

        try:
            origin_list = [airport_from_code(scanner, code) for code in origin_codes]
        except GenericError as exc:
            yield sse_event({"type": "error", "error": str(exc)})
            return

        yield sse_event(
            {
                "type": "progress",
                "message": "Connessione a Skyscanner...",
                "current": 0,
                "total": 0,
            }
        )

        nonlocal search_everywhere, dest_items, dest_codes

        if not search_everywhere:
            country_items = [
                item for item in dest_items if item["entity_type"] == "COUNTRY"
            ]
            if country_items:
                for idx, item in enumerate(country_items, start=1):
                    title = item.get("title") or item.get("code") or "paese"
                    yield sse_event(
                        {
                            "type": "progress",
                            "message": f"Espando {title} in città",
                            "current": idx,
                            "total": len(country_items),
                        }
                    )

                expanded = []
                for item in country_items:
                    expanded.extend(
                        get_country_places(
                            scanner, item["code"], item.get("title", "")
                        )
                    )

                expanded_items = [
                    {"code": place["skyCode"], "entity_type": place["type"]}
                    for place in expanded
                    if place.get("skyCode")
                ]
                dest_items = [
                    item for item in dest_items if item["entity_type"] != "COUNTRY"
                ] + expanded_items
                dest_codes = dedupe_codes(dest_items)

            if not dest_codes:
                yield sse_event(
                    {
                        "type": "error",
                        "error": "Nessuna destinazione valida trovata.",
                    }
                )
                return

        if search_everywhere:
            origin_codes_str = [o.skyId for o in origin_list]
            all_countries = {}

            total_origins = len(origin_list)
            for origin_idx, origin in enumerate(origin_list, start=1):
                yield sse_event(
                    {
                        "type": "progress",
                        "message": f"Cerco paesi da {origin.skyId}",
                        "current": origin_idx,
                        "total": total_origins,
                    }
                )

                response = scanner.get_flight_prices(
                    origin=origin,
                    destination=SpecialTypes.EVERYWHERE,
                    depart_date=depart_date,
                )

                for r in response.json.get("everywhereDestination", {}).get("results", []):
                    content = r.get("content", {})
                    location = content.get("location", {})
                    price = content.get("flightQuotes", {}).get("cheapest", {}).get(
                        "rawPrice", 999999
                    )
                    if location.get("name") and location.get("skyCode") and price and price <= max_price:
                        sky_code = location["skyCode"]
                        if sky_code not in all_countries:
                            all_countries[sky_code] = {
                                "name": location["name"],
                                "skyCode": sky_code,
                            }

            countries = list(all_countries.values())
            if countries:
                yield sse_event(
                    {
                        "type": "progress",
                        "message": f"Trovati {len(countries)} paesi in budget",
                        "current": len(countries),
                        "total": len(countries),
                    }
                )

            all_cities = {}
            first_origin = origin_list[0]
            total_countries = len(countries)

            for country_idx, country in enumerate(countries, start=1):
                yield sse_event(
                    {
                        "type": "progress",
                        "message": f"Cerco città in {country['name']}",
                        "current": country_idx,
                        "total": total_countries,
                    }
                )

                country_airports = scanner.search_airports(country["skyCode"])
                if not country_airports:
                    continue
                country_entity = next(
                    (a for a in country_airports if a.skyId == country["skyCode"]),
                    country_airports[0],
                )

                country_response = scanner.get_flight_prices(
                    origin=first_origin,
                    destination=country_entity,
                    depart_date=depart_date,
                )

                for r in country_response.json.get("countryDestination", {}).get("results", []):
                    content = r.get("content", {})
                    location = content.get("location", {})
                    city_price = content.get("flightQuotes", {}).get("cheapest", {}).get(
                        "rawPrice", 999999
                    )
                    if location.get("name") and location.get("skyCode") and city_price and city_price <= max_price:
                        sky_code = location["skyCode"]
                        if sky_code not in all_cities:
                            all_cities[sky_code] = {
                                "name": location["name"],
                                "skyCode": sky_code,
                                "country": country["name"],
                            }

            cities = list(all_cities.values())
            if cities:
                yield sse_event(
                    {
                        "type": "progress",
                        "message": f"Trovate {len(cities)} città in budget",
                        "current": len(cities),
                        "total": len(cities),
                    }
                )

            voli_trovati = []
            voli_keys = {}
            total_searches = len(cities) * len(origin_list)
            search_count = 0

            for city in cities:
                for origin in origin_list:
                    search_count += 1
                    country_name = city.get("country", "")
                    detail = f" ({country_name})" if country_name else ""
                    yield sse_event(
                        {
                            "type": "progress",
                            "message": f"Guardo {origin.skyId} → {city['name']}{detail}",
                            "current": search_count,
                            "total": total_searches,
                            "found": len(voli_trovati),
                        }
                    )

                    city_airports = scanner.search_airports(city["skyCode"])
                    if not city_airports:
                        continue

                    flight_response = scanner.get_flight_prices(
                        origin=origin,
                        destination=city_airports[0],
                        depart_date=depart_date,
                    )

                    before_count = len(voli_trovati)
                    process_flight_response(
                        flight_response,
                        origin,
                        city,
                        depart_date,
                        max_price,
                        min_hour,
                        max_hour,
                        min_arrival_hour,
                        max_arrival_hour,
                        direct_only,
                        same_day,
                        voli_trovati,
                        voli_keys,
                    )
                    if len(voli_trovati) > before_count:
                        yield sse_event(
                            {
                                "type": "results",
                                "flights": voli_trovati[before_count:],
                                "count": len(voli_trovati),
                            }
                        )

            stats = {
                "paesi": len(countries),
                "città": len(cities),
                "partenze": ", ".join(origin_codes_str),
            }
            flights = sort_flights(voli_trovati, sort_key)

        else:
            try:
                dest_list = [airport_from_code(scanner, code) for code in dest_codes]
            except GenericError as exc:
                yield sse_event({"type": "error", "error": str(exc)})
                return

            origin_codes_str = [o.skyId for o in origin_list]
            dest_codes_str = [d.skyId for d in dest_list]

            voli_trovati = []
            voli_keys = {}
            total_searches = len(origin_list) * len(dest_list)
            search_count = 0

            for origin in origin_list:
                for dest in dest_list:
                    search_count += 1
                    yield sse_event(
                        {
                            "type": "progress",
                            "message": f"Guardo {origin.skyId} → {dest.title}",
                            "current": search_count,
                            "total": total_searches,
                            "found": len(voli_trovati),
                        }
                    )

                    flight_response = scanner.get_flight_prices(
                        origin=origin, destination=dest, depart_date=depart_date
                    )

                    city_info = {"name": dest.title, "skyCode": dest.skyId, "country": ""}

                    before_count = len(voli_trovati)
                    process_flight_response(
                        flight_response,
                        origin,
                        city_info,
                        depart_date,
                        max_price,
                        min_hour,
                        max_hour,
                        min_arrival_hour,
                        max_arrival_hour,
                        direct_only,
                        same_day,
                        voli_trovati,
                        voli_keys,
                    )
                    if len(voli_trovati) > before_count:
                        yield sse_event(
                            {
                                "type": "results",
                                "flights": voli_trovati[before_count:],
                                "count": len(voli_trovati),
                            }
                        )

            stats = {
                "partenze": ", ".join(origin_codes_str),
                "destinazioni": ", ".join(dest_codes_str),
            }
            flights = sort_flights(voli_trovati, sort_key)

        yield sse_event(
            {
                "type": "complete",
                "flights": flights,
                "stats": stats,
                "count": len(flights),
                "search_everywhere": search_everywhere,
            }
        )

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/search", methods=["POST"])
def api_search():
    payload = request.get_json(silent=True) or {}

    origin_items = normalize_selected_locations(payload.get("origins", []))
    dest_items = normalize_selected_locations(payload.get("destinations", []))
    origin_codes = dedupe_codes(origin_items)
    dest_codes = dedupe_codes(dest_items)
    search_everywhere = payload.get("search_everywhere", False) or (
        "EVERYWHERE" in dest_codes or not dest_codes
    )

    if not origin_codes:
        return jsonify({"error": "Seleziona almeno un aeroporto di partenza."}), 400

    try:
        depart_date = parse_date(payload.get("depart_date", ""))
        max_price = float(payload.get("max_price", 0))
        min_hour = int(payload.get("min_hour", 0))
        max_hour = int(payload.get("max_hour", 24))
        min_arrival_hour = int(payload.get("min_arrival_hour", 0))
        max_arrival_hour = int(payload.get("max_arrival_hour", 24))
    except (TypeError, ValueError):
        return (
            jsonify(
                {
                    "error": "Controlla i valori inseriti. Formato data: GG/MM/AAAA.",
                }
            ),
            400,
        )

    direct_only = bool(payload.get("direct_only"))
    same_day = bool(payload.get("same_day", True))
    sort_key = payload.get("sort", "prezzo")

    scanner = build_scanner()

    try:
        origin_list = [airport_from_code(scanner, code) for code in origin_codes]
    except GenericError as exc:
        return jsonify({"error": str(exc)}), 400

    if not search_everywhere:
        country_items = [
            item for item in dest_items if item["entity_type"] == "COUNTRY"
        ]
        if country_items:
            expanded = []
            for item in country_items:
                expanded.extend(
                    get_country_places(
                        scanner, item["code"], item.get("title", "")
                    )
                )

            expanded_items = [
                {"code": place["skyCode"], "entity_type": place["type"]}
                for place in expanded
                if place.get("skyCode")
            ]
            dest_items = [
                item for item in dest_items if item["entity_type"] != "COUNTRY"
            ] + expanded_items
            dest_codes = dedupe_codes(dest_items)

        if not dest_codes:
            return (
                jsonify(
                    {
                        "error": "Nessuna destinazione valida trovata per il paese selezionato.",
                    }
                ),
                400,
            )

    if search_everywhere:
        flights, stats = search_everywhere_multi(
            scanner,
            origin_list,
            depart_date,
            max_price,
            min_hour,
            max_hour,
            min_arrival_hour,
            max_arrival_hour,
            direct_only,
            same_day,
        )
    else:
        try:
            dest_list = [airport_from_code(scanner, code) for code in dest_codes]
        except GenericError as exc:
            return jsonify({"error": str(exc)}), 400

        flights, stats = search_specific_destinations(
            scanner,
            origin_list,
            dest_list,
            depart_date,
            max_price,
            min_hour,
            max_hour,
            min_arrival_hour,
            max_arrival_hour,
            direct_only,
            same_day,
        )

    flights = sort_flights(flights, sort_key)

    return jsonify(
        {
            "flights": flights,
            "stats": stats,
            "count": len(flights),
            "search_everywhere": search_everywhere,
        }
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
