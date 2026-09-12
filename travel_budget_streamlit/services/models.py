from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TravelOffer:
    category: str  # "transport" | "lodging"
    subtype: str   # flight, hotel, airbnb, train, bus...
    provider: str
    title: str
    price_total: float | None
    currency: str = "EUR"
    url: str | None = None
    details: str = ""
    confidence: float = 1.0

    @property
    def confidence_label(self) -> str:
        if self.confidence >= 0.9:
            return "prix structuré"
        if self.confidence >= 0.65:
            return "prix indicatif"
        return "à vérifier"
