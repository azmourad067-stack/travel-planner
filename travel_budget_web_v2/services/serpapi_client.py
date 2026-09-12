from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlparse
import re
import requests

from .models import TravelOffer


class SerpApiError(RuntimeError):
    pass


class SerpApiClient:
    BASE_URL = "https://serpapi.com/search.json"
    ACCOUNT_URL = "https://serpapi.com/account.json"

    def __init__(self, api_key: str, timeout: int = 30) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()

    def _request(self, engine: str, **params: Any) -> dict[str, Any]:
        payload = {
            "engine": engine,
            "api_key": self.api_key,
            **params,
        }
        try:
            response = self.session.get(
                self.BASE_URL,
                params=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise SerpApiError(f"connexion impossible : {exc}") from exc

        if response.status_code == 401:
            raise SerpApiError("clé SERPAPI_KEY invalide")
        if response.status_code == 429:
            raise SerpApiError("quota SerpAPI dépassé")
        if not response.ok:
            raise SerpApiError(f"requête SerpAPI refusée ({response.status_code})")

        try:
            data = response.json()
        except ValueError as exc:
            raise SerpApiError("réponse SerpAPI non JSON") from exc

        if data.get("error"):
            raise SerpApiError(str(data["error"]))

        return data

    def account_status(self) -> dict[str, Any]:
        """
        Vérifie gratuitement la clé et retourne les informations de quota.
        L'Account API SerpAPI n'est pas comptée dans le quota de recherche.
        """
        try:
            response = self.session.get(
                self.ACCOUNT_URL,
                params={"api_key": self.api_key},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise SerpApiError(f"connexion impossible : {exc}") from exc

        if response.status_code in (401, 403):
            raise SerpApiError("clé SERPAPI_KEY invalide")
        if not response.ok:
            raise SerpApiError(f"vérification impossible ({response.status_code})")

        data = response.json()
        if data.get("error"):
            raise SerpApiError(str(data["error"]))
        return data

    def resolve_flight_location(self, city: str) -> dict[str, Any] | None:
        """
        Transforme une ville libre ('Paris', 'Rome'...) en identifiant Google Flights
        (kgmid) et récupère aussi les aéroports IATA associés.
        """
        data = self._request(
            "google_flights_autocomplete",
            q=city,
            hl="fr",
            gl="fr",
            exclude_regions="true",
        )
        suggestions = data.get("suggestions") or []
        if not suggestions:
            return None

        wanted = city.strip().casefold()

        def score(item: dict[str, Any]) -> tuple[int, int]:
            name = str(item.get("name", "")).casefold()
            exact = 0 if name == wanted or name.startswith(wanted + ",") else 1
            city_type = 0 if item.get("type") == "city" else 1
            return (exact, city_type)

        suggestions = sorted(suggestions, key=score)
        best = suggestions[0]

        airports = [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "city": a.get("city"),
            }
            for a in (best.get("airports") or [])
            if a.get("id")
        ]

        return {
            "name": best.get("name") or city,
            "id": best.get("id"),
            "description": best.get("description", ""),
            "airports": airports,
        }

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date,
        adults: int,
        max_budget: float | None = None,
    ) -> tuple[list[TravelOffer], dict[str, Any], dict[str, Any]]:
        origin_loc = self.resolve_flight_location(origin)
        destination_loc = self.resolve_flight_location(destination)

        if not origin_loc:
            raise SerpApiError(f"ville de départ introuvable : {origin}")
        if not destination_loc:
            raise SerpApiError(f"destination introuvable : {destination}")
        if not origin_loc.get("id"):
            raise SerpApiError(f"aucun identifiant Google Flights pour {origin}")
        if not destination_loc.get("id"):
            raise SerpApiError(f"aucun identifiant Google Flights pour {destination}")

        data = self._request(
            "google_flights",
            departure_id=origin_loc["id"],
            arrival_id=destination_loc["id"],
            outbound_date=departure_date.isoformat(),
            return_date=return_date.isoformat(),
            adults=adults,
            type=1,
            travel_class=1,
            currency="EUR",
            hl="fr",
            gl="fr",
        )

        rows = (data.get("best_flights") or []) + (data.get("other_flights") or [])
        offers: list[TravelOffer] = []

        for row in rows:
            price = _to_float(row.get("price"))
            if price is None:
                continue
            if max_budget is not None and price > max_budget:
                continue

            flights = row.get("flights") or []
            airline_names: list[str] = []
            segments: list[str] = []

            for flight in flights:
                airline = flight.get("airline")
                if airline and airline not in airline_names:
                    airline_names.append(str(airline))

                dep = flight.get("departure_airport") or {}
                arr = flight.get("arrival_airport") or {}
                dep_id = dep.get("id", "?")
                arr_id = arr.get("id", "?")
                segments.append(f"{dep_id}→{arr_id}")

            layovers = row.get("layovers") or []
            total_duration = row.get("total_duration")
            emissions = (row.get("carbon_emissions") or {}).get("this_flight")

            detail_parts = []
            if segments:
                detail_parts.append(" · ".join(segments))
            if total_duration:
                detail_parts.append(f"{_format_minutes(total_duration)}")
            if layovers:
                detail_parts.append(f"{len(layovers)} escale(s)")
            else:
                detail_parts.append("direct ou sans escale listée")
            if emissions:
                detail_parts.append(f"CO₂ {emissions} g")

            offers.append(
                TravelOffer(
                    category="transport",
                    subtype="flight",
                    provider=", ".join(airline_names) if airline_names else "Google Flights",
                    title=f"Vol {origin_loc['name']} ↔ {destination_loc['name']}",
                    price_total=price,
                    currency="EUR",
                    url=None,
                    details=" · ".join(detail_parts),
                    confidence=0.95,
                )
            )

        return (
            _dedupe_offers(sorted(offers, key=lambda x: x.price_total or 10**9)),
            origin_loc,
            destination_loc,
        )

    def search_hotels(
        self,
        destination: str,
        check_in: date,
        check_out: date,
        adults: int,
        max_budget: float | None = None,
        vacation_rentals: bool = False,
    ) -> list[TravelOffer]:
        params: dict[str, Any] = {
            "q": destination,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "adults": adults,
            "children": 0,
            "currency": "EUR",
            "hl": "fr",
            "gl": "fr",
        }
        if vacation_rentals:
            params["vacation_rentals"] = "true"

        data = self._request("google_hotels", **params)
        properties = data.get("properties") or []
        nights = max(1, (check_out - check_in).days)

        offers: list[TravelOffer] = []
        for prop in properties:
            total_rate = prop.get("total_rate") or {}
            nightly_rate = prop.get("rate_per_night") or {}

            total = _to_float(total_rate.get("extracted_lowest"))
            confidence = 0.95

            if total is None:
                nightly = _to_float(nightly_rate.get("extracted_lowest"))
                if nightly is not None:
                    total = nightly * nights
                    confidence = 0.85

            if total is None:
                continue
            if max_budget is not None and total > max_budget:
                continue

            ptype = str(prop.get("type") or "").lower()
            subtype = (
                "vacation_rental"
                if vacation_rentals or "vacation" in ptype
                else "hotel"
            )

            price_sources = prop.get("prices") or []
            provider = "Google Hotels"
            direct_url = None
            if price_sources:
                provider = price_sources[0].get("source") or provider
                direct_url = price_sources[0].get("link")

            rating = prop.get("overall_rating")
            reviews = prop.get("reviews")
            hotel_class = prop.get("hotel_class")
            amenities = prop.get("amenities") or []
            essential = prop.get("essential_info") or []

            detail_parts = []
            if hotel_class:
                detail_parts.append(f"{hotel_class}★")
            if rating:
                rating_text = f"note {rating}/5"
                if reviews:
                    rating_text += f" ({reviews} avis)"
                detail_parts.append(rating_text)
            if essential:
                detail_parts.extend(str(x) for x in essential[:2])
            elif amenities:
                detail_parts.append(", ".join(str(x) for x in amenities[:3]))

            offers.append(
                TravelOffer(
                    category="lodging",
                    subtype=subtype,
                    provider=str(provider),
                    title=prop.get("name") or "Hébergement",
                    price_total=total,
                    currency="EUR",
                    url=direct_url,
                    details=" · ".join(detail_parts) or f"{nights} nuit(s)",
                    confidence=confidence,
                )
            )

        return _dedupe_offers(sorted(offers, key=lambda x: x.price_total or 10**9))

    def search_airbnb_links(
        self,
        destination: str,
        check_in: date,
        check_out: date,
        adults: int,
    ) -> list[TravelOffer]:
        query = (
            f'site:airbnb.fr "{destination}" '
            f'{check_in.isoformat()} {check_out.isoformat()} '
            f'{adults} voyageurs'
        )
        data = self._request(
            "google",
            q=query,
            hl="fr",
            gl="fr",
            num=10,
        )
        offers: list[TravelOffer] = []
        for item in data.get("organic_results") or []:
            title = item.get("title") or "Airbnb"
            snippet = item.get("snippet") or ""
            link = item.get("link")
            amount = _extract_euro_amount(f"{title} {snippet}")

            # Un snippet Airbnb n'est pas assez fiable pour considérer le prix
            # comme total de séjour. On l'affiche mais on ne l'utilise pas dans
            # le moteur de budget.
            details = _compact(snippet)
            if amount is not None:
                details += f" · tarif aperçu : {amount:.2f} € (unité à vérifier)"

            offers.append(
                TravelOffer(
                    category="lodging",
                    subtype="airbnb",
                    provider=_provider_name(link) or "Airbnb",
                    title=title,
                    price_total=None,
                    currency="EUR",
                    url=link,
                    details=details,
                    confidence=0.45,
                )
            )
        return offers

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
                f"train {origin} {destination} aller retour "
                f"{departure_date.isoformat()} {return_date.isoformat()} "
                f"{adults} adulte prix EUR",
            ),
            (
                "bus",
                f"bus {origin} {destination} aller retour "
                f"{departure_date.isoformat()} {return_date.isoformat()} "
                f"{adults} adulte prix EUR",
            ),
        ]

        output: list[TravelOffer] = []
        for subtype, query in queries:
            data = self._request(
                "google",
                q=query,
                hl="fr",
                gl="fr",
                num=10,
            )
            for item in data.get("organic_results") or []:
                title = item.get("title") or subtype.title()
                snippet = item.get("snippet") or ""
                link = item.get("link")
                text = (title + " " + snippet).lower()
                extracted = _extract_euro_amount(title + " " + snippet)

                # On n'intègre le prix dans le budget que si le snippet indique
                # clairement un total / aller-retour. Sinon il reste indicatif.
                total_markers = [
                    "aller-retour",
                    "aller retour",
                    "a/r",
                    "prix total",
                    "total",
                ]
                price_total = (
                    extracted
                    if extracted is not None and any(m in text for m in total_markers)
                    else None
                )

                details = _compact(snippet)
                if extracted is not None and price_total is None:
                    details += f" · tarif aperçu : {extracted:.2f} € (total non garanti)"

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

        return _dedupe_offers(output)


