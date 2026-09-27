from unittest.mock import MagicMock

from scripts.generate_data_dictionary import buscar_linhas_information_schema


def test_buscar_linhas_information_schema_converte_cursor_em_dicts():
    cursor = MagicMock()
    cursor.description = [
        ("table_schema",),
        ("table_name",),
        ("table_comment",),
        ("column_name",),
        ("column_comment",),
        ("data_type",),
        ("column_position",),
    ]
    cursor.fetchall.return_value = [
        ("silver", "senadores", "Um senador por linha.", "codigo_senador", "Identificador único.", "string", 1),
    ]
    conn = MagicMock()
    conn.cursor.return_value = cursor

    linhas = buscar_linhas_information_schema(conn)

    assert linhas == [
        {
            "table_schema": "silver",
            "table_name": "senadores",
            "table_comment": "Um senador por linha.",
            "column_name": "codigo_senador",
            "column_comment": "Identificador único.",
            "data_type": "string",
            "column_position": 1,
        }
    ]
    cursor.close.assert_called_once()
