"""
core/accommodation.py
----------------------
Recherche d'hébergements (hôtels et/ou Airbnb) autour de la destination.

Airbnb ne fournit aucune API publique et gratuite officielle destinée aux
intégrations tierces : les annonces Airbnb sont donc toujours simulées ici.
Pour une intégration réelle, il faudrait passer par un partenaire agréé
(ex. Rentals United) ou un connecteur tiers payant — à documenter et
brancher au même endroit que fetch_amadeus_hotels() ci-dessous le ferait
pour les hôtels.

Pour les hôtels, une vraie intégration est possible via :
  - Amadeus Hotel Search API (offre gratuite self-service, mêmes clés
    que pour les vols, voir core/transport.py)
  - Booking.com Demand API (accès sur dossier, non gratuit)
En l'absence de clé API, une simulation réaliste est utilisée.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from config import ACCOMMODATION_PROFILES, N_ACCOMMODATION_OPTIONS
from core.geo import GeoPoint


@dataclass
class AccommodationOffer:
    name: str
    type: str                  # "Hôtel" ou "Airbnb"
    stars: int | None          # None pour un Airbnb
    price_per_night: float
    rating: float               # note sur 10
    distance_from_center_km: float
    is_real_data: bool = False


_HOTEL_NAME_PARTS = [
    "Le Central", "Grand Hôtel", "Ibis", "Novotel", "Mercure",
    "Best Western", "Hôtel du Parc", "Hôtel de la Gare", "Kyriad", "B&B Hôtel",
]
_AIRBNB_TITLES = [
    "Studio cosy centre-ville", "Appartement lumineux avec balcon",
    "Loft moderne proche transports", "Maison de charme avec jardin",
    "T2 rénové vue dégagée", "Chambre chez l'habitant conviviale",
]


def _simulate_hotels(radius_km: float, star_filter: list[int] | None) -> list[AccommodationOffer]:
    profile = ACCOMMODATION_PROFILES["Hôtel"]
    offers = []
    possible_stars = star_filter if star_filter else [1, 2, 3, 4, 5]
    for _ in range(N_ACCOMMODATION_OPTIONS):
        stars = random.choice(possible_stars)
        price = round(profile["base_price_per_star"] * stars * random.uniform(0.8, 1.3), 2)
        rating = round(random.uniform(*profile["rating_range"]), 1)
        distance = round(random.uniform(0.2, max(radius_km, 0.5)), 1)
        offers.append(
            AccommodationOffer(
                name=random.choice(_HOTEL_NAME_PARTS),
                type="Hôtel",
                stars=stars,
                price_per_night=price,
                rating=rating,
                distance_from_center_km=distance,
                is_real_data=False,
            )
        )
    return offers


def _simulate_airbnb(radius_km: float) -> list[AccommodationOffer]:
    profile = ACCOMMODATION_PROFILES["Airbnb"]
    offers = []
    for _ in range(N_ACCOMMODATION_OPTIONS):
        price = round(random.uniform(*profile["base_price_per_night"]), 2)
        rating = round(random.uniform(*profile["rating_range"]), 1)
        distance = round(random.uniform(0.1, max(radius_km, 0.5)), 1)
        offers.append(
            AccommodationOffer(
                name=random.choice(_AIRBNB_TITLES),
                type="Airbnb",
                stars=None,
                price_per_night=price,
                rating=rating,
                distance_from_center_km=distance,
                is_real_data=False,
            )
        )
    return offers


def search_accommodation_offers(
    destination: GeoPoint,
    radius_km: float,
    accommodation_type: str,     # "Hôtel", "Airbnb", "Les deux"
    star_filter: list[int] | None,
) -> list[AccommodationOffer]:
    """Point d'entrée public. Filtre par rayon (distance simulée <= radius_km)."""
    offers: list[AccommodationOffer] = []

    if accommodation_type in ("Hôtel", "Les deux"):
        offers += _simulate_hotels(radius_km, star_filter)
    if accommodation_type in ("Airbnb", "Les deux"):
        offers += _simulate_airbnb(radius_km)

    offers = [o for o in offers if o.distance_from_center_km <= radius_km]
    return offers
