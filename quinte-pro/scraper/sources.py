"""Adaptateurs de sources hippiques.

Regle de fiabilite (verifiee a la conception de ce projet) :
- AUCUNE API publique officielle n'existe cote PMU / France Galop / LeTrot /
  Geny / Paris-Turf. Les donnees y sont accessibles via leurs sites web,
  proteges par anti-bot et soumis a des conditions d'utilisation.
- open-pmu-api (https://github.com/nanaelie/open-pmu-api) est une API REST
  open source non officielle, gratuite, que l'on peut auto-heberger
  (les arrivees detaillees : cheval, driver, gains, musique, cotes...).
- Chaque adaptateur est donc : *disponible* (actif) ou *desactive* par defaut
  avec un message explicite. Un echec ne fait JAMAIS planter le pronostic :
  le modele tourne sur les donnees de saisie, enrichies si possible.
"""
from __future__ import annotations

import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field

from scraper.base import PoliteFetcher

logger = logging.getLogger("quinte.sources")

_SEARCH_ENABLED = os.getenv("QUINTE_SEARCH_ENABLED", "1") == "1"
_SEARCH_MAX_PER_RACE = int(os.getenv("QUINTE_SEARCH_MAX_PER_RACE", "16"))
_SEARCH_DELAY_S = float(os.getenv("QUINTE_SEARCH_DELAY_S", "1.2"))
_OPENPMU_URL = os.getenv("OPEN_PMU_API_URL", "").strip()  # ex: http://localhost:8000


