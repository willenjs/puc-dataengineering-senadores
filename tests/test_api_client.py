import pytest
import responses

from senado_pipeline.api_client import BASE_URL, SenadoAPIError, fetch_json


@responses.activate
def test_fetch_json_returns_parsed_body():
    responses.add(
        responses.GET,
        f"{BASE_URL}/senador/lista/atual",
        json={"ListaParlamentarEmExercicio": {"Parlamentares": {}}},
        status=200,
    )

    result = fetch_json("/senador/lista/atual")

    assert result == {"ListaParlamentarEmExercicio": {"Parlamentares": {}}}


@responses.activate
def test_fetch_json_retries_on_server_error_then_succeeds():
    url = f"{BASE_URL}/senador/lista/atual"
    responses.add(responses.GET, url, status=503)
    responses.add(responses.GET, url, json={"ok": True}, status=200)

    result = fetch_json("/senador/lista/atual", max_retries=2, backoff_seconds=0)

    assert result == {"ok": True}
    assert len(responses.calls) == 2


@responses.activate
def test_fetch_json_raises_after_exhausting_retries():
    url = f"{BASE_URL}/senador/lista/atual"
    responses.add(responses.GET, url, status=503)
    responses.add(responses.GET, url, status=503)
    responses.add(responses.GET, url, status=503)

    with pytest.raises(SenadoAPIError):
        fetch_json("/senador/lista/atual", max_retries=2, backoff_seconds=0)

    assert len(responses.calls) == 3


@responses.activate
def test_fetch_json_nao_tenta_de_novo_em_erro_de_cliente():
    url = f"{BASE_URL}/senador/lista/atual"
    responses.add(responses.GET, url, status=404)

    with pytest.raises(SenadoAPIError):
        fetch_json("/senador/lista/atual", max_retries=2, backoff_seconds=0)

    assert len(responses.calls) == 1
