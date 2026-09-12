from __future__ import annotations

from datetime import date
from typing import Any
import time
import requests

from .models import TravelOffer


class AmadeusError(RuntimeError):
    pass


class AmadeusClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str = "https://test.api.amadeus.com",
        timeout: int = 20,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._token: str | None = None
        self._token_expires_at = 0.0

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 30:
            return self._token

        response = requests.post(
            f"{self.base_url}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=self.timeout,
        )
        if not response.ok:
            raise AmadeusError(
                f"authentification impossible ({response.status_code})"
            )

        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires_at = time.time() + int(payload.get("expires_in", 1800))
        return self._token

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}{path}",
            params=params,
            headers={"Authorization": f"Bearer {self._get_token()}"},
            timeout=self.timeout,
        )
        if response.status_code == 429:
            raise AmadeusError("quota API dépassé, réessaie plus tard")
        if not response.ok:
            try:
                data = response.json()
                detail = data.get("errors", [{}])[0].get("detail")
            except Exception:
                detail = None
            raise AmadeusError(
                detail or f"requête refusée ({response.status_code})"
            )
        return response.json()

    def find_location(self, keyword: str) -> dict[str, Any] | None:
        payload = self._get(
            "/v1/reference-data/locations",
            {
                "subType": "CITY,AIRPORT",
                "keyword": keyword,
                "page[limit]": 10,
                "view": "LIGHT",
            },
        )
        items = payload.get("data", [])
        if not items:
            return None

        # Priorité à une ville portant le nom demandé, sinon premier résultat.
        normalized = keyword.strip().casefold()
        items.sort(
            key=lambda x: (
                0 if x.get("name", "").casefold() == normalized else 1,
                0 if x.get("subType") == "CITY" else 1,
            )
        )
        return items[0]

    def search_flights(
        self,
        origin_code: str,
        destination_code: str,
        departure_date: date,
        return_date: date,
        adults: int,
        max_price: float,
        limit: int = 20,
    ) -> list[TravelOffer]:
        payload = self._get(
            "/v2/shopping/flight-offers",
            {
                "originLocationCode": origin_code,
                "destinationLocationCode": destination_code,
                "departureDate": departure_date.isoformat(),
                "returnDate": return_date.isoformat(),
                "adults": adults,
                "currencyCode": "EUR",
                "maxPrice": int(max_price),
                "max": limit,
            },
        )

        dictionaries = payload.get("dictionaries", {})
        carriers = dictionaries.get("carriers", {})
        offers: list[TravelOffer] = []

        for row in payload.get("data", []):
            price = row.get("price", {})
            total = _to_float(price.get("grandTotal") or price.get("total"))
            if total is None:
                continue

            itineraries = row.get("itineraries", [])
            carrier_codes = []
            stops = 0
            for itinerary in itineraries:
                segments = itinerary.get("segments", [])
                stops += max(0, len(segments) - 1)
                for segment in segments:
                    code = segment.get("carrierCode")
                    if code and code not in carrier_codes:
                        carrier_codes.append(code)

            carrier_names = [carriers.get(code, code) for code in carrier_codes]
            provider = ", ".join(carrier_names) if carrier_names else "Compagnie aérienne"
            details = (
                f"aller-retour · {stops} correspondance(s) au total · "
                f"{' / '.join(carrier_codes) if carrier_codes else 'compagnie non précisée'}"
            )

            offers.append(
                TravelOffer(
                    category="transport",
                    subtype="flight",
                    provider=provider,
                    title=f"Vol {origin_code} ↔ {destination_code}",
                    price_total=total,
                    currency=price.get("currency", "EUR"),
                    url=None,
                    details=details,
                    confidence=1.0,
                )
            )

        return sorted(offers, key=lambda x: x.price_total or 10**9)

    def search_hotels(
        self,
        city_code: str,
        check_in: date,
        check_out: date,
        adults: int,
        max_total: float,
        hotel_limit: int = 35,
        chunk_size: int = 15,
    ) -> list[TravelOffer]:
        hotel_list = self._get(
            "/v1/reference-data/locations/hotels/by-city",
            {
                "cityCode": city_code,
                "radius": 20,
                "radiusUnit": "KM",
                "hotelSource": "ALL",
            },
        )
        hotels = hotel_list.get("data", [])[:hotel_limit]
        if not hotels:
            return []

        name_by_id = {
            h.get("hotelId"): h.get("name", h.get("hotelId", "Hôtel"))
            for h in hotels
            if h.get("hotelId")
        }
        hotel_ids = list(name_by_id)

        results: list[TravelOffer] = []

        # L'API hotel-offers accepte plusieurs hotelIds. On segmente pour
        # éviter les URL trop longues et limiter les erreurs.
        for i in range(0, len(hotel_ids), chunk_size):
            chunk = hotel_ids[i : i + chunk_size]
            try:
                payload = self._get(
                    "/v3/shopping/hotel-offers",
                    {
                        "hotelIds": ",".join(chunk),
                        "adults": adults,
                        "checkInDate": check_in.isoformat(),
                        "checkOutDate": check_out.isoformat(),
                        "roomQuantity": 1,
                        "currency": "EUR",
                        "bestRateOnly": "true",
                    },
                )
            except AmadeusError:
                continue

            for item in payload.get("data", []):
                hotel = item.get("hotel", {})
                hotel_id = hotel.get("hotelId")
                hotel_name = hotel.get("name") or name_by_id.get(hotel_id, "Hôtel")
                for offer in item.get("offers", [])[:1]:
                    price = offer.get("price", {})
                    total = _to_float(price.get("total"))
                    if total is None or total > max_total:
                        continue

                    room = offer.get("room", {})
                    room_desc = (
                        room.get("description", {}).get("text")
                        or room.get("typeEstimated", {}).get("category")
                        or "chambre"
                    )
                    results.append(
                        TravelOffer(
                            category="lodging",
                            subtype="hotel",
                            provider="Amadeus",
                            title=hotel_name,
                            price_total=total,
                            currency=price.get("currency", "EUR"),
                            url=None,
                            details=room_desc[:180],
                            confidence=1.0,
                        )
                    )

        return sorted(results, key=lambda x: x.price_total or 10**9)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
