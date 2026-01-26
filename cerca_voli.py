from skyscanner import SkyScanner
from skyscanner.types import SpecialTypes
import datetime

# Configurazione filtri
MAX_PRICE = 100
MIN_DEPARTURE_HOUR = 18
MAX_ARRIVAL_HOUR = 23

scanner = SkyScanner(locale="it-IT", currency="EUR", market="IT")

VCE = scanner.get_airport_by_code("VCE")
depart_date = datetime.datetime(2026, 2, 6)

print(f"🛫 Voli da VENEZIA il {depart_date.strftime('%d/%m/%Y')}")
print(f"   Filtri: max €{MAX_PRICE}, partenza ≥{MIN_DEPARTURE_HOUR}:00, arrivo ≤{MAX_ARRIVAL_HOUR}:59")
print()

# 1. Cerca tutti i paesi economici
print("1. Cerco paesi economici...", end=" ", flush=True)
response = scanner.get_flight_prices(
    origin=VCE,
    destination=SpecialTypes.EVERYWHERE,
    depart_date=depart_date
)

countries = []
for r in response.json.get("everywhereDestination", {}).get("results", []):
    content = r.get("content", {})
    location = content.get("location", {})
    price = content.get("flightQuotes", {}).get("cheapest", {}).get("rawPrice", 999999)
    if location.get("name") and location.get("skyCode") and price and price <= MAX_PRICE:
        countries.append({
            "name": location["name"],
            "skyCode": location["skyCode"],
            "price": price
        })

print(f"{len(countries)} paesi trovati")

# 2. Per ogni paese, ottieni le città
print("2. Cerco città per ogni paese...", end=" ", flush=True)
all_cities = []

for country in countries:
    try:
        # Cerca il paese
        country_airports = scanner.search_airports(country["skyCode"])
        if not country_airports:
            continue

        country_entity = next((a for a in country_airports if a.skyId == country["skyCode"]), country_airports[0])

        # Cerca voli verso il paese per ottenere le città
        country_response = scanner.get_flight_prices(
            origin=VCE,
            destination=country_entity,
            depart_date=depart_date
        )

        # Estrai città da countryDestination
        for r in country_response.json.get("countryDestination", {}).get("results", []):
            content = r.get("content", {})
            location = content.get("location", {})
            city_price = content.get("flightQuotes", {}).get("cheapest", {}).get("rawPrice", 999999)

            if location.get("name") and location.get("skyCode") and city_price and city_price <= MAX_PRICE:
                all_cities.append({
                    "name": location["name"],
                    "skyCode": location["skyCode"],
                    "country": country["name"]
                })
    except:
        continue

# Rimuovi città duplicate
seen = set()
cities = []
for c in all_cities:
    if c["skyCode"] not in seen:
        seen.add(c["skyCode"])
        cities.append(c)

print(f"{len(cities)} città trovate")

# 3. Cerca voli per ogni città
print(f"3. Cerco voli per {len(cities)} città...", end=" ", flush=True)
voli_trovati = []

for city in cities:
    try:
        city_airports = scanner.search_airports(city["skyCode"])
        if not city_airports:
            continue

        flight_response = scanner.get_flight_prices(
            origin=VCE,
            destination=city_airports[0],
            depart_date=depart_date
        )

        voli_visti = set()
        for bucket in flight_response.json.get("itineraries", {}).get("buckets", []):
            for item in bucket.get("items", []):
                if item["id"] in voli_visti:
                    continue
                voli_visti.add(item["id"])

                price = item.get("price", {}).get("raw", 999999)
                if price > MAX_PRICE:
                    continue

                leg = item.get("legs", [{}])[0]
                dep_str = leg.get("departure", "")
                arr_str = leg.get("arrival", "")
                if not dep_str or not arr_str:
                    continue

                dep = datetime.datetime.fromisoformat(dep_str)
                arr = datetime.datetime.fromisoformat(arr_str)

                if dep.hour < MIN_DEPARTURE_HOUR or arr.date() != dep.date() or arr.hour > MAX_ARRIVAL_HOUR:
                    continue

                duration = leg.get("durationInMinutes", 0)
                carriers = leg.get("carriers", {}).get("marketing", [])
                dest_country = leg.get("destination", {}).get("country", city["country"])

                voli_trovati.append({
                    "città": leg.get("destination", {}).get("city", city["name"]),
                    "paese": dest_country,
                    "prezzo": price,
                    "partenza": dep.strftime("%H:%M"),
                    "arrivo": arr.strftime("%H:%M"),
                    "durata": f"{duration // 60}h{duration % 60:02d}",
                    "scali": leg.get("stopCount", 0),
                    "compagnia": carriers[0].get("name", "N/A") if carriers else "N/A"
                })
    except:
        continue

print("fatto!\n")

# Rimuovi duplicati e ordina
voli_unici = list({f"{v['città']}-{v['partenza']}-{v['prezzo']}": v for v in voli_trovati}.values())
voli_unici.sort(key=lambda x: x["prezzo"])

# Output
print(f"{'DESTINAZIONE':<25} {'PAESE':<15} {'PREZZO':>7} {'ORARIO':>13} {'DURATA':>8} {'COMPAGNIA':<15}")
print("-" * 90)

for v in voli_unici:
    scali = "" if v["scali"] == 0 else f" ({v['scali']}x)"
    dest = v['città'][:24]
    paese = v['paese'][:14]
    print(f"{dest:<25} {paese:<15} {v['prezzo']:>6.2f}€ {v['partenza']} → {v['arrivo']:>5} {v['durata']+scali:>8} {v['compagnia']:<15}")

print(f"\n✅ {len(voli_unici)} voli trovati")