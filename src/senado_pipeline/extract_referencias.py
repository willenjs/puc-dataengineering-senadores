"""Extração Bronze: listas de referência (domínios controlados) da API do Senado --
pequenas e praticamente estáticas, buscadas por inteiro a cada execução, sem escopo
por matéria (diferente de extract_materias/extract_status_processos)."""
from __future__ import annotations

from senado_pipeline.api_client import fetch_json
from senado_pipeline.volume_writer import build_bronze_relative_path, write_json_to_volume


def extract_tipos_situacao(
    volume_root: str,
    extraction_date: str,
    fetch=fetch_json,
    write=write_json_to_volume,
) -> dict:
    """Busca a lista de referência de situações de tramitação (/processo/tipos-situacao)
    -- domínio controlado usado para dar significado a dim_materia.sigla_situacao_atual.

    Retorna {"situacoes_extraidas": int}.
    """
    lista = fetch("/processo/tipos-situacao")
    relative_path = build_bronze_relative_path("referencia_situacoes", extraction_date, "tipos_situacao")
    write(volume_root, relative_path, lista)
    return {"situacoes_extraidas": len(lista)}


def extract_tipos_materia(
    volume_root: str,
    extraction_date: str,
    fetch=fetch_json,
    write=write_json_to_volume,
) -> dict:
    """Busca a lista de referência de tipos/siglas de matéria (/processo/siglas) --
    domínio controlado usado para dar significado a dim_materia.sigla.

    Retorna {"tipos_extraidos": int}.
    """
    lista = fetch("/processo/siglas")
    relative_path = build_bronze_relative_path("referencia_tipos_materia", extraction_date, "tipos_materia")
    write(volume_root, relative_path, lista)
    return {"tipos_extraidos": len(lista)}
