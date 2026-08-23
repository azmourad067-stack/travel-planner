"""
core/geo.py
-----------
Géolocalisation EN TEMPS RÉEL des villes via l'API publique et gratuite
OpenStreetMap Nominatim (aucune clé requise), et calcul de distances
géographiques réelles (formule de haversine). Toute la logique de
"où sont les villes et quelle distance les sépare" vit ici,
indépendamment du reste de l'application.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import requests
import streamlit as st

from config import NOMINATIM_URL, NOMINATIM_USER_AGENT
from core.exceptions import GeocodingError


@dataclass
class GeoPoint:
    name: str
    latitude: float
    longitude: float
    display_name: str


@st.cache_data(ttl=3600, show_spinner=False)
def geocode_city(city_name: str) -> GeoPoint:
    """
    Géolocalise une ville via l'API Nominatim (OpenStreetMap) en temps réel.

    Lève GeocodingError si la ville est introuvable ou en cas de panne API.
    Le résultat est mis en cache 1h (par nom de ville) pour éviter de
    solliciter inutilement l'API en cas de recherches répétées.
    """
    if not city_name or not city_name.strip():
        raise GeocodingError("Le nom de ville est vide.")

    params = {"q": city_name.strip(), "format": "json", "limit": 1}
    headers = {"User-Agent": NOMINATIM_USER_AGENT}

    try:
        response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=8)
        response.raise_for_status()
        results = response.json()
    except requests.RequestException as exc:
        raise GeocodingError(
            f"Impossible de contacter le service de géolocalisation pour « {city_name} ». "
            "Vérifiez votre connexion et réessayez."
        ) from exc

    if not results:
        raise GeocodingError(
            f"Impossible de localiser « {city_name} ». Vérifiez l'orthographe "
            "ou essayez un nom plus précis (ex. « Lyon, France »)."
        )

    top = results[0]
    return GeoPoint(
        name=city_name,
        latitude=float(top["lat"]),
        longitude=float(top["lon"]),
        display_name=top.get("display_name", city_name),
    )


def haversine_distance_km(point_a: GeoPoint, point_b: GeoPoint) -> float:
    """Distance orthodromique (à vol d'oiseau) entre deux points, en kilomètres."""
    r = 6371.0  # rayon moyen de la Terre, en km
    lat1, lon1 = math.radians(point_a.latitude), math.radians(point_a.longitude)
    lat2, lon2 = math.radians(point_b.latitude), math.radians(point_b.longitude)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))
