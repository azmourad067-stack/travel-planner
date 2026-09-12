from __future__ import annotations

from dataclasses import dataclass
import os
import streamlit as st


@dataclass(frozen=True)
class Settings:
    amadeus_client_id: str | None
    amadeus_client_secret: str | None
    amadeus_base_url: str
    serpapi_key: str | None


def _secret_or_env(name: str, default: str | None = None) -> str | None:
    try:
        if name in st.secrets:
            value = st.secrets[name]
            return str(value) if value is not None else default
    except Exception:
        pass
    return os.getenv(name, default)


def get_settings() -> Settings:
    return Settings(
        amadeus_client_id=_secret_or_env("AMADEUS_CLIENT_ID"),
        amadeus_client_secret=_secret_or_env("AMADEUS_CLIENT_SECRET"),
        amadeus_base_url=_secret_or_env(
            "AMADEUS_BASE_URL", "https://test.api.amadeus.com"
        ) or "https://test.api.amadeus.com",
        serpapi_key=_secret_or_env("SERPAPI_KEY"),
    )
