"""Extração Bronze: matérias apresentadas/tramitando entre 2023 e 2026."""
from __future__ import annotations

from senado_pipeline.api_client import fetch_json
from senado_pipeline.volume_writer import build_bronze_relative_path, write_json_to_volume

ANOS = range(2023, 2027)


def extract_materias(
    volume_root: str,
    extraction_date: str,
    fetch=fetch_json,
    write=write_json_to_volume,
) -> dict:
    """Busca a lista de matérias de cada ano de 2023 a 2026 e grava o payload bruto em Bronze.

    Retorna {"anos_extraidos": int, "anos_falhos": list[int]}.
    """
    falhos: list[int] = []
    sucesso = 0
    for ano in ANOS:
        try:
            pesquisa = fetch("/materia/pesquisa/lista", params={"ano": ano})
        except Exception:
            falhos.append(ano)
            continue
        relative_path = build_bronze_relative_path("materias", extraction_date, f"pesquisa_{ano}")
        write(volume_root, relative_path, pesquisa)
        sucesso += 1

    return {"anos_extraidos": sucesso, "anos_falhos": falhos}


def extract_materias_faltantes(
    codigos: list[str],
    volume_root: str,
    extraction_date: str,
    fetch=fetch_json,
    write=write_json_to_volume,
) -> dict:
    """Busca o detalhe de matérias específicas não cobertas por `extract_materias`
    (ex: apresentadas antes de 2023 mas ainda referenciadas por uma votação de
    2023-2026, ou de um tipo que a busca por ano não retorna).

    Retorna {"materias_extraidas": int, "materias_falhas": list[str]}.
    """
    falhas: list[str] = []
    sucesso = 0
    for codigo in codigos:
        try:
            detalhe = fetch(f"/materia/{codigo}")
        except Exception:
            falhas.append(codigo)
            continue
        relative_path = build_bronze_relative_path("materias_detalhe", extraction_date, f"detalhe_{codigo}")
        write(volume_root, relative_path, detalhe)
        sucesso += 1

    return {"materias_extraidas": sucesso, "materias_falhas": falhas}
