"""
ui/components.py
------------------
Composants d'affichage réutilisables : carte de package voyage et
graphique de comparaison visuelle. Ne contient AUCUNE logique métier
(recherche, scoring...) — uniquement de la présentation.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from core.combiner import TravelPackage


def render_package_card(pkg: TravelPackage, rank: int) -> None:
    """Affiche une carte HTML détaillée pour un package voyage."""
    is_top = rank == 1
    card_class = "package-card top-pick" if is_top else "package-card"
    acc = pkg.accommodation
    trs = pkg.transport

    stars_display = "⭐" * acc.stars if acc.stars else "—"
    badges_html = "".join(f"<span class='badge'>{b}</span>" for b in pkg.badges)

    st.markdown(
        f"""
        <div class="{card_class}">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <div>
                    <span style="font-size:1.05rem; font-weight:700;">
                        #{rank} — {trs.mode} {trs.operator} + {acc.type} {stars_display}
                    </span><br>
                    {badges_html}
                </div>
                <div style="text-align:right;">
                    <div class="score-pill">{pkg.score}/100</div>
                    <div class="muted">score qualité-prix</div>
                </div>
            </div>
            <hr style="margin:0.6rem 0;">
            <div style="display:flex; gap:2.2rem; flex-wrap:wrap;">
                <div><b>💰 Total séjour</b><br>{pkg.total_price:.0f} €</div>
                <div><b>🚗 Transport</b><br>{trs.price_eur:.0f} € · {trs.duration_min // 60}h{trs.duration_min % 60:02d}
                    (+ {trs.access_time_min} min d'accès)</div>
                <div><b>🏨 Hébergement</b><br>{acc.price_per_night:.0f} €/nuit · {acc.name} ·
                    {acc.distance_from_center_km} km du centre</div>
                <div><b>🌱 CO₂ estimé</b><br>{pkg.total_co2_kg} kg</div>
            </div>
            <div class="muted" style="margin-top:0.4rem;">
                Départ {trs.departure_time or "flexible"} ·
                {"Données réelles (API)" if trs.is_real_data else "Estimation simulée"}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_comparison_chart(packages: list[TravelPackage]) -> None:
    """Nuage de points prix / durée : taille = score, couleur = mode de transport."""
    if not packages:
        return
    df = pd.DataFrame(
        {
            "Prix total (€)": [p.total_price for p in packages],
            "Durée totale (h)": [round(p.total_duration_min / 60, 1) for p in packages],
            "Score qualité-prix": [p.score for p in packages],
            "Mode": [p.transport.mode for p in packages],
            "Hébergement": [p.accommodation.type for p in packages],
        }
    )
    fig = px.scatter(
        df,
        x="Prix total (€)",
        y="Durée totale (h)",
        size="Score qualité-prix",
        color="Mode",
        symbol="Hébergement",
        hover_data=["Score qualité-prix"],
        title="Comparaison visuelle : en bas à gauche = moins cher et plus rapide",
    )
    fig.update_layout(height=430, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)