_EURO_PATTERNS = [
    re.compile(r"(?<!\d)(\d{1,5}(?:[.,]\d{1,2})?)\s*€"),
    re.compile(r"€\s*(\d{1,5}(?:[.,]\d{1,2})?)"),
    re.compile(r"(?<!\d)(\d{1,5}(?:[.,]\d{1,2})?)\s*(?:EUR|euros?)", re.I),
]


def _extract_euro_amount(text: str) -> float | None:
    candidates: list[float] = []
    for pattern in _EURO_PATTERNS:
        for match in pattern.findall(text):
            try:
                value = float(match.replace(",", "."))
            except ValueError:
                continue
            if 1 <= value <= 50000:
                candidates.append(value)
    return min(candidates) if candidates else None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace("€", "").replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _format_minutes(value: Any) -> str:
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return str(value)
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h} h {m:02d}"
    if h:
        return f"{h} h"
    return f"{m} min"


def _provider_name(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return urlparse(url).netloc.lower().removeprefix("www.") or None
    except Exception:
        return None


def _compact(text: str, max_len: int = 240) -> str:
    text = " ".join(str(text).split())
    if not text:
        return "Informations à vérifier sur le site source."
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def _dedupe_offers(items: list[TravelOffer]) -> list[TravelOffer]:
    seen: set[tuple[Any, ...]] = set()
    out: list[TravelOffer] = []
    for item in items:
        key = (
            item.category,
            item.subtype,
            item.provider.casefold(),
            item.title.casefold(),
            round(item.price_total or -1, 2),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
