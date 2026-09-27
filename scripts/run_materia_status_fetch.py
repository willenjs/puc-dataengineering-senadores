"""Busca o status de tramitação (/processo/{id}) das matérias efetivamente votadas.

Roda depois que dim_materia já tem id_processo populado (via refresh do pipeline
seguinte ao gap-fill, já que id_processo pode vir tanto de materias_pesquisa quanto de
materias_detalhe) -- descobre o id_processo de cada matéria referenciada por uma
votação e busca o status individualmente, gravando em Bronze.status_processos (via
Volume). silver_status_processos une pelo id_processo, e dim_materia (Gold) expõe
tramitando/situacao_atual/materia_concluida no próximo refresh do pipeline.
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
from senado_pipeline.extract_status_processos import extract_status_processos

VOLUME_ROOT_PADRAO = "/Volumes/senado_votacoes/bronze/raw_landing"


def buscar_id_processos_votados(conn) -> list[str]:
    """Lê a fila de controle dos processos a consultar (o de cada matéria já votada).

    Mesmo escopo de custo controlado das outras duas tarefas: não consulta as ~18k
    matérias apresentadas, só as que já geraram votação. O recorte é declarado em
    `silver_fila_processos_status.sql`, e por isso a consulta aqui é um select simples.
    """
    cursor = conn.cursor()
    try:
        cursor.execute("select id_processo from senado_votacoes.silver.fila_processos_status")
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
        id_processos = buscar_id_processos_votados(conn)
        print(f"{len(id_processos)} processos a verificar.")
        if not id_processos:
            return
        resumo = extract_status_processos(id_processos, volume_root, extraction_date)
        print(resumo)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
