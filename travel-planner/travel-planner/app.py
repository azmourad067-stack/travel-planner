"""
app.py
-------
Point d'entrée Streamlit de TripSense, comparateur de voyages
(transport + hébergement). Ce fichier ne contient QUE de la logique
d'interface : la recherche, le scoring et les règles métier vivent dans
le package `core/`.

Lancer en local :   streamlit run app.py
Déploiement :       voir README.md
"""

from datetime import date, timedelta

import streamlit as st

from config import APP_TITLE, APP_ICON, USE_REAL_FLIGHT_API
from core.accommodation import search_accommodation_offers
from core.combiner import build_packages
from core.exceptions import TripSenseError
from core.geo import geocode_city, haversine_distance_km
from core.scoring import score_packages
from core.transport import search_transport_offers
from ui.components import render_comparison_chart, render_package_card
from ui.styles import inject_custom_css

st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")
inject_custom_css()

st.title(f"{APP_ICON} {APP_TITLE}")
st.caption(
    "Comparez en un instant les meilleures combinaisons transport + hébergement "
    "pour votre budget, avec un score qualité-prix calculé automatiquement."
)

if not USE_REAL_FLIGHT_API:
    st.info(
        "Mode démo : la géolocalisation des villes est en temps réel (OpenStreetMap), "
        "mais les tarifs train/bus/avion/hébergement sont simulés à partir de barèmes "
        "réalistes fondés sur la distance réelle. Ajoutez une clé API Amadeus gratuite "
        "dans les secrets pour activer la recherche de vols en temps réel "
        "(voir le README).",
        icon="ℹ️",
    )

# ---------------------------------------------------------------------------
# Formulaire de recherche
# ---------------------------------------------------------------------------
with st.form("search_form"):
    st.subheader("🔎 Votre recherche")

    col1, col2 = st.columns(2)
    with col1:
        departure_city = st.text_input("Ville de départ", placeholder="ex. Paris")
    with col2:
        destination_city = st.text_input("Ville de destination", placeholder="ex. Barcelone")

    col3, col4 = st.columns(2)
    with col3:
        departure_date = st.date_input(
            "Date de départ", value=date.today() + timedelta(days=30), min_value=date.today()
        )
    with col4:
        return_date = st.date_input(
            "Date de retour",
            value=date.today() + timedelta(days=33),
            min_value=date.today() + timedelta(days=1),
        )

    col5, col6 = st.columns(2)
    with col5:
        travelers = st.number_input("Nombre de voyageurs", min_value=1, max_value=8, value=2)
    with col6:
        radius_km = st.slider("Rayon de recherche autour de la destination (km)", 1, 50, 10)

    st.markdown("**Budget total du séjour**")
    col7, col8 = st.columns(2)
    with col7:
        target_budget = st.number_input("Budget cible (€)", min_value=50, value=600, step=50)
    with col8:
        tolerance = st.slider("Marge de tolérance (± €)", 0, 500, 100, step=25)

    st.markdown("**Hébergement**")
    col9, col10 = st.columns(2)
    with col9:
        accommodation_type = st.radio(
            "Type d'hébergement", ["Hôtel", "Airbnb", "Les deux"], horizontal=True
        )
    with col10:
        hotel_enabled = accommodation_type in ("Hôtel", "Les deux")
        star_filter = st.multiselect(
            "Étoiles (hôtels uniquement)",
            options=[1, 2, 3, 4, 5],
            default=[2, 3, 4] if hotel_enabled else [],
            disabled=not hotel_enabled,
            help="Actif uniquement si le type d'hébergement inclut « Hôtel ».",
        )

    submitted = st.form_submit_button("Rechercher les meilleurs plans de voyage", type="primary")

