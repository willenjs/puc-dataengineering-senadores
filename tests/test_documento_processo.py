import json
from datetime import date
from pathlib import Path

import pytest

from senado_pipeline.documento_processo import (
    FONTE_COMPOSTA,
    VERIFICADAS,
    Escolha,
    candidatos,
    classificar_conteudo,
    compactar,
    escolher_documentos,
    etapa_da_votacao,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "v3" / "documentos_96.json").read_text(encoding="utf-8"))


def _doc(catalogo, id_documento):
    return next(d for d in catalogo if d["id"] == id_documento)


def test_fixture_cobre_as_96_materias_com_posicao():
    assert len(FIXTURE) == 96
    assert len({m["codigo_materia"] for m in FIXTURE}) == 96


def test_compactar_tira_espacos_acentos_e_caixa():
    assert compactar("Redação  para o turn o Suplementar") == "redacaoparaoturnosuplementar"
    assert compactar("2º turno") == "2oturno"


def test_classificar_conteudo_reproduz_todo_rotulo_verificado():
    divergencias = []
    for m in FIXTURE:
        for id_doc, t in m["textos"].items():
            if t["conteudo_verificado"] is None:
                continue
            ident = _doc(m["catalogo"], int(id_doc))["identificacao"] or ""
            obtido = classificar_conteudo(t["inicio"], t["chars"], t["paginas"], ident)
            # CASO_B é rótulo de papel, não de conteúdo: o conteúdo daquele PDF é TEXTO.
            esperado = t["conteudo_verificado"]
            if esperado == "CASO_B_SUBSTITUTIVO":
                continue
            # TEXTO e PARECER_ANALISE nunca foram distinguidos na verificação, porque nenhum dos
            # dois é fonte: o rótulo antigo chamava de TEXTO 35 pareceres (catálogo PARECER, com
            # relatório, análise e voto). Aqui eles contam como uma classe só, a dos não-fonte.
            nao_fonte = {"TEXTO", "PARECER_ANALISE"}
            if esperado in nao_fonte and obtido in nao_fonte:
                continue
            if obtido != esperado:
                divergencias.append((m["materia"], id_doc, esperado, obtido))
    assert divergencias == []


def test_etapa_da_votacao_reproduz_as_96():
    divergencias = [
        (m["materia"], m["etapa_verificada"], etapa_da_votacao(m["sigla"], m["descricao_votacao"]))
        for m in FIXTURE
        if etapa_da_votacao(m["sigla"], m["descricao_votacao"]) != m["etapa_verificada"]
    ]
    assert divergencias == []


def _conteudo_de_fixture(materia):
    def conteudo_de(doc):
        t = materia["textos"].get(str(doc["id"]))
        if t is None:
            raise KeyError(f"{materia['materia']}: documento {doc['id']} sem texto na fixture")
        return classificar_conteudo(t["inicio"], t["chars"], t["paginas"], doc.get("identificacao") or "")
    return conteudo_de


def test_escolher_documentos_reproduz_a_escolha_verificada_nas_96():
    divergencias = []
    for m in FIXTURE:
        escolha = escolher_documentos(
            m["codigo_materia"], m["sigla"], m["etapa_verificada"],
            date.fromisoformat(m["data_votacao"]), m["catalogo"], _conteudo_de_fixture(m),
        )
        esperado = Escolha(m["esperado"]["fonte"], tuple(m["esperado"]["ids_documento"]))
        if escolha != esperado:
            divergencias.append((m["materia"], esperado, escolha))
    assert divergencias == []


def test_distribuicao_das_fontes_bate_com_a_spec():
    fontes = {}
    for m in FIXTURE:
        fontes[m["esperado"]["fonte"]] = fontes.get(m["esperado"]["fonte"], 0) + 1
    assert fontes[FONTE_COMPOSTA] == 5
    assert fontes["INICIAL_VERIFICADO"] == 8
    assert fontes["CASO_B_SUBSTITUTIVO"] == 1


def test_verificadas_sao_as_nove_excecoes_da_spec():
    assert len(VERIFICADAS) == 9
    assert VERIFICADAS["166053"] == Escolha("CASO_B_SUBSTITUTIVO", (9844178,))


def test_candidatos_respeita_a_janela_de_30_dias_e_pega_plv_de_qualquer_data():
    catalogo = [
        {"id": 1, "siglaTipo": "PARECER_REDACAO", "identificacao": "P.S 1", "dataRecebimento": "2024-01-10"},
        {"id": 2, "siglaTipo": "PARECER_REDACAO", "identificacao": "P.S 2", "dataRecebimento": "2024-02-10"},
        {"id": 3, "siglaTipo": "PARECER", "identificacao": "P.S 3", "dataRecebimento": "2024-01-09"},
        {"id": 4, "siglaTipo": "PROJETO_LEI_CONVERSAO", "identificacao": "Autógrafo aprovado na Câmara", "dataRecebimento": "2024-01-09"},
        {"id": 5, "siglaTipo": "PROJETO_LEI_ORDINARIA", "identificacao": "PL 1/2020", "dataRecebimento": "2020-01-01"},
        {"id": 6, "siglaTipo": "PROJETO_LEI_ORDINARIA", "identificacao": "Autógrafo - PL 1/2020", "dataRecebimento": "2024-01-15"},
    ]
    finais, inicial = candidatos(catalogo, date(2024, 1, 10))
    assert {d["id"] for d in finais} == {1, 4, 6}
    assert [d["id"] for d in inicial] == [5]


def test_sem_documento_verificavel_devolve_none():
    catalogo = [{"id": 5, "siglaTipo": "PROJETO_LEI_ORDINARIA", "identificacao": "PL 1/2020", "dataRecebimento": "2020-01-01"}]
    assert escolher_documentos("999999", "PL", "TEXTO", date(2024, 1, 10), catalogo, lambda d: "TEXTO") is None


def test_empate_de_data_escolhe_o_maior_id():
    catalogo = [
        {"id": 100, "siglaTipo": "PARECER_REDACAO", "identificacao": "P.S 100", "dataRecebimento": "2024-07-03"},
        {"id": 102, "siglaTipo": "PARECER_REDACAO", "identificacao": "P.S 102", "dataRecebimento": "2024-07-03"},
    ]
    escolha = escolher_documentos("1", "PL", "TEXTO", date(2024, 7, 3), catalogo, lambda d: "RF_TEXTO")
    assert escolha == Escolha("RF_TEXTO", (102,))
