"""Extração Bronze: todos os parlamentares (titulares e suplentes) da 57ª legislatura.

Usa /senador/lista/legislatura/57 em vez de /senador/lista/atual: a lista "atual" só
traz quem ocupa a cadeira hoje, mas fact_voto_senador cobre votos de 2023-2026 e
inclui suplentes/titulares que já deixaram o cargo nesse período.
"""
from __future__ import annotations

from senado_pipeline.api_client import fetch_json
from senado_pipeline.volume_writer import build_bronze_relative_path, write_json_to_volume

LEGISLATURA = 57


def extract_senadores(
    volume_root: str,
    extraction_date: str,
    fetch=fetch_json,
    write=write_json_to_volume,
) -> dict:
    """Busca todos os parlamentares da 57ª legislatura e grava o payload bruto em Bronze.

    Retorna {"senadores_extraidos": int}.
    """
    lista = fetch(f"/senador/lista/legislatura/{LEGISLATURA}")
    relative_path = build_bronze_relative_path("senadores", extraction_date, "lista_atual")
    write(volume_root, relative_path, lista)

    return {"senadores_extraidos": len(_extrair_codigos(lista))}


def _extrair_codigos(lista: dict) -> list[str]:
    parlamentares = (
        lista.get("ListaParlamentarLegislatura", {})
        .get("Parlamentares", {})
        .get("Parlamentar", [])
    )
    if isinstance(parlamentares, dict):
        parlamentares = [parlamentares]
    return [p["IdentificacaoParlamentar"]["CodigoParlamentar"] for p in parlamentares]
