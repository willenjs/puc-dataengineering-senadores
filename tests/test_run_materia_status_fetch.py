from unittest.mock import MagicMock

from scripts.run_materia_status_fetch import buscar_id_processos_votados


def test_buscar_id_processos_votados_retorna_lista_de_ids():
    cursor = MagicMock()
    cursor.fetchall.return_value = [("8349431",), ("9106586",)]
    conn = MagicMock()
    conn.cursor.return_value = cursor

    ids = buscar_id_processos_votados(conn)

    assert ids == ["8349431", "9106586"]
    sql = cursor.execute.call_args[0][0]
    assert "senado_votacoes.silver.fila_processos_status" in sql
    # Tarefa de ingestão não lê o Gold: a camada analítica existe para consumo, e a
    # dependência desta tarefa é declarada numa view de controle da Silver.
    assert "senado_votacoes.gold." not in sql
    cursor.close.assert_called_once()
