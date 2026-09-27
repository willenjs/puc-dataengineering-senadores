"""Lê o information_schema do Unity Catalog e escreve o dicionário de dados em docs/data-dictionary.md."""
from __future__ import annotations

import os
from pathlib import Path

from databricks import sql
from dotenv import load_dotenv

from senado_pipeline.data_dictionary import build_data_dictionary
from senado_pipeline.databricks_auth import (
    DATABRICKS_HTTP_PATH_PADRAO,
    DATABRICKS_SERVER_HOSTNAME_PADRAO,
    obter_secret,
)

OUTPUT_PATH = Path("docs/data-dictionary.md")

QUERY = """
select
    t.table_schema,
    t.table_name,
    t.comment as table_comment,
    c.column_name,
    c.comment as column_comment,
    -- full_data_type e não data_type: traz precisão e parâmetros (decimal(5,4), array<string>).
    c.full_data_type as data_type,
    c.ordinal_position as column_position
from senado_votacoes.information_schema.tables t
join senado_votacoes.information_schema.columns c
    on c.table_catalog = t.table_catalog
    and c.table_schema = t.table_schema
    and c.table_name = t.table_name
where t.table_schema in ('bronze', 'silver', 'gold')
    -- Lakeflow materializa cada view internamente sob nomes prefixados com dois
    -- underscores (visíveis nesta mesma information_schema.tables) -- tentativas com
    -- startswith() e com LIKE+ESCAPE devolvem 0 linhas ou erro de sintaxe nesta
    -- versão do Databricks; substring()
    -- evita escaping de barra invertida por completo e funciona.
    and substring(t.table_name, 1, 2) != '__'
    -- O log de eventos do pipeline (event_log_<id do pipeline>) é publicado no schema
    -- bronze pelo próprio Lakeflow: é tabela operacional, não dado, e não tem COMMENT.
    and substring(t.table_name, 1, 10) != 'event_log_'
order by t.table_schema, t.table_name, c.ordinal_position
"""


def buscar_linhas_information_schema(conn) -> list[dict]:
    cursor = conn.cursor()
    try:
        cursor.execute(QUERY)
        colunas = [desc[0] for desc in cursor.description]
        return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
    finally:
        cursor.close()


def main() -> None:
    load_dotenv()
    # `or` em vez do default de dois argumentos: `.get(k, PADRAO)` devolve "" quando a
    # chave existe mas está vazia -- exatamente o que `.env.example` produz depois de
    # `cp .env.example .env` + `load_dotenv()`.
    conn = sql.connect(
        server_hostname=os.environ.get("DATABRICKS_SERVER_HOSTNAME") or DATABRICKS_SERVER_HOSTNAME_PADRAO,
        http_path=os.environ.get("DATABRICKS_HTTP_PATH") or DATABRICKS_HTTP_PATH_PADRAO,
        access_token=obter_secret("databricks-token", "DATABRICKS_TOKEN"),
    )
    try:
        linhas = buscar_linhas_information_schema(conn)
    finally:
        conn.close()

    dicionario = build_data_dictionary(linhas)
    # Rodando como Job task remoto, o working directory não é necessariamente a raiz
    # do repositório (docs/ pode não existir ali) -- cria o diretório antes de
    # escrever, e também imprime o conteúdo inteiro no stdout, já que a Task 9 do
    # Plano 2 recupera esse arquivo pelo log de execução da task quando rodada remota
    # (não pelo git, que só reflete o estado local).
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(dicionario, encoding="utf-8")
    print(f"Dicionário de dados gerado em {OUTPUT_PATH}")
    print("--- CONTEÚDO ---")
    print(dicionario)


if __name__ == "__main__":
    main()
