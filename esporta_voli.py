from skyscanner import SkyScanner
from skyscanner.types import SpecialTypes
import datetime
import json
import csv

scanner = SkyScanner(locale="it-IT", currency="EUR", market="IT")

VCE = scanner.get_airport_by_code("VCE")
depart_date = datetime.datetime(2026, 2, 6)

print("Cerco voli verso LONDRA (città specifica)...")

# Cerca aeroporto Londra
airports = scanner.search_airports("London")
dest_airport = airports[0]
print(f"Aeroporto trovato: {dest_airport.title} (skyId: {dest_airport.skyId})")

# Cerca i voli
response = scanner.get_flight_prices(
    origin=VCE,
    destination=dest_airport,
    depart_date=depart_date
)

# Salva JSON grezzo per analisi
with open("risposta_grezza.json", "w", encoding="utf-8") as f:
    json.dump(response.json, f, indent=2, ensure_ascii=False)
print("\nJSON grezzo salvato in: risposta_grezza.json")

# Prova a estrarre gli itinerari in vari modi possibili
data = response.json

print("\n=== STRUTTURA RISPOSTA ===")
print(f"Chiavi principali: {list(data.keys())}")

# Cerca itineraries
if "itineraries" in data:
    itin = data["itineraries"]
    print(f"\nChiavi in 'itineraries': {list(itin.keys()) if isinstance(itin, dict) else 'è una lista'}")

    if isinstance(itin, dict):
        for key in itin.keys():
            val = itin[key]
            if isinstance(val, list):
                print(f"  - {key}: lista con {len(val)} elementi")
                if len(val) > 0:
                    print(f"    Primo elemento chiavi: {list(val[0].keys()) if isinstance(val[0], dict) else val[0]}")

# Cerca results
if "results" in data:
    print(f"\nChiavi in 'results': {list(data['results'].keys()) if isinstance(data['results'], dict) else 'è una lista'}")

# Esporta in CSV tutti i dati che troviamo
print("\n=== TENTATIVO ESTRAZIONE VOLI ===")

voli = []

# Metodo 1: itineraries.results
if "itineraries" in data and isinstance(data["itineraries"], dict):
    results = data["itineraries"].get("results", [])
    print(f"Trovati {len(results)} risultati in itineraries.results")

    for i, r in enumerate(results[:3]):  # primi 3 per debug
        print(f"\nRisultato {i+1} chiavi: {list(r.keys())}")

# Metodo 2: itineraries.buckets
if "itineraries" in data and isinstance(data["itineraries"], dict):
    buckets = data["itineraries"].get("buckets", [])
    print(f"\nTrovati {len(buckets)} buckets")
    for b in buckets:
        print(f"  - {b.get('id', 'N/A')}: {len(b.get('items', []))} items")

# Metodo 3: cerca "legs" ovunque
def find_legs(obj, path=""):
    if isinstance(obj, dict):
        if "legs" in obj:
            print(f"Trovato 'legs' in: {path}")
        for k, v in obj.items():
            find_legs(v, f"{path}.{k}")
    elif isinstance(obj, list) and len(obj) > 0:
        find_legs(obj[0], f"{path}[0]")

print("\n=== RICERCA 'legs' nella struttura ===")
find_legs(data)

# Salva anche un CSV con i dati grezzi degli itinerari
if "itineraries" in data and isinstance(data["itineraries"], dict):
    results = data["itineraries"].get("results", [])
    if results:
        with open("voli_grezzi.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            # Scrivi tutte le chiavi come header
            if isinstance(results[0], dict):
                writer.writerow(results[0].keys())
                for r in results:
                    writer.writerow([str(v)[:100] for v in r.values()])  # tronca valori lunghi
        print("\nCSV salvato in: voli_grezzi.csv")

print("\n\nApri 'risposta_grezza.json' con un editor di testo per vedere la struttura completa!")