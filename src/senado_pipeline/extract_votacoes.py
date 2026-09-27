"""Extração Bronze: votações plenárias de 2023 a 2026 (arquivo anual pré-gerado)."""
from __future__ import annotations

from senado_pipeline.api_client import fetch_json
from senado_pipeline.volume_writer import build_bronze_relative_path, write_json_to_volume

ANOS = range(2023, 2027)


def extract_votacoes(
    volume_root: str,
    extraction_date: str,
    fetch=fetch_json,
    write=write_json_to_volume,
) -> dict:
    """Busca o arquivo anual de votações (já inclui os votos individuais aninhados).

    Retorna {"anos_extraidos": int, "anos_falhos": list[int]}.
    """
    falhos: list[int] = []
    sucesso = 0
    for ano in ANOS:
        try:
            votacoes = fetch(f"/arquivos/ListaVotacoes{ano}.json")
        except Exception:
            falhos.append(ano)
            continue
        relative_path = build_bronze_relative_path("votacoes", extraction_date, f"lista_{ano}")
        write(volume_root, relative_path, votacoes)
        sucesso += 1

    return {"anos_extraidos": sucesso, "anos_falhos": falhos}