# ---------------------------------------------------------------------------
# Traitement de la recherche (à la soumission du formulaire uniquement)
# ---------------------------------------------------------------------------
if submitted:
    errors = []
    if not departure_city.strip():
        errors.append("Merci d'indiquer une ville de départ.")
    if not destination_city.strip():
        errors.append("Merci d'indiquer une ville de destination.")
    if (
        departure_city.strip()
        and destination_city.strip()
        and departure_city.strip().lower() == destination_city.strip().lower()
    ):
        errors.append("La ville de départ et la destination doivent être différentes.")
    if return_date <= departure_date:
        errors.append("La date de retour doit être postérieure à la date de départ.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        nights = (return_date - departure_date).days
        budget_min = max(0, target_budget - tolerance)
        budget_max = target_budget + tolerance

        try:
            with st.spinner("Localisation des villes en temps réel..."):
                origin_point = geocode_city(departure_city)
                destination_point = geocode_city(destination_city)

            distance_km = round(haversine_distance_km(origin_point, destination_point), 1)

            with st.spinner("Recherche des offres de transport..."):
                transport_offers, used_real_flight_api = search_transport_offers(
                    origin_point, destination_point, distance_km, departure_date.isoformat()
                )

            with st.spinner("Recherche des hébergements..."):
                accommodation_offers = search_accommodation_offers(
                    destination_point, radius_km, accommodation_type, star_filter or None
                )

            if not transport_offers:
                st.error("Aucune offre de transport trouvée pour ce trajet. Réessayez avec des villes différentes.")
                st.session_state.pop("last_search", None)
            elif not accommodation_offers:
                st.error("Aucun hébergement trouvé dans ce rayon. Essayez d'élargir le rayon de recherche.")
                st.session_state.pop("last_search", None)
            else:
                packages, cheapest_overall = build_packages(
                    transport_offers, accommodation_offers, int(travelers), nights, budget_min, budget_max
                )
                if not packages:
                    st.warning(
                        f"😕 Aucune combinaison trouvée entre {budget_min:.0f} € et {budget_max:.0f} €. "
                        f"Le package le moins cher trouvé pour ce trajet coûte environ "
                        f"**{cheapest_overall:.0f} €**. Essayez d'augmenter votre budget ou la marge de "
                        "tolérance, ou d'élargir le rayon de recherche d'hébergement."
                    )
                    st.session_state.pop("last_search", None)
                else:
                    packages = score_packages(packages)
                    st.session_state["last_search"] = {
                        "packages": packages,
                        "origin_name": origin_point.name,
                        "destination_name": destination_point.name,
                        "distance_km": distance_km,
                        "nights": nights,
                        "travelers": int(travelers),
                        "used_real_flight_api": used_real_flight_api,
                    }
        except TripSenseError as e:
            st.error(str(e))
            st.session_state.pop("last_search", None)
        except Exception as e:  # filet de sécurité générique
            st.error("Une erreur inattendue est survenue pendant la recherche. Merci de réessayer.")
            st.exception(e)
            st.session_state.pop("last_search", None)

# ---------------------------------------------------------------------------
# Affichage des résultats (persistant tant qu'une recherche est en mémoire,
# afin que le tri interactif ne fasse pas disparaître les résultats)
# ---------------------------------------------------------------------------
if "last_search" in st.session_state:
    data = st.session_state["last_search"]
    packages = data["packages"]

    st.success(
        f"📍 {data['origin_name']} → {data['destination_name']} · {data['distance_km']} km à vol d'oiseau · "
        f"{data['nights']} nuit(s) · {data['travelers']} voyageur(s)"
    )
    if data["used_real_flight_api"]:
        st.caption("✈️ Vols récupérés en temps réel via l'API Amadeus.")

    st.markdown(f"### 🎯 {len(packages)} plan(s) de voyage correspondent à votre budget")

    render_comparison_chart(packages)

    sort_option = st.selectbox(
        "Trier les résultats par",
        ["Meilleur score qualité-prix", "Prix croissant", "Durée croissante", "Impact CO₂ croissant"],
        key="sort_select",
    )
    display_packages = list(packages)
    if sort_option == "Prix croissant":
        display_packages.sort(key=lambda p: p.total_price)
    elif sort_option == "Durée croissante":
        display_packages.sort(key=lambda p: p.total_duration_min)
    elif sort_option == "Impact CO₂ croissant":
        display_packages.sort(key=lambda p: p.total_co2_kg)
    # sinon : déjà trié par score décroissant

    for i, pkg in enumerate(display_packages[:15], start=1):
        render_package_card(pkg, rank=i)

elif not submitted:
    st.markdown(
        "👋 Renseignez votre départ, votre destination et votre budget ci-dessus, "
        "puis lancez la recherche pour comparer automatiquement toutes les "
        "combinaisons transport + hébergement possibles."
    )
