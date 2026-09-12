from __future__ import annotations

from datetime import date, timedelta
import pandas as pd
import streamlit as st

from services.amadeus import AmadeusClient, AmadeusError
from services.search_web import WebSearchClient
from services.models import TravelOffer
from services.combinations import build_budget_combinations
from services.config import get_settings


st.set_page_config(
    page_title="Travel Budget Explorer",
    page_icon="✈️",
    layout="wide",
)

st.title("✈️ Travel Budget Explorer")
st.caption(
    "Compare hébergements et transports, puis construis des combinaisons compatibles avec ton budget."
)

settings = get_settings()

with st.sidebar:
    st.header("Configuration")
    if settings.amadeus_client_id and settings.amadeus_client_secret:
        st.success("Amadeus configuré")
    else:
        st.warning("Amadeus non configuré")

    if settings.serpapi_key:
        st.success("Recherche web configurée")
    else:
        st.warning("Recherche web non configurée")

    st.caption(
        "Les clés sont lues depuis st.secrets ou les variables d'environnement. "
        "Aucune clé n'est codée en dur."
    )

with st.form("trip_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        origin = st.text_input("Ville de départ", placeholder="Paris")
    with c2:
        destination = st.text_input("Destination", placeholder="Rome")
    with c3:
        max_budget = st.number_input(
            "Budget maximal total (€)",
            min_value=50.0,
            value=500.0,
            step=25.0,
        )

    st.markdown("#### Paramètres complémentaires")
    d1, d2, d3 = st.columns(3)
    default_departure = date.today() + timedelta(days=30)
    with d1:
        departure_date = st.date_input(
            "Date de départ",
            value=default_departure,
            min_value=date.today(),
        )
    with d2:
        return_date = st.date_input(
            "Date de retour",
            value=default_departure + timedelta(days=3),
            min_value=date.today() + timedelta(days=1),
        )
    with d3:
        adults = st.number_input("Voyageurs adultes", min_value=1, max_value=9, value=1)

    submitted = st.form_submit_button("🔎 Rechercher les meilleures options", type="primary")

if submitted:
    origin = origin.strip()
    destination = destination.strip()

    if not origin or not destination:
        st.error("Renseigne une ville de départ et une destination.")
        st.stop()

    if origin.casefold() == destination.casefold():
        st.error("La ville de départ et la destination doivent être différentes.")
        st.stop()

    if return_date <= departure_date:
        st.error("La date de retour doit être postérieure à la date de départ.")
        st.stop()

    nights = (return_date - departure_date).days
    budget_per_person = max_budget / adults

    st.info(
        f"Recherche pour **{adults} voyageur(s)**, **{nights} nuit(s)**, "
        f"budget total **{max_budget:.0f} €**."
    )

    transport_offers: list[TravelOffer] = []
    lodging_offers: list[TravelOffer] = []
    web_discovery: list[TravelOffer] = []
    warnings: list[str] = []

    progress = st.progress(0, text="Initialisation…")

    # -------- Amadeus: villes, vols, hôtels --------
    if settings.amadeus_client_id and settings.amadeus_client_secret:
        try:
            progress.progress(10, text="Résolution des villes et aéroports…")
            amadeus = AmadeusClient(
                client_id=settings.amadeus_client_id,
                client_secret=settings.amadeus_client_secret,
                base_url=settings.amadeus_base_url,
            )

            origin_loc = amadeus.find_location(origin)
            destination_loc = amadeus.find_location(destination)

            if not origin_loc:
                warnings.append(f"Ville/aéroport de départ introuvable dans Amadeus : {origin}")
            if not destination_loc:
                warnings.append(f"Destination introuvable dans Amadeus : {destination}")

            if origin_loc and destination_loc:
                progress.progress(25, text="Recherche des vols…")
                try:
                    transport_offers.extend(
                        amadeus.search_flights(
                            origin_code=origin_loc["iataCode"],
                            destination_code=destination_loc["iataCode"],
                            departure_date=departure_date,
                            return_date=return_date,
                            adults=int(adults),
                            max_price=max_budget,
                        )
                    )
                except AmadeusError as exc:
                    warnings.append(f"Vols Amadeus : {exc}")

                progress.progress(45, text="Recherche des hôtels…")
                try:
                    lodging_offers.extend(
                        amadeus.search_hotels(
                            city_code=destination_loc["iataCode"],
                            check_in=departure_date,
                            check_out=return_date,
                            adults=int(adults),
                            max_total=max_budget,
                        )
                    )
                except AmadeusError as exc:
                    warnings.append(f"Hôtels Amadeus : {exc}")

        except AmadeusError as exc:
            warnings.append(f"Amadeus indisponible : {exc}")
    else:
        warnings.append(
            "Clés Amadeus absentes : les vols et hôtels structurés ne peuvent pas être récupérés."
        )

    # -------- Recherche web: Airbnb, train, bus --------
    if settings.serpapi_key:
        progress.progress(65, text="Recherche web Airbnb, trains et bus…")
        web_client = WebSearchClient(settings.serpapi_key)

        try:
            web_discovery.extend(
                web_client.search_accommodations(
                    destination=destination,
                    check_in=departure_date,
                    check_out=return_date,
                    adults=int(adults),
                    max_total=max_budget,
                )
            )
        except Exception as exc:
            warnings.append(f"Recherche web hébergements : {exc}")

        try:
            web_discovery.extend(
                web_client.search_ground_transport(
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                    adults=int(adults),
                )
            )
        except Exception as exc:
            warnings.append(f"Recherche web transports : {exc}")
    else:
        warnings.append(
            "SERPAPI_KEY absente : Airbnb/train/bus ne peuvent pas être recherchés sur le web."
        )

    progress.progress(85, text="Construction des combinaisons sous budget…")

    # Les offres web avec prix fiable peuvent entrer dans les combinaisons.
    for offer in web_discovery:
        if offer.price_total is None:
            continue
        if offer.category == "lodging":
            lodging_offers.append(offer)
        elif offer.category == "transport":
            transport_offers.append(offer)

    # Déduplique et trie.
    def _dedupe(items: list[TravelOffer]) -> list[TravelOffer]:
        seen = set()
        out = []
        for item in items:
            key = (
                item.category,
                item.provider.lower(),
                item.title.lower(),
                round(item.price_total or -1, 2),
            )
            if key not in seen:
                seen.add(key)
                out.append(item)
        return out

    lodging_offers = _dedupe(lodging_offers)
    transport_offers = _dedupe(transport_offers)

    combinations = build_budget_combinations(
        transport_offers=transport_offers,
        lodging_offers=lodging_offers,
        max_budget=float(max_budget),
        limit=25,
    )

    progress.progress(100, text="Recherche terminée")

    for msg in warnings:
        st.warning(msg)

    tab1, tab2, tab3, tab4 = st.tabs(
        ["💡 Combinaisons", "🛏️ Hébergements", "🚆 Transports", "🌐 Résultats web"]
    )

    with tab1:
        if not combinations:
            st.error(
                "Aucune combinaison avec un prix exploitable ne respecte le budget. "
                "Essaie d'augmenter le budget, de changer les dates ou de consulter les résultats web indicatifs."
            )
        else:
            combo_df = pd.DataFrame(
                [
                    {
                        "Transport": c.transport.title,
                        "Prix transport (€)": round(c.transport.price_total or 0, 2),
                        "Hébergement": c.lodging.title,
                        "Prix hébergement (€)": round(c.lodging.price_total or 0, 2),
                        "Total (€)": round(c.total_price, 2),
                        "Reste budget (€)": round(c.remaining_budget, 2),
                        "Confiance": c.confidence,
                    }
                    for c in combinations
                ]
            )
            st.dataframe(combo_df, use_container_width=True, hide_index=True)

            best = combinations[0]
            st.success(
                f"Option la moins chère trouvée : **{best.total_price:.2f} €** "
                f"({best.remaining_budget:.2f} € sous le budget)."
            )

    with tab2:
        priced = [o for o in lodging_offers if o.price_total is not None]
        if not priced:
            st.info("Aucun hébergement tarifé exploitable trouvé.")
        for offer in sorted(priced, key=lambda x: x.price_total or 10**9)[:30]:
            with st.container(border=True):
                cols = st.columns([4, 1])
                with cols[0]:
                    st.markdown(f"**{offer.title}**")
                    st.caption(f"{offer.provider} · {offer.details}")
                    if offer.url:
                        st.link_button("Voir l'offre", offer.url)
                with cols[1]:
                    st.metric("Total séjour", f"{offer.price_total:.2f} €")
                    st.caption(offer.confidence_label)

    with tab3:
        priced = [o for o in transport_offers if o.price_total is not None]
        if not priced:
            st.info("Aucun transport tarifé exploitable trouvé.")
        for offer in sorted(priced, key=lambda x: x.price_total or 10**9)[:30]:
            with st.container(border=True):
                cols = st.columns([4, 1])
                with cols[0]:
                    st.markdown(f"**{offer.title}**")
                    st.caption(f"{offer.provider} · {offer.details}")
                    if offer.url:
                        st.link_button("Voir / vérifier", offer.url)
                with cols[1]:
                    st.metric("Prix total", f"{offer.price_total:.2f} €")
                    st.caption(offer.confidence_label)

    with tab4:
        if not web_discovery:
            st.info("Aucun résultat web complémentaire.")
        else:
            st.caption(
                "Les prix extraits de snippets web sont indicatifs. Vérifie toujours le tarif final sur le site source."
            )
            for offer in web_discovery[:40]:
                with st.container(border=True):
                    st.markdown(f"**{offer.title}**")
                    price_txt = (
                        f"{offer.price_total:.2f} €"
                        if offer.price_total is not None
                        else "prix non exploitable automatiquement"
                    )
                    st.caption(
                        f"{offer.provider} · {offer.subtype} · {price_txt} · {offer.details}"
                    )
                    if offer.url:
                        st.link_button("Ouvrir le résultat", offer.url)

    st.divider()
    st.caption(
        "⚠️ Les prix de voyage changent rapidement. Cette application compare des résultats de recherche ; "
        "elle ne garantit ni disponibilité ni tarif au moment de la réservation."
    )
