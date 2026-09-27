"""Credenciais e configuração de conexão com o Databricks, compartilhadas pelos
scripts que rodam tanto localmente (via .env) quanto como Job task remoto."""
from __future__ import annotations

import os

SECRET_SCOPE = "senado-votacoes"
DATABRICKS_SERVER_HOSTNAME_PADRAO = "dbc-0fa55160-bf7d.cloud.databricks.com"
DATABRICKS_HTTP_PATH_PADRAO = "/sql/1.0/warehouses/4e68171519692b7c"


def obter_secret(key: str, env_var: str, obrigatorio: bool = True) -> str | None:
    """Busca uma credencial sensível: usa a variável de ambiente/`.env` quando
    presente (execução local), senão recorre ao secret scope do Databricks via
    `dbutils.secrets.get` (execução como Job task em compute serverless, que não tem
    um jeito nativo no Jobs API de injetar env vars com `{{secrets/...}}` num
    `spark_python_task` -- só clusters clássicos suportam isso via `spark_env_vars`).

    `obrigatorio=False` retorna `None` em vez de propagar o erro quando o secret não
    existe (usado para `ANTHROPIC_WORKSPACE_ID`, que é opcional).
    """
    valor = os.environ.get(env_var)
    if valor:
        return valor
    from databricks.sdk.runtime import dbutils

    try:
        return dbutils.secrets.get(scope=SECRET_SCOPE, key=key)
    except Exception:
        if obrigatorio:
            raise
        return None
