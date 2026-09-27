"""Orquestra a extração Bronze completa: senadores, matérias e votações."""
from __future__ import annotations

import os
from datetime import date

from dotenv import load_dotenv

from senado_pipeline.api_client import fetch_json
from senado_pipeline.extract_materias import extract_materias
from senado_pipeline.extract_referencias import extract_tipos_materia, extract_tipos_situacao
from senado_pipeline.extract_senadores import extract_senadores
from senado_pipeline.extract_votacoes import extract_votacoes
from senado_pipeline.volume_writer import write_json_to_volume

VOLUME_ROOT_PADRAO = "/Volumes/senado_votacoes/bronze/raw_landing"


def run_all(
    volume_root: str,
    extraction_date: str,
    fetch=fetch_json,
    write=write_json_to_volume,
) -> dict:
    """Roda as 5 extrações Bronze e retorna um resumo consolidado."""
    return {
        "senadores": extract_senadores(volume_root, extraction_date, fetch, write),
        "materias": extract_materias(volume_root, extraction_date, fetch, write),
        "votacoes": extract_votacoes(volume_root, extraction_date, fetch, write),
        "tipos_situacao": extract_tipos_situacao(volume_root, extraction_date, fetch, write),
        "tipos_materia": extract_tipos_materia(volume_root, extraction_date, fetch, write),
    }


def main() -> None:
    load_dotenv()
    # `or` em vez do default de dois argumentos: `.get(k, PADRAO)` devolve "" quando a
    # chave existe mas está vazia -- exatamente o que `.env.example` produz depois de
    # `cp .env.example .env` + `load_dotenv()`.
    volume_root = os.environ.get("SENADO_VOLUME_ROOT") or VOLUME_ROOT_PADRAO
    extraction_date = date.today().isoformat()

    resumo = run_all(volume_root, extraction_date)
    print(resumo)


if __name__ == "__main__":
    main()
