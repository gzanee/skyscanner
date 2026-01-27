import datetime
from flask import Flask, jsonify, render_template, request
from skyscanner import SkyScanner
from skyscanner.errors import GenericError
from skyscanner.types import Airport, SpecialTypes


app = Flask(__name__)


def build_scanner() -> SkyScanner:
    return SkyScanner(locale="it-IT", currency="EUR", market="IT")


def parse_date(date_str: str) -> datetime.datetime:
    return datetime.datetime.strptime(date_str, "%d/%m/%Y")


def airport_from_code(scanner: SkyScanner, code: str) -> Airport:
    return scanner.get_airport_by_code(code)


def process_flight_response(
    flight_response,
    origin: Airport,
    city,
    depart_date,
    max_price,
    min_hour,
    direct_only,
    same_day,
    voli_trovati,
    voli_keys,
):
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

            if dep.hour < min_hour:
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
                "compagnia": carriers[0].get("name", "N/A") if carriers else "N/A",
            }

            key = (
                f"{flight['codice_origine']}-{flight['codice_dest']}-"
                f"{flight['partenza']}-{flight['prezzo']}"
            )
            if key not in voli_keys:
                voli_keys.add(key)
                voli_trovati.append(flight)


def search_everywhere_multi(
    scanner: SkyScanner,
    origin_list,
    depart_date,
    max_price,
    min_hour,
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
    voli_keys = set()

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
    direct_only,
    same_day,
):
    origin_codes = [o.skyId for o in origin_list]
    dest_codes = [d.skyId for d in dest_list]

    voli_trovati = []
    voli_keys = set()

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


@app.route("/api/search", methods=["POST"])
def api_search():
    payload = request.get_json(silent=True) or {}

    origin_codes = payload.get("origins", [])
    dest_codes = payload.get("destinations", [])
    search_everywhere = payload.get("search_everywhere", False) or (
        "EVERYWHERE" in dest_codes or not dest_codes
    )

    if not origin_codes:
        return jsonify({"error": "Seleziona almeno un aeroporto di partenza."}), 400

    try:
        depart_date = parse_date(payload.get("depart_date", ""))
        max_price = float(payload.get("max_price", 0))
        min_hour = int(payload.get("min_hour", 0))
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

    if search_everywhere:
        flights, stats = search_everywhere_multi(
            scanner,
            origin_list,
            depart_date,
            max_price,
            min_hour,
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
