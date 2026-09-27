from senado_pipeline.data_dictionary import build_data_dictionary


def test_build_data_dictionary_agrupa_por_schema_e_lista_colunas_em_ordem():
    linhas = [
        {
            "table_schema": "silver",
            "table_name": "senadores",
            "table_comment": "Um senador por linha.",
            "column_name": "nome_senador",
            "column_comment": "Nome do senador.",
            "data_type": "string",
            "column_position": 2,
        },
        {
            "table_schema": "silver",
            "table_name": "senadores",
            "table_comment": "Um senador por linha.",
            "column_name": "codigo_senador",
            "column_comment": "Identificador único do senador.",
            "data_type": "string",
            "column_position": 1,
        },
        {
            "table_schema": "gold",
            "table_name": "senador_alinhamento",
            "table_comment": "Índice de alinhamento por senador.",
            "column_name": "codigo_senador",
            "column_comment": "FK para dim_senador.",
            "data_type": "string",
            "column_position": 1,
        },
    ]

    dicionario = build_data_dictionary(linhas)

    assert "## Schema `GOLD`" in dicionario
    assert "## Schema `SILVER`" in dicionario
    assert "### `senadores`" in dicionario
    assert "| Coluna | Tipo | Descrição |" in dicionario
    assert "| `codigo_senador` | `string` | Identificador único do senador. |" in dicionario
    # Ordem alfabética por schema: GOLD < SILVER.
    assert dicionario.index("## Schema `GOLD`") < dicionario.index("## Schema `SILVER`")
    # Colunas na ordem declarada (column_position), não alfabética.
    bloco_senadores = dicionario[dicionario.index("### `senadores`") :]
    assert bloco_senadores.index("`codigo_senador`") < bloco_senadores.index("`nome_senador`")


def test_build_data_dictionary_usa_texto_padrao_quando_sem_descricao():
    linhas = [
        {
            "table_schema": "silver",
            "table_name": "materias",
            "table_comment": None,
            "column_name": "sigla",
            "column_comment": None,
            "data_type": "string",
            "column_position": 1,
        },
    ]

    dicionario = build_data_dictionary(linhas)

    assert "_sem descrição_" in dicionario


def test_build_data_dictionary_mostra_o_tipo_completo_de_cada_coluna():
    linhas = [
        {
            "table_schema": "gold",
            "table_name": "fact_materia_scored",
            "table_comment": "Nota publicada por matéria.",
            "column_name": "nota_classe_baixa",
            "column_comment": "Nota de -1 a 1.",
            "data_type": "double",
            "column_position": 1,
        },
        {
            "table_schema": "gold",
            "table_name": "fact_materia_scored",
            "table_comment": "Nota publicada por matéria.",
            "column_name": "data_votacao",
            "column_comment": "Data.",
            "data_type": "date",
            "column_position": 2,
        },
    ]

    dicionario = build_data_dictionary(linhas)

    assert "| `nota_classe_baixa` | `double` | Nota de -1 a 1. |" in dicionario
    assert "| `data_votacao` | `date` | Data. |" in dicionario
