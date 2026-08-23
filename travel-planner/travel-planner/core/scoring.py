"""
core/scoring.py
-----------------
Calcul du score qualité-prix global d'un package voyage (transport +
hébergement), utilisé pour classer et recommander les meilleures offres.

Le score est RELATIF aux résultats de la recherche en cours (et non
absolu) : chaque critère est normalisé entre le meilleur et le pire
résultat trouvé, ce qui donne une lecture immédiate ("ce package est
parmi les moins chers ET parmi les plus rapides de cette recherche").

Pourquoi ce choix (point de vue métier) : un voyageur ne compare jamais
un prix dans l'absolu, mais toujours par rapport aux autres offres
disponibles pour son trajet précis. Un score relatif reste donc
pertinent quel que soit le budget ou la destination.
"""

from __future__ import annotations

from config import SCORE_WEIGHTS


def _normalize(value: float, best: float, worst: float) -> float:
    """Retourne un score 0-100, où `best` -> 100 et `worst` -> 0."""
    if best == worst:
        return 100.0
    ratio = (worst - value) / (worst - best) if worst > best else (value - worst) / (best - worst)
    return max(0.0, min(100.0, ratio * 100))


def score_packages(packages: list) -> list:
    """
    Attribue un `.score` (0-100) et des `.badges` à chaque TravelPackage
    de la liste, puis la retourne triée par score décroissant.
    """
    if not packages:
        return packages

    prices = [p.total_price for p in packages]
    durations = [p.total_duration_min for p in packages]
    comforts = [p.comfort_score for p in packages]
    co2s = [p.total_co2_kg for p in packages]

    for pkg in packages:
        price_score = _normalize(pkg.total_price, min(prices), max(prices))
        duration_score = _normalize(pkg.total_duration_min, min(durations), max(durations))
        comfort_score = _normalize(pkg.comfort_score, max(comforts), min(comforts))
        eco_score = _normalize(pkg.total_co2_kg, min(co2s), max(co2s))

        pkg.score = round(
            price_score * SCORE_WEIGHTS["price"]
            + duration_score * SCORE_WEIGHTS["duration"]
            + comfort_score * SCORE_WEIGHTS["comfort"]
            + eco_score * SCORE_WEIGHTS["eco"],
            1,
        )
        pkg.badges = []  # réinitialise avant ré-attribution (utile en cas de re-tri)

    packages.sort(key=lambda p: p.score, reverse=True)

    packages[0].badges.append("🏆 Meilleur rapport qualité-prix")
    cheapest = min(packages, key=lambda p: p.total_price)
    fastest = min(packages, key=lambda p: p.total_duration_min)
    greenest = min(packages, key=lambda p: p.total_co2_kg)
    if "💶 Le plus économique" not in cheapest.badges:
        cheapest.badges.append("💶 Le plus économique")
    if "⚡ Le plus rapide" not in fastest.badges:
        fastest.badges.append("⚡ Le plus rapide")
    if "🌱 Le plus écologique" not in greenest.badges:
        greenest.badges.append("🌱 Le plus écologique")

    return packages
