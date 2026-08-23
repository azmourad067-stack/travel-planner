"""
core/combiner.py
------------------
Combine les offres de transport et d'hébergement en "packages" complets,
calcule leur coût et leur durée totale porte-à-porte, et filtre selon le
budget (cible +/- tolérance) fourni par l'utilisateur.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from core.accommodation import AccommodationOffer
from core.transport import TransportOffer


@dataclass
class TravelPackage:
    transport: TransportOffer
    accommodation: AccommodationOffer
    travelers: int
    nights: int
    total_price: float = 0.0
    total_duration_min: int = 0       # durée porte-à-porte, un sens (trajet + accès)
    total_co2_kg: float = 0.0
    comfort_score: float = 0.0
    score: float = 0.0
    badges: list[str] = field(default_factory=list)

    def __post_init__(self):
        rooms = math.ceil(self.travelers / 2)  # hypothèse : 2 voyageurs / chambre
        transport_total = self.transport.price_eur * self.travelers
        accommodation_total = self.accommodation.price_per_night * self.nights * rooms
        self.total_price = round(transport_total + accommodation_total, 2)
        self.total_duration_min = self.transport.duration_min + self.transport.access_time_min
        self.total_co2_kg = round(self.transport.co2_kg * self.travelers, 1)
        self.comfort_score = (self.transport.comfort_score + self.accommodation.rating) / 2


def build_packages(
    transport_offers: list[TransportOffer],
    accommodation_offers: list[AccommodationOffer],
    travelers: int,
    nights: int,
    budget_min: float,
    budget_max: float,
) -> tuple[list[TravelPackage], float]:
    """
    Construit toutes les combinaisons transport x hébergement, et ne garde
    que celles dont le prix total tombe dans [budget_min, budget_max].

    Retourne aussi le prix minimal trouvé toutes combinaisons confondues,
    utile pour aider l'utilisateur si aucun résultat n'entre dans le budget.
    """
    all_packages = [
        TravelPackage(transport=t, accommodation=a, travelers=travelers, nights=nights)
        for t in transport_offers
        for a in accommodation_offers
    ]

    if not all_packages:
        return [], 0.0

    cheapest_overall = min(p.total_price for p in all_packages)
    within_budget = [p for p in all_packages if budget_min <= p.total_price <= budget_max]

    return within_budget, cheapest_overall
