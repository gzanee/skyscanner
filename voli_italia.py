from skyscanner import SkyScanner
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

# Cerca Italia
airports = scanner.search_airports("Italy")
italy = next((a for a in airports if a.skyId == "IT"), airports[0])

# Ottieni città italiane
response = scanner.get_flight_prices(origin=VCE, destination=italy, depart_date=depart_date)
cities = []
for r in response.json.get("countryDestination", {}).get("results", []):
    content = r.get("content", {})
    location = content.get("location", {})
    price = content.get("flightQuotes", {}).get("cheapest", {}).get("rawPrice", 999999)
    if location.get("name") and location.get("skyCode") and price <= MAX_PRICE:
        cities.append({"name": location["name"], "skyCode": location["skyCode"]})

print(f"Cerco voli per {len(cities)} città...", end=" ", flush=True)

# Cerca voli per ogni città
voli_trovati = []
for city in cities:
    try:
        city_airports = scanner.search_airports(city["skyCode"])
        if not city_airports:
            continue

        flight_response = scanner.get_flight_prices(
            origin=VCE, destination=city_airports[0], depart_date=depart_date
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

                voli_trovati.append({
                    "città": leg.get("destination", {}).get("city", city["name"]),
                    "aeroporto": leg.get("destination", {}).get("name", ""),
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
print(f"{'DESTINAZIONE':<20} {'PREZZO':>8} {'ORARIO':>14} {'DURATA':>8} {'COMPAGNIA':<15}")
print("-" * 70)

for v in voli_unici:
    scali = "" if v["scali"] == 0 else f" ({v['scali']}x)"
    print(f"{v['città']:<20} {v['prezzo']:>7.2f}€ {v['partenza']} → {v['arrivo']:>5} {v['durata']+scali:>8} {v['compagnia']:<15}")

print(f"\n✅ {len(voli_unici)} voli trovati")