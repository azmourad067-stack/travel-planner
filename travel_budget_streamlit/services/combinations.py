from __future__ import annotations

from dataclasses import dataclass
from .models import TravelOffer


@dataclass(slots=True)
class BudgetCombination:
    transport: TravelOffer
    lodging: TravelOffer
    total_price: float
    remaining_budget: float
    confidence: str


def build_budget_combinations(
    transport_offers: list[TravelOffer],
    lodging_offers: list[TravelOffer],
    max_budget: float,
    limit: int = 25,
) -> list[BudgetCombination]:
    combos: list[BudgetCombination] = []

    priced_transports = [x for x in transport_offers if x.price_total is not None]
    priced_lodgings = [x for x in lodging_offers if x.price_total is not None]

    for transport in priced_transports:
        for lodging in priced_lodgings:
            total = float(transport.price_total) + float(lodging.price_total)
            if total <= max_budget:
                min_conf = min(transport.confidence, lodging.confidence)
                if min_conf >= 0.9:
                    confidence = "élevée"
                elif min_conf >= 0.65:
                    confidence = "moyenne"
                else:
                    confidence = "faible"

                combos.append(
                    BudgetCombination(
                        transport=transport,
                        lodging=lodging,
                        total_price=total,
                        remaining_budget=max_budget - total,
                        confidence=confidence,
                    )
                )

    # Priorité au coût, puis à la confiance.
    combos.sort(
        key=lambda x: (
            x.total_price,
            -(min(x.transport.confidence, x.lodging.confidence)),
        )
    )
    return combos[:limit]
