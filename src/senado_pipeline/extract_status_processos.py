"""Extração Bronze: status de tramitação de processos legislativos (/processo/{id}).

Escopado às matérias efetivamente votadas (mesmo padrão de custo controlado do
gap-fill e do scoring por LLM: não busca as ~18k matérias todas, só as ~360 que já
geraram votação -- ver scripts/run_materia_status_fetch.py para a query de escopo).

/processo/{id} é o substituto oficial de /materia/situacaoatual/{codigo} e de
/materia/{codigo} para esta finalidade -- ambos já carregam aviso de descontinuação
(Descontinuacao.DataDesativacaoCompleta) na própria resposta.
"""
from __future__ import annotations

from senado_pipeline.api_client import fetch_json
from senado_pipeline.volume_writer import build_bronze_relative_path, write_json_to_volume


def extract_status_processos(
    id_processos: list[str],
    volume_root: str,
    extraction_date: str,
    fetch=fetch_json,
    write=write_json_to_volume,
) -> dict:
    """Busca o status de tramitação de cada processo e grava o payload bruto em Bronze.

    Retorna {"processos_extraidos": int, "processos_falhos": list[str]}.
    """
    falhos: list[str] = []
    sucesso = 0
    for id_processo in id_processos:
        try:
            status = fetch(f"/processo/{id_processo}")
        except Exception:
            falhos.append(id_processo)
            continue
        relative_path = build_bronze_relative_path("status_processos", extraction_date, f"status_{id_processo}")
        write(volume_root, relative_path, status)
        sucesso += 1

    return {"processos_extraidos": sucesso, "processos_falhos": falhos}
