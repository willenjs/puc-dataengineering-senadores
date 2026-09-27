from unittest.mock import MagicMock

from scripts.run_materias_gap_fill import buscar_codigos_materia_orfaos


def test_buscar_codigos_materia_orfaos_retorna_lista_de_codigos():
    cursor = MagicMock()
    cursor.fetchall.return_value = [("170530",), ("172059",)]
    conn = MagicMock()
    conn.cursor.return_value = cursor

    codigos = buscar_codigos_materia_orfaos(conn)

    assert codigos == ["170530", "172059"]
    sql = cursor.execute.call_args[0][0]
    assert "senado_votacoes.silver.fila_materias_detalhe" in sql
    # Tarefa de ingestão não lê o Gold: a camada analítica existe para consumo, e a
    # dependência desta tarefa é declarada numa view de controle da Silver.
    assert "senado_votacoes.gold." not in sql
    cursor.close.assert_called_once()
