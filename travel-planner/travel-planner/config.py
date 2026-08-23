"""
config.py
----------
Configuration centrale de l'application : constantes métier, paramètres
de tarification/temps de trajet par mode de transport, facteurs
d'émission CO2, endpoints des APIs externes et accès sécurisé aux clés
API (via st.secrets sur Streamlit Cloud, ou variables d'environnement
en local).

C'est le SEUL fichier à modifier pour ajuster les hypothèses tarifaires
ou brancher de nouvelles clés API.
"""

import os
import streamlit as st

# ---------------------------------------------------------------------------
# Informations générales de l'application
# ---------------------------------------------------------------------------
APP_TITLE = "TripSense — Comparateur intelligent de voyages"
APP_ICON = "🧭"

# ---------------------------------------------------------------------------
# Accès sécurisé aux clés API
# ---------------------------------------------------------------------------
# Sur Streamlit Community Cloud : Settings > Secrets, coller un TOML du type :
#   AMADEUS_API_KEY = "xxxx"
#   AMADEUS_API_SECRET = "xxxx"
# En local : copier .streamlit/secrets.toml.example vers
# .streamlit/secrets.toml, ou définir des variables d'environnement du
# même nom.


def get_secret(name: str, default: str = "") -> str:
    """Récupère une clé API depuis st.secrets, sinon depuis l'environnement."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name, default)


AMADEUS_API_KEY = get_secret("AMADEUS_API_KEY")
AMADEUS_API_SECRET = get_secret("AMADEUS_API_SECRET")
AMADEUS_BASE_URL = "https://test.api.amadeus.com"  # environnement gratuit "test"

# Active automatiquement les appels réels à Amadeus si des clés sont fournies.
USE_REAL_FLIGHT_API = bool(AMADEUS_API_KEY and AMADEUS_API_SECRET)

# Géocodage (OpenStreetMap Nominatim) — gratuit, sans clé, usage raisonnable requis.
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "TripSense-TravelPlanner/1.0 (contact: demo@example.com)"

# ---------------------------------------------------------------------------
# Hypothèses tarifaires / vitesses par mode de transport (simulation réaliste)
# À REMPLACER par de vrais fournisseurs quand disponibles :
#   - Train : SNCF Connect API / Trainline Partner API / Omio API
#   - Bus   : FlixBus API / Omio API
#   - Avion : Amadeus Flight Offers Search (déjà branché, voir core/transport.py)
# ---------------------------------------------------------------------------
TRANSPORT_PROFILES = {
    "Train": {
        "avg_speed_kmh": 160,
        "price_per_km": 0.11,
        "base_price": 8,
        "access_time_min": 25,   # temps moyen pour rejoindre/quitter une gare
        "comfort_score": 8,      # sur 10
        "co2_kg_per_km": 0.005,  # source indicative : ADEME Base Carbone (train électrique FR)
        "min_distance_km": 0,
    },
    "Bus": {
        "avg_speed_kmh": 80,
        "price_per_km": 0.045,
        "base_price": 5,
        "access_time_min": 15,
        "comfort_score": 5,
        "co2_kg_per_km": 0.03,   # source indicative : ADEME Base Carbone (autocar)
        "min_distance_km": 0,
    },
    "Avion": {
        "avg_speed_kmh": 700,
        "price_per_km": 0.09,
        "base_price": 40,
        "access_time_min": 120,  # enregistrement + sécurité + accès aéroport
        "comfort_score": 7,
        "co2_kg_per_km": 0.20,   # source indicative : ADEME Base Carbone (court/moyen-courrier)
        "min_distance_km": 300,  # l'avion n'est proposé qu'au-delà de cette distance
    },
}

# ---------------------------------------------------------------------------
# Hypothèses hébergement (simulation réaliste)
# À REMPLACER par : Amadeus Hotel Search API, Booking.com Demand API,
# ou pour Airbnb (pas d'API publique officielle) : Rentals United, ou un
# connecteur tiers non-officiel type RapidAPI "Airbnb Search" (payant).
# ---------------------------------------------------------------------------
ACCOMMODATION_PROFILES = {
    "Hôtel": {
        "base_price_per_star": 28,  # €/nuit par étoile, modulé ensuite
        "rating_range": (6.0, 9.7),
    },
    "Airbnb": {
        "base_price_per_night": (35, 140),
        "rating_range": (6.5, 9.9),
    },
}

# Nombre d'options générées par recherche (pour la simulation)
N_TRANSPORT_OPTIONS_PER_MODE = 3
N_ACCOMMODATION_OPTIONS = 10

# Pondération du score qualité-prix global (doit sommer à 1.0)
SCORE_WEIGHTS = {
    "price": 0.35,
    "duration": 0.25,
    "comfort": 0.20,
    "eco": 0.20,
}
