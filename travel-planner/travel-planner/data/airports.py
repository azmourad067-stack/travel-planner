"""
data/airports.py
-----------------
Référentiel statique des principaux aéroports internationaux, utilisé pour
retrouver l'aéroport le plus proche d'une ville géolocalisée. C'est
nécessaire pour interroger l'API Amadeus Flight Offers Search, qui
fonctionne par codes IATA et non par coordonnées GPS.

Liste volontairement limitée aux grands hubs pour rester lisible ; à
enrichir si besoin avec un référentiel complet (ex. données ouvertes
OpenFlights.org) sans changer l'API de `find_nearest_airport`.
"""

from __future__ import annotations

import math

AIRPORTS = [
    {"iata": "CDG", "city": "Paris", "lat": 49.0097, "lon": 2.5479},
    {"iata": "ORY", "city": "Paris", "lat": 48.7262, "lon": 2.3652},
    {"iata": "LYS", "city": "Lyon", "lat": 45.7256, "lon": 5.0811},
    {"iata": "MRS", "city": "Marseille", "lat": 43.4393, "lon": 5.2214},
    {"iata": "NCE", "city": "Nice", "lat": 43.6584, "lon": 7.2159},
    {"iata": "TLS", "city": "Toulouse", "lat": 43.6293, "lon": 1.3638},
    {"iata": "BOD", "city": "Bordeaux", "lat": 44.8283, "lon": -0.7156},
    {"iata": "NTE", "city": "Nantes", "lat": 47.1532, "lon": -1.6107},
    {"iata": "LIL", "city": "Lille", "lat": 50.5619, "lon": 3.0894},
    {"iata": "STR", "city": "Strasbourg", "lat": 48.5383, "lon": 7.6284},
    {"iata": "LHR", "city": "Londres", "lat": 51.4700, "lon": -0.4543},
    {"iata": "LGW", "city": "Londres", "lat": 51.1537, "lon": -0.1821},
    {"iata": "AMS", "city": "Amsterdam", "lat": 52.3105, "lon": 4.7683},
    {"iata": "BRU", "city": "Bruxelles", "lat": 50.9010, "lon": 4.4844},
    {"iata": "FRA", "city": "Francfort", "lat": 50.0379, "lon": 8.5622},
    {"iata": "MUC", "city": "Munich", "lat": 48.3538, "lon": 11.7861},
    {"iata": "BER", "city": "Berlin", "lat": 52.3667, "lon": 13.5033},
    {"iata": "MAD", "city": "Madrid", "lat": 40.4983, "lon": -3.5676},
    {"iata": "BCN", "city": "Barcelone", "lat": 41.2971, "lon": 2.0785},
    {"iata": "LIS", "city": "Lisbonne", "lat": 38.7813, "lon": -9.1359},
    {"iata": "FCO", "city": "Rome", "lat": 41.8003, "lon": 12.2389},
    {"iata": "MXP", "city": "Milan", "lat": 45.6306, "lon": 8.7281},
    {"iata": "ZRH", "city": "Zurich", "lat": 47.4647, "lon": 8.5492},
    {"iata": "GVA", "city": "Genève", "lat": 46.2381, "lon": 6.1090},
    {"iata": "VIE", "city": "Vienne", "lat": 48.1103, "lon": 16.5697},
    {"iata": "DUB", "city": "Dublin", "lat": 53.4264, "lon": -6.2499},
    {"iata": "CPH", "city": "Copenhague", "lat": 55.6180, "lon": 12.6560},
    {"iata": "ARN", "city": "Stockholm", "lat": 59.6519, "lon": 17.9186},
    {"iata": "OSL", "city": "Oslo", "lat": 60.1976, "lon": 11.1004},
    {"iata": "ATH", "city": "Athènes", "lat": 37.9364, "lon": 23.9445},
    {"iata": "IST", "city": "Istanbul", "lat": 41.2753, "lon": 28.7519},
    {"iata": "JFK", "city": "New York", "lat": 40.6413, "lon": -73.7781},
    {"iata": "YUL", "city": "Montréal", "lat": 45.4706, "lon": -73.7408},
    {"iata": "DXB", "city": "Dubaï", "lat": 25.2532, "lon": 55.3657},
    {"iata": "HND", "city": "Tokyo", "lat": 35.5494, "lon": 139.7798},
    {"iata": "SIN", "city": "Singapour", "lat": 1.3644, "lon": 103.9915},
    {"iata": "BKK", "city": "Bangkok", "lat": 13.6900, "lon": 100.7501},
]


def find_nearest_airport(lat: float, lon: float, max_distance_km: float = 150) -> dict | None:
    """Retourne l'aéroport le plus proche d'un point donné, ou None si trop loin."""

    def _dist(a_lat: float, a_lon: float) -> float:
        r = 6371.0
        p1, p2 = math.radians(lat), math.radians(a_lat)
        dphi = math.radians(a_lat - lat)
        dlmb = math.radians(a_lon - lon)
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
        return r * 2 * math.asin(math.sqrt(a))

    nearest, best_dist = None, max_distance_km
    for airport in AIRPORTS:
        d = _dist(airport["lat"], airport["lon"])
        if d <= best_dist:
            nearest, best_dist = airport, d
    return nearest
