"""
core/transport.py
------------------
Recherche des offres de transport (train, bus, avion) entre deux points
géolocalisés.

Stratégie de données :
  - Avion : si des identifiants Amadeus sont configurés
    (config.USE_REAL_FLIGHT_API), interroge EN TEMPS RÉEL l'API Amadeus
    Flight Offers Search (offre gratuite "self-service" — voir
    https://developers.amadeus.com). En cas d'échec ou d'absence de clé,
    bascule automatiquement sur une simulation réaliste.
  - Train / Bus : il n'existe pas d'API gratuite grand public équivalente
    sans partenariat commercial (SNCF Connect, Trainline Partner API,
    FlixBus/Omio nécessitent un accord fournisseur). Les offres sont donc
    simulées à partir de la distance RÉELLE (calculée via géocodage) et de
    barèmes tarifaires réalistes définis dans config.TRANSPORT_PROFILES.
    → Pour brancher un vrai fournisseur : ajouter une fonction
      fetch_<provider>_offers() sur le modèle de fetch_amadeus_flights()
      ci-dessous, puis l'appeler dans search_transport_offers().
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

import requests
import streamlit as st

from config import (
    AMADEUS_API_KEY,
    AMADEUS_API_SECRET,
    AMADEUS_BASE_URL,
    TRANSPORT_PROFILES,
    USE_REAL_FLIGHT_API,
    N_TRANSPORT_OPTIONS_PER_MODE,
)
from core.geo import GeoPoint
from data.airports import find_nearest_airport


@dataclass
class TransportOffer:
    mode: str                     # "Train", "Bus", "Avion"
    operator: str
    price_eur: float              # prix aller-retour, par voyageur
    duration_min: int             # durée du trajet (un sens), en minutes
    access_time_min: int          # temps d'accès/attente gares-aéroports (aller-retour)
    comfort_score: int            # 0-10
    co2_kg: float                 # émissions estimées, aller-retour, par voyageur
    is_real_data: bool = False    # True si issu d'une vraie API (vs simulation)
    departure_time: str = ""
    details: str = ""


# ---------------------------------------------------------------------------
# Simulation réaliste (train / bus / avion de secours)
# ---------------------------------------------------------------------------

_OPERATORS = {
    "Train": ["TGV inOui", "Ouigo", "Intercités", "Eurostar", "Thalys"],
    "Bus": ["FlixBus", "BlaBlaCar Bus", "Ouibus Connect"],
    "Avion": ["Air France", "easyJet", "Ryanair", "Transavia", "Vueling"],
}

_DEPARTURE_SLOTS = ["06:20", "08:45", "11:10", "14:30", "17:15", "19:50"]


def _simulate_offers_for_mode(mode: str, distance_km: float) -> list[TransportOffer]:
    """Génère plusieurs offres réalistes pour un mode de transport donné."""
    profile = TRANSPORT_PROFILES[mode]
    if distance_km < profile["min_distance_km"]:
        return []

    offers = []
    for _ in range(N_TRANSPORT_OPTIONS_PER_MODE):
        price_variance = random.uniform(0.85, 1.35)
        speed_variance = random.uniform(0.9, 1.1)

        price_one_way = (profile["base_price"] + distance_km * profile["price_per_km"]) * price_variance
        price_round_trip = round(price_one_way * 1.85, 2)  # remise habituelle sur l'aller-retour

        duration_min = int((distance_km / (profile["avg_speed_kmh"] * speed_variance)) * 60)
        duration_min = max(duration_min, 20)

        co2 = round(distance_km * profile["co2_kg_per_km"] * 2, 1)  # aller-retour

        offers.append(
            TransportOffer(
                mode=mode,
                operator=random.choice(_OPERATORS[mode]),
                price_eur=price_round_trip,
                duration_min=duration_min,
                access_time_min=profile["access_time_min"] * 2,
                comfort_score=profile["comfort_score"],
                co2_kg=co2,
                is_real_data=False,
                departure_time=random.choice(_DEPARTURE_SLOTS),
                details="Estimation basée sur la distance réelle et des barèmes "
                        "tarifaires moyens du marché (données simulées).",
            )
        )
    offers.sort(key=lambda o: o.price_eur)
    return offers


# ---------------------------------------------------------------------------
# Vraie API : Amadeus Flight Offers Search
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1500, show_spinner=False)
def _get_amadeus_token() -> Optional[str]:
    """Récupère un jeton OAuth2 Amadeus (client_credentials), mis en cache 25 min."""
    try:
        resp = requests.post(
            f"{AMADEUS_BASE_URL}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": AMADEUS_API_KEY,
                "client_secret": AMADEUS_API_SECRET,
            },
            timeout=8,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except requests.RequestException:
        return None


def _parse_iso_duration(duration: str) -> int:
    """Convertit une durée ISO 8601 simplifiée (ex. 'PT2H15M') en minutes."""
    hours, minutes = 0, 0
    duration = duration.replace("PT", "")
    if "H" in duration:
        hours_part, duration = duration.split("H")
        hours = int(hours_part)
    if "M" in duration:
        minutes = int(duration.replace("M", "") or 0)
    return hours * 60 + minutes


def fetch_amadeus_flights(
    origin: GeoPoint, destination: GeoPoint, departure_date: str
) -> list[TransportOffer]:
    """
    Interroge EN TEMPS RÉEL l'API Amadeus Flight Offers Search.

    Retourne une liste vide (sans lever d'exception) si les aéroports sont
    trop loin, si les clés sont absentes, ou si l'appel échoue : l'appelant
    se rabat alors automatiquement sur la simulation.
    """
    origin_airport = find_nearest_airport(origin.latitude, origin.longitude)
    dest_airport = find_nearest_airport(destination.latitude, destination.longitude)
    if not origin_airport or not dest_airport or origin_airport["iata"] == dest_airport["iata"]:
        return []

    token = _get_amadeus_token()
    if not token:
        return []

    try:
        resp = requests.get(
            f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "originLocationCode": origin_airport["iata"],
                "destinationLocationCode": dest_airport["iata"],
                "departureDate": departure_date,
                "adults": 1,
                "max": 5,
                "currencyCode": "EUR",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except requests.RequestException:
        return []

    offers = []
    for item in data:
        try:
            price = float(item["price"]["grandTotal"])
            itinerary = item["itineraries"][0]
            duration_min = _parse_iso_duration(itinerary["duration"])
            carrier = (
                item["validatingAirlineCodes"][0] if item.get("validatingAirlineCodes") else "Compagnie"
            )
            offers.append(
                TransportOffer(
                    mode="Avion",
                    operator=carrier,
                    price_eur=round(price * 1.85, 2),  # approximation aller-retour
                    duration_min=duration_min,
                    access_time_min=TRANSPORT_PROFILES["Avion"]["access_time_min"] * 2,
                    comfort_score=TRANSPORT_PROFILES["Avion"]["comfort_score"],
                    co2_kg=round((duration_min / 60) * 90, 1),  # approximation grossière
                    is_real_data=True,
                    details="Tarif réel obtenu via l'API Amadeus (environnement de test).",
                )
            )
        except (KeyError, IndexError, ValueError):
            continue
    return offers


# ---------------------------------------------------------------------------
# Point d'entrée public
# ---------------------------------------------------------------------------

def search_transport_offers(
    origin: GeoPoint, destination: GeoPoint, distance_km: float, departure_date: str
) -> tuple[list[TransportOffer], bool]:
    """
    Retourne (liste d'offres tous modes confondus, api_reelle_utilisee).
    Combine données réelles (avion, si disponible) et simulation réaliste
    (train, bus, et avion de secours si l'API réelle est indisponible).
    """
    all_offers: list[TransportOffer] = []
    used_real_api = False

    all_offers += _simulate_offers_for_mode("Train", distance_km)
    all_offers += _simulate_offers_for_mode("Bus", distance_km)

    real_flights: list[TransportOffer] = []
    if USE_REAL_FLIGHT_API and distance_km >= TRANSPORT_PROFILES["Avion"]["min_distance_km"]:
        real_flights = fetch_amadeus_flights(origin, destination, departure_date)

    if real_flights:
        all_offers += real_flights
        used_real_api = True
    else:
        all_offers += _simulate_offers_for_mode("Avion", distance_km)

    return all_offers, used_real_api
