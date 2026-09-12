from __future__ import annotations

from datetime import date
import re
from urllib.parse import urlparse
import requests

from .models import TravelOffer


_EURO_PATTERNS = [
    re.compile(r"(?<!\d)(\d{1,4}(?:[.,]\d{1,2})?)\s*€"),
    re.compile(r"€\s*(\d{1,4}(?:[.,]\d{1,2})?)"),
    re.compile(r"(?<!\d)(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:EUR|euros?)", re.I),
]


class WebSearchClient:
    """
    Recherche web complémentaire via SerpAPI.

    Important :
    - on ne scrape pas directement Airbnb, Trainline, FlixBus, etc.;
    - le prix éventuel est extrait du snippet Google et reste indicatif;
    - seul un prix suffisamment explicite est ajouté aux combinaisons.
    """

    def __init__(self, api_key: str, timeout: int = 20) -> None:
        self.api_key = api_key
        self.timeout = timeout

    def _search(self, query: str, num: int = 10) -> list[dict]:
        response = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google",
                "q": query,
                "api_key": self.api_key,
                "hl": "fr",
                "gl": "fr",
                "num": num,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json().get("organic_results", [])

    def search_accommodations(
        self,
        destination: str,
        check_in: date,
        check_out: date,
        adults: int,
        max_total: float,
    ) -> list[TravelOffer]:
        nights = max(1, (check_out - check_in).days)
        queries = [
            (
                "airbnb",
                f"site:airbnb.fr {destination} {check_in.isoformat()} "
                f"{check_out.isoformat()} {adults} voyageurs prix",
            ),
            (
                "hotel_web",
                f"hôtel {destination} {check_in.isoformat()} {check_out.isoformat()} "
                f"{adults} adulte prix EUR",
            ),
        ]

        output: list[TravelOffer] = []
        for subtype, query in queries:
            for item in self._search(query, num=10):
                title = item.get("title") or "Hébergement"
                snippet = item.get("snippet") or ""
                link = item.get("link")
                extracted = _extract_euro_amount(snippet + " " + title)

                # Un prix de snippet peut être "par nuit". On ne peut pas toujours
                # savoir s'il s'agit du total. On ne l'utilise dans le budget que
                # si le texte contient un marqueur de total/séjour.
                text = (title + " " + snippet).lower()
                is_totalish = any(
                    token in text
                    for token in ["total", "séjour", "pour le séjour", "prix total"]
                )
                price_total = extracted if is_totalish else None

                details = _compact(snippet)
                if extracted is not None and not is_totalish:
                    details = f"{details} · prix vu dans le snippet: {extracted:.2f} € (unité incertaine)"

                output.append(
                    TravelOffer(
                        category="lodging",
                        subtype=subtype,
                        provider=_provider_name(link) or "Résultat web",
                        title=title,
                        price_total=price_total,
                        currency="EUR",
                        url=link,
                        details=details,
                        confidence=0.7 if price_total is not None else 0.45,
                    )
                )
        return output

    def search_ground_transport(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date,
        adults: int,
    ) -> list[TravelOffer]:
        queries = [
            (
                "train",
                f"train {origin} {destination} aller retour {departure_date.isoformat()} "
                f"{return_date.isoformat()} {adults} adulte prix EUR",
            ),
            (
                "bus",
                f"bus {origin} {destination} aller retour {departure_date.isoformat()} "
                f"{return_date.isoformat()} {adults} adulte prix EUR",
            ),
        ]

        output: list[TravelOffer] = []
        for subtype, query in queries:
            for item in self._search(query, num=10):
                title = item.get("title") or subtype.title()
                snippet = item.get("snippet") or ""
                link = item.get("link")
                text = (title + " " + snippet).lower()
                extracted = _extract_euro_amount(title + " " + snippet)

                # Les snippets affichent souvent "à partir de X€" ou un aller simple.
                # On refuse donc de l'injecter dans le budget si le caractère
                # aller-retour / total n'est pas explicite.
                total_markers = ["aller-retour", "aller retour", "a/r", "total"]
                price_total = extracted if any(m in text for m in total_markers) else None

                details = _compact(snippet)
                if extracted is not None and price_total is None:
                    details = f"{details} · tarif aperçu: {extracted:.2f} € (total non garanti)"

                output.append(
                    TravelOffer(
                        category="transport",
                        subtype=subtype,
                        provider=_provider_name(link) or "Résultat web",
                        title=title,
                        price_total=price_total,
                        currency="EUR",
                        url=link,
                        details=details,
                        confidence=0.68 if price_total is not None else 0.4,
                    )
                )

        return output


def _extract_euro_amount(text: str) -> float | None:
    candidates: list[float] = []
    for pattern in _EURO_PATTERNS:
        for match in pattern.findall(text):
            try:
                value = float(match.replace(",", "."))
            except ValueError:
                continue
            if 1 <= value <= 10000:
                candidates.append(value)
    return min(candidates) if candidates else None


def _provider_name(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        return host or None
    except Exception:
        return None


def _compact(text: str, max_len: int = 240) -> str:
    text = " ".join(text.split())
    return text if len(text) <= max_len else text[: max_len - 1] + "…"
