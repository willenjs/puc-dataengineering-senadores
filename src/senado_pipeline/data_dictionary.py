"""Gera um dicionário de dados em Markdown a partir do information_schema do Unity Catalog."""
from __future__ import annotations


def build_data_dictionary(linhas: list[dict]) -> str:
    """Renderiza um dicionário de dados em Markdown, agrupado por schema.

    Cada linha em `linhas` representa uma coluna, com as chaves: table_schema,
    table_name, table_comment, column_name, column_comment, data_type, column_position.
    """
    tabelas: dict[tuple[str, str], dict] = {}
    for linha in linhas:
        chave = (linha["table_schema"], linha["table_name"])
        tabela = tabelas.setdefault(chave, {"table_comment": linha["table_comment"], "colunas": []})
        tabela["colunas"].append(
            (linha["column_position"], linha["column_name"], linha["data_type"], linha["column_comment"])
        )

    linhas_saida = ["# Dicionário de Dados — Senado Votações", ""]
    schema_atual: str | None = None

    for (schema, nome_tabela), tabela in sorted(
        tabelas.items(), key=lambda kv: (kv[0][0].upper(), kv[0][1].upper())
    ):
        if schema != schema_atual:
            linhas_saida.append(f"## Schema `{schema.upper()}`")
            linhas_saida.append("")
            schema_atual = schema

        descricao = tabela["table_comment"] or "_sem descrição_"
        linhas_saida.append(f"### `{nome_tabela}`")
        linhas_saida.append("")
        linhas_saida.append(descricao)
        linhas_saida.append("")
        linhas_saida.append("| Coluna | Tipo | Descrição |")
        linhas_saida.append("|---|---|---|")

        for _, nome_coluna, tipo, col_descricao in sorted(tabela["colunas"]):
            linhas_saida.append(
                f"| `{nome_coluna}` | `{tipo}` | {col_descricao or '_sem descrição_'} |"
            )
        linhas_saida.append("")

    return "\n".join(linhas_saida)
