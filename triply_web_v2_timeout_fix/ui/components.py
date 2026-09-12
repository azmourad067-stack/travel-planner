from __future__ import annotations

import streamlit as st

from services.models import TravelOffer
from services.state import is_favorite, toggle_favorite, offer_id


ICONS = {
    "flight": "✈️",
    "train": "🚆",
    "bus": "🚌",
    "hotel": "🏨",
    "vacation_rental": "🏡",
    "airbnb": "🏠",
}


def page_heading(title: str, subtitle: str | None = None) -> None:
    st.markdown(f"<h1 style='letter-spacing:-.035em'>{title}</h1>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(
            f"<div class='section-subtitle'>{subtitle}</div>",
            unsafe_allow_html=True,
        )


def render_offer_card(
    offer: TravelOffer,
    *,
    key_prefix: str,
    show_favorite: bool = True,
) -> None:
    with st.container(border=True):
        left, price_col = st.columns([4.6, 1.4], vertical_alignment="center")
        with left:
            icon = ICONS.get(offer.subtype, "🧳")
            st.markdown(f"#### {icon} {offer.title}")
            st.caption(
                f"{offer.provider} · {offer.subtype.replace('_', ' ').title()} · "
                f"{offer.confidence_label}"
            )
            if offer.details:
                st.write(offer.details)

            action_cols = st.columns([1.1, 1.1, 4])
            if offer.url:
                with action_cols[0]:
                    st.link_button("Voir l'offre", offer.url, use_container_width=True)
            if show_favorite:
                with action_cols[1]:
                    fav = is_favorite(offer)
                    if st.button(
                        "❤️ Enregistré" if fav else "🤍 Favori",
                        key=f"{key_prefix}_{offer_id(offer)}",
                        use_container_width=True,
                    ):
                        toggle_favorite(offer)
                        st.rerun()

        with price_col:
            if offer.price_total is not None:
                st.markdown(
                    f"<div class='price'>{offer.price_total:,.0f} €</div>",
                    unsafe_allow_html=True,
                )
                st.caption("prix total estimé")
            else:
                st.markdown("**Prix à vérifier**")
                st.caption("sur le site source")


def render_footer() -> None:
    st.markdown(
        """
        <div class="footer">
            Triply compare des résultats de recherche de voyage.
            Vérifie toujours le prix et la disponibilité finale avant réservation.
        </div>
        """,
        unsafe_allow_html=True,
    )
