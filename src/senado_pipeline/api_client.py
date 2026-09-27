"""Cliente HTTP para a API de Dados Abertos do Senado."""
from __future__ import annotations

import time

import requests

BASE_URL = "https://legis.senado.leg.br/dadosabertos"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class SenadoAPIError(Exception):
    """Erro ao consultar a API do Senado após esgotar as tentativas."""


def fetch_json(
    path: str,
    params: dict | None = None,
    session: requests.Session | None = None,
    max_retries: int = 3,
    backoff_seconds: float = 0.5,
) -> dict:
    session = session or requests.Session()
    url = f"{BASE_URL}{path}"
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = session.get(
                url, params=params, headers={"Accept": "application/json"}, timeout=30
            )
        except requests.RequestException as exc:
            last_error = exc
        else:
            if response.status_code not in RETRYABLE_STATUS_CODES:
                try:
                    response.raise_for_status()
                except requests.HTTPError as exc:
                    raise SenadoAPIError(f"HTTP {response.status_code} em {url}: {exc}") from exc
                return response.json()
            last_error = SenadoAPIError(f"HTTP {response.status_code} em {url}")

        if attempt < max_retries:
            time.sleep(backoff_seconds * (2**attempt))

    raise SenadoAPIError(
        f"Falha ao consultar {url} após {max_retries + 1} tentativas: {last_error}"
    ) from last_error