def normalize_name(name: str | None) -> str:
    """Normalise un nom (cheval/driver) pour rapprochement multi-sources."""
    if not name:
        return ""
    s = unicodedata.normalize("NFD", str(name).upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip()


# ----------------------------------------------------------------------
# 1) open-pmu-api (auto-hebergable, sources des arrivees PMU)
# ----------------------------------------------------------------------
class OpenPMUAPI:
    """Adaptateur vers une instance open-pmu-api.

    Desactive tant que OPEN_PMU_API_URL n'est pas defini (variable d'env
    ou secret Streamlit). Methode : GET {base}/arrivees?date=DD/MM/YYYY
    filtrable par hippodrome ; les partants arrives sont identifies par
    nom de cheval normalise.
    """

    name = "open-pmu-api"

    def __init__(self, fetcher: PoliteFetcher | None = None):
        self.fetcher = fetcher or PoliteFetcher(timeout=6, retries=1)
        self.base_url = _OPENPMU_URL
        self.active = bool(self.base_url)

    def fetch_race(self, race: dict) -> tuple[dict | None, str]:
        """Retourne (payload normalise par partant, message d'etat)."""
        if not self.active:
            return None, "inactif (variable OPEN_PMU_API_URL non definie)"
        date = race.get("date", "")
        if not date:
            return None, "date de course requise pour interroger open-pmu-api"
        try:
            jour, mois, annee = date.split("/")
            _ = (int(jour), int(mois), int(annee))
        except ValueError:
            return None, f"date invalide: {date!r} (format attendu JJ/MM/AAAA)"
        res = self.fetcher.get_json(
            f"{self.base_url.rstrip('/')}/arrivees",
            params={"date": date, "hippo": race.get("hippodrome", "")},
        )
        if not res.ok:
            return None, res.error
        payload = res.data or {}
        courses = payload.get("message", []) if isinstance(payload, dict) else []
        return self._parse(courses, race), f"ok (cache={res.cached})"

    def _parse(self, courses: list, race: dict) -> dict:
        """Construit {nom_cheval_norm: {cote, gains, musique, driver, place}}."""
        out: dict = {}
        for course in courses:
            details = course.get("arrivee_details") or {}
            for num, info in details.items():
                nom = normalize_name(info.get("nom_cheval"))
                if not nom:
                    continue
                out[nom] = {
                    "cote": float(info["cotes"][-1]) if info.get("cotes") else None,
                    "gains": info.get("gains"),
                    "musique": info.get("musique"),
                    "driver": normalize_name(info.get("nom_jockey")),
                    "place": int(num) if str(num).isdigit() else None,
                }
        return out

    def describe(self) -> str:
        return f"open-pmu-api [{'actif: ' + self.base_url if self.active else 'desactive'}]"


# ----------------------------------------------------------------------
# 2) Recherche web libre (actualites / forme) - DuckDuckGo HTML
# ----------------------------------------------------------------------
class WebSearch:
    """Recherche de snippets d'actualites pour un cheval / driver.

    Aucune cle API requise, mais c'est du scraping de page de resultats :
    fragile (anti-bot possible), a usage raisonnable (delai entre requetes,
    cache long). Une cle SerpAPI peut etre substituee via QUINTE_SERPAPI_KEY.
    """

    name = "recherche-web"

    POSITIF = ("1er", "victoire", "vainqueur", "gagnant", "place",
               "en forme", "atout", "confirme", "turbo", "devra")
    NEGATIF = ("decevant", "non place", "forfait", "declasse", "malheureux",
               "a l'ecart", "delicat", "rendement", "sur sa distance")

    def __init__(self, fetcher: PoliteFetcher | None = None):
        self.fetcher = fetcher or PoliteFetcher(timeout=7, retries=1, cache_ttl_seconds=21600)
        self.active = _SEARCH_ENABLED

    def fetch_race(self, race: dict) -> tuple[dict | None, str]:
        """Interface commune appelee par le moteur : la recherche web est
        traitee partant par partant dans engine.py, pas ici."""
        return None, "geree partant par partant par le moteur"

    def search(self, query: str) -> tuple[list[str], float, str]:
        """Retourne (snippets, sentiment dans [-1, 1], etat)."""
        if not self.active:
            return [], 0.0, "desactive (QUINTE_SEARCH_ENABLED=0)"
        if os.getenv("QUINTE_SERPAPI_KEY"):
            return self._serpapi(query)
        url = "https://html.duckduckgo.com/html/"
        res = self.fetcher.get_text(url, {"q": query})
        if not res.ok:
            return [], 0.0, f"echec recherche: {res.error}"
        snippets = self._extract_snippets(res.data or "")
        sentiment = self._sentiment(snippets)
        return snippets, sentiment, f"ok, {len(snippets)} resultat(s)"

    def _extract_snippets(self, html: str) -> list[str]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return []
        soup = BeautifulSoup(html, "lxml")
        out = []
        for node in soup.select(".result__snippet"):
            text = node.get_text(" ", strip=True)
            if text:
                out.append(text)
        return out[:5]

    def _sentiment(self, snippets: list[str]) -> float:
        if not snippets:
            return 0.0
        text = " ".join(snippets).lower()
        pos = sum(1 for w in self.POSITIF if w in text)
        neg = sum(1 for w in self.NEGATIF if w in text)
        return max(-1.0, min(1.0, (pos - neg) / max(1, len(snippets))))

    def _serpapi(self, query: str) -> tuple[list[str], float, str]:
        key = os.getenv("QUINTE_SERPAPI_KEY")
        res = self.fetcher.get_json(
            "https://serpapi.com/search.json",
            {"q": query, "engine": "google", "api_key": key, "hl": "fr", "num": "5"},
        )
        if not res.ok:
            return [], 0.0, f"echec SerpAPI: {res.error}"
        results = (res.data or {}).get("organic_results", [])
        snippets = [r.get("snippet", "") for r in results if r.get("snippet")]
        return snippets, self._sentiment(snippets), f"SerpAPI ok, {len(snippets)} resultat(s)"

    def describe(self) -> str:
        return f"recherche-web [{'actif' if self.active else 'desactive'}]"


# ----------------------------------------------------------------------
# 3) Sites officiels - adaptateurs PREPARES mais DESACTIVES par defaut
#    (anti-bot / conditions d'utilisation non documentees / robots.txt).
#    Le code est la pour etre active a vos risques, apres verification
#    des conditions d'utilisation et du robots.txt de chaque site.
# ----------------------------------------------------------------------
@dataclass
class DisabledSiteAdapter:
    """Squelette d'adaptateur pour un site officiel non accessible en scraping."""

    name: str
    base_url: str
    note: str
    fetcher: PoliteFetcher = field(default_factory=PoliteFetcher)
    active: bool = field(default=False, init=False)

    def fetch_race(self, race: dict) -> tuple[dict | None, str]:
        _ = race
        return None, f"desactive par defaut: {self.note}"

    def describe(self) -> str:
        return f"{self.name} [desactive - {self.note}]"


# ----------------------------------------------------------------------
# Registre des sources
# ----------------------------------------------------------------------
def build_sources() -> list:
    """Construit la liste ordonnee des adaptateurs actifs/inactifs."""
    return [
        OpenPMUAPI(),
        WebSearch(),
        DisabledSiteAdapter("geny.com", "https://www.geny.com/",
                            "anti-bot + ToS; activer a vos risques"),
        DisabledSiteAdapter("paris-turf.com", "https://www.paris-turf.com/",
                            "anti-bot (Next.js) + ToS; activer a vos risques"),
        DisabledSiteAdapter("letrot.com", "https://www.letrot.com/",
                            "anti-bot + ToS; activer a vos risques"),
        DisabledSiteAdapter("france-galop.com", "https://www.france-galop.com/",
                            "pas d'API publique documentee"),
    ]


class RateLimiter:
    """Garde-fou : jamais plus d'une requete toutes les `delay` secondes."""

    def __init__(self, delay: float):
        self.delay = delay
        self._last = 0.0

    def wait(self) -> None:
        if self.delay <= 0:
            return
        delta = self.delay - (time.time() - self._last)
        if delta > 0:
            time.sleep(delta)
        self._last = time.time()
