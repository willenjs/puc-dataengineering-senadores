"""As três filas de controle da Silver, lidas como arquivo.

As tarefas Python do Job (gap-fill, scoring por LLM e busca de status) descobrem o que
fazer lendo uma view de controle da Silver. Os filtros que antes moravam no SQL embutido
em cada script agora moram nestes arquivos, então é aqui que a proteção contra invertê-los
tem de viver -- `tests/test_run_llm_scoring.py` já não vê esse SQL.
"""
from pathlib import Path

import pytest

TRANSFORMACOES = Path(__file__).resolve().parents[1] / "lakeflow" / "transformations"
FILAS = ["fila_materias_detalhe", "fila_materias_pontuacao", "fila_processos_status"]


def ler(nome: str) -> str:
    return (TRANSFORMACOES / f"silver_{nome}.sql").read_text(encoding="utf-8")


@pytest.mark.parametrize("nome", FILAS)
def test_fila_e_uma_view_da_silver(nome):
    sql = ler(nome)
    assert f"CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.silver.{nome} (" in sql
    assert "COMMENT '" in sql


@pytest.mark.parametrize("nome", FILAS)
def test_fila_nao_le_o_gold(nome):
    # Uma fila que lesse o Gold recriaria exatamente a dependência que ela existe para
    # remover: a ingestão passaria a depender da camada analítica de novo, só que com
    # um nível de indireção a mais.
    assert "senado_votacoes.gold." not in ler(nome)


def test_fila_de_detalhe_procura_o_que_falta():
    sql = ler("fila_materias_detalhe")
    assert "LEFT JOIN senado_votacoes.silver.materias" in sql
    assert "WHERE m.codigo_materia IS NULL" in sql


def test_fila_de_pontuacao_mantem_a_polaridade_de_materia_substantiva():
    # Checar só o nome da coluna não bastaria: "AND NOT t.materia_substantiva" e
    # "t.materia_substantiva = false" contêm o nome e invertem o filtro, pontuando
    # exatamente os 2/3 procedimentais que ele existe para excluir. O commit 081ac76 foi a
    # correção de um bug com essa forma (sinal invertido que passou pela revisão), então
    # aqui se afirma a polaridade, não só a presença.
    sql = ler("fila_materias_pontuacao")
    assert "AND t.materia_substantiva" in sql
    assert "NOT t.materia_substantiva" not in sql
    assert "materia_substantiva =" not in sql


def test_fila_de_pontuacao_exige_ementa_e_votacao():
    sql = ler("fila_materias_pontuacao")
    assert "WHERE m.ementa IS NOT NULL" in sql
    assert "JOIN senado_votacoes.silver.votacoes v ON v.codigo_materia = m.codigo_materia" in sql


def test_fila_de_status_so_traz_processo_de_materia_votada():
    sql = ler("fila_processos_status")
    assert "JOIN senado_votacoes.silver.votacoes v ON v.codigo_materia = m.codigo_materia" in sql
    assert "WHERE m.id_processo IS NOT NULL" in sql
