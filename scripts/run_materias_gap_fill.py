"""Preenche o gap de matérias referenciadas em fact_votacao mas ausentes de dim_materia.

Roda depois que a Silver já existe: lê a fila `silver.fila_materias_detalhe`, que
declara quais codigo_materia uma votação referencia sem que a busca por ano
(extract_materias) os tenha trazido, busca o detalhe de cada um individualmente e grava
em Bronze.materias_detalhe (via Volume) -- materias (Silver) une as duas fontes, e
dim_materia (Gold) repassa o resultado, no próximo refresh do Lakeflow Pipeline.

O que atravessa a fronteira para a ingestão é uma lista de identificadores, e o que é
gravado na Bronze é o payload cru da API numa partição dt= nova: nenhum dado derivado
volta para a Bronze, e a linhagem dos dados continua só Bronze -> Silver -> Gold.
"""
from __future__ import annotations

import os
from datetime import date

from databricks import sql
from dotenv import load_dotenv

from senado_pipeline.databricks_auth import (
    DATABRICKS_HTTP_PATH_PADRAO,
    DATABRICKS_SERVER_HOSTNAME_PADRAO,
    obter_secret,
)
from senado_pipeline.extract_materias import extract_materias_faltantes

VOLUME_ROOT_PADRAO = "/Volumes/senado_votacoes/bronze/raw_landing"


def buscar_codigos_materia_orfaos(conn) -> list[str]:
    """Lê a fila de controle das matérias órfãs (votadas e ausentes de silver.materias).

    A regra mora em `silver_fila_materias_detalhe.sql`, não neste script: declarada no
    pipeline ela aparece na linhagem do Unity Catalog, e a ingestão passa a ler a Silver
    em vez de atravessar até o Gold, que existe para consumo analítico.
    """
    cursor = conn.cursor()
    try:
        cursor.execute("select codigo_materia from senado_votacoes.silver.fila_materias_detalhe")
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()


def main() -> None:
    load_dotenv()
    # `or` em vez do default de dois argumentos: `.get(k, PADRAO)` devolve "" quando a
    # chave existe mas está vazia -- exatamente o que `.env.example` produz depois de
    # `cp .env.example .env` + `load_dotenv()`.
    volume_root = os.environ.get("SENADO_VOLUME_ROOT") or VOLUME_ROOT_PADRAO
    extraction_date = date.today().isoformat()

    conn = sql.connect(
        server_hostname=os.environ.get("DATABRICKS_SERVER_HOSTNAME") or DATABRICKS_SERVER_HOSTNAME_PADRAO,
        http_path=os.environ.get("DATABRICKS_HTTP_PATH") or DATABRICKS_HTTP_PATH_PADRAO,
        access_token=obter_secret("databricks-token", "DATABRICKS_TOKEN"),
    )
    try:
        codigos = buscar_codigos_materia_orfaos(conn)
        print(f"{len(codigos)} matérias órfãs encontradas.")
        if not codigos:
            return
        resumo_extracao = extract_materias_faltantes(codigos, volume_root, extraction_date)
        print(resumo_extracao)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
