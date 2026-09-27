import pytest

from senado_pipeline.lote_scoring import (
    AMOSTRAS_V3,
    PEDIDOS_POR_AMOSTRA_POR_RODADA,
    PRECO_ENTRADA_POR_MILHAO,
    PRECO_SAIDA_POR_MILHAO,
    contar_tentativas,
    custo_usd,
    estimar_custo,
    gasto_da_rodada,
    id_pedido,
    interpretar_resposta,
    montar_pedido,
    planejar_pedidos,
    texto_da_mensagem,
)

VERSOES = ("v3-com-empurrao", "v3-sem-empurrao")
RESPOSTA_OK = (
    '{"analise_distributiva": "x", "nota_pobre": 0.5, "justificativa_pobre": "a", '
    '"nota_classe_media": 0, "justificativa_classe_media": "b", "nota_rico": -0.2, "justificativa_rico": "c"}'
)


def test_id_pedido_e_valido_para_a_api():
    cid = id_pedido("171725", "v3-sem-empurrao", 9, 4)
    assert cid == "171725_v3-sem-empurrao_a9_t4"
    assert len(cid) <= 64


def test_planejar_pede_as_18_chaves_de_uma_materia_nova():
    pedidos, esgotadas = planejar_pedidos(["1"], VERSOES, AMOSTRAS_V3, set(), {}, {})
    assert len(pedidos) == 18 and esgotadas == []
    assert {p["tentativa"] for p in pedidos} == {1}


def test_planejar_pula_as_prontas_e_repete_a_mesma_amostra_com_tentativa_seguinte():
    prontas = {("1", "texto", "v3-com-empurrao", a) for a in range(1, 10)} | {("1", "texto", "v3-sem-empurrao", a) for a in range(1, 9)}
    total = {("1", "texto", "v3-sem-empurrao", 9): 2}
    na_rodada = {("1", "texto", "v3-sem-empurrao", 9): 2}
    pedidos, esgotadas = planejar_pedidos(["1"], VERSOES, AMOSTRAS_V3, prontas, total, na_rodada)
    assert pedidos == [{"codigo_materia": "1", "numero_objeto": "texto", "prompt_version": "v3-sem-empurrao", "amostra": 9, "tentativa": 3}]
    assert esgotadas == []


def test_planejar_esgota_a_amostra_depois_de_quatro_pedidos_na_rodada():
    chave = ("1", "texto", "v3-sem-empurrao", 9)
    prontas = {("1", "texto", v, a) for v in VERSOES for a in range(1, 10)} - {chave}
    pedidos, esgotadas = planejar_pedidos(["1"], VERSOES, AMOSTRAS_V3, prontas, {chave: 4},
                                          {chave: PEDIDOS_POR_AMOSTRA_POR_RODADA})
    assert pedidos == [] and esgotadas == [chave]


def test_contar_tentativas_separa_o_total_da_rodada():
    registros = [
        {"rodada": "piloto", "pedidos": [{"codigo_materia": "1", "prompt_version": "v", "amostra": 1, "tentativa": 1}]},
        {"rodada": "completa", "pedidos": [{"codigo_materia": "1", "prompt_version": "v", "amostra": 1, "tentativa": 2}]},
    ]
    total, na_rodada = contar_tentativas(registros, "completa")
    assert total == {("1", "texto", "v", 1): 2}
    assert na_rodada == {("1", "texto", "v", 1): 1}


def test_montar_pedido_usa_saida_estruturada_e_o_conteudo_dado():
    conteudo = [{"type": "text", "text": "doc"}]
    p = montar_pedido({"codigo_materia": "1", "prompt_version": "v3-com-empurrao", "amostra": 2, "tentativa": 1}, conteudo)
    assert p["custom_id"] == "1_v3-com-empurrao_a2_t1"
    assert p["params"]["messages"] == [{"role": "user", "content": conteudo}]
    assert p["params"]["output_config"]["format"]["type"] == "json_schema"
    assert p["params"]["model"] == "claude-sonnet-5"


def test_interpretar_resposta_legivel_e_ilegivel():
    assert interpretar_resposta(RESPOSTA_OK)["nota_rico"] == -0.2
    assert interpretar_resposta('{"analise_distributiva": "x"; "nota_pobre": 1}') is None
    assert interpretar_resposta("") is None


def test_texto_da_mensagem_pula_bloco_sem_texto():
    class Bloco:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class Msg:
        content = [Bloco(type="thinking"), Bloco(type="text", text="oi")]

    assert texto_da_mensagem(Msg()) == "oi"


def test_custo_com_desconto_de_lote_cache_de_uma_hora_e_leitura():
    uso = {"input_tokens": 1000, "output_tokens": 2000, "cache_read_input_tokens": 100_000,
           "cache_creation_input_tokens": 50_000,
           "cache_creation": {"ephemeral_1h_input_tokens": 50_000, "ephemeral_5m_input_tokens": 0}}
    esperado = 0.5 * (1000 * PRECO_ENTRADA_POR_MILHAO + 50_000 * PRECO_ENTRADA_POR_MILHAO * 2
                      + 100_000 * PRECO_ENTRADA_POR_MILHAO * 0.1 + 2000 * PRECO_SAIDA_POR_MILHAO) / 1e6
    assert custo_usd(uso) == pytest.approx(esperado)


def test_estimativa_em_lote_cobra_a_entrada_inteira_em_cada_pedido_pela_metade():
    from senado_pipeline.lote_scoring import TOKENS_INSTRUCOES
    pedidos = [{"codigo_materia": "1"}] * 18
    obtido = estimar_custo({"1": 100_000}, pedidos, saida_media=1000, modo="lote")
    esperado = 0.5 * 18 * ((100_000 + TOKENS_INSTRUCOES) * PRECO_ENTRADA_POR_MILHAO
                           + 1000 * PRECO_SAIDA_POR_MILHAO) / 1e6
    assert obtido == pytest.approx(esperado)


def test_documento_grande_vai_sincrono_e_pequeno_vai_em_lote():
    from senado_pipeline.lote_scoring import modo_por_tamanho
    pedidos = [{"codigo_materia": "1"}] * 18
    for t in (50_000, 3_000):
        lote = estimar_custo({"1": t}, pedidos, saida_media=1200, modo="lote")
        sinc = estimar_custo({"1": t}, pedidos, saida_media=1200, modo="sincrono")
        assert modo_por_tamanho(t) == ("sincrono" if sinc < lote else "lote")


def test_sem_cache_tira_so_a_marcacao():
    from senado_pipeline.lote_scoring import sem_cache
    conteudo = [{"type": "text", "text": "doc", "cache_control": {"type": "ephemeral", "ttl": "1h"}},
                {"type": "text", "text": "instr"}]
    assert sem_cache(conteudo) == [{"type": "text", "text": "doc"}, {"type": "text", "text": "instr"}]
    assert "cache_control" in conteudo[0]


def test_gasto_da_rodada_soma_so_os_lotes_coletados_da_rodada():
    registros = [
        {"rodada": "piloto", "coletado": True, "custo_usd": 1.5},
        {"rodada": "piloto", "coletado": False, "custo_usd": None, "estimativa_usd": None},
        {"rodada": "completa", "coletado": True, "custo_usd": 9.0},
    ]
    assert gasto_da_rodada(registros, "piloto") == pytest.approx(1.5)


def test_custo_de_chamada_sincrona_nao_tem_desconto_de_lote():
    uso = {"input_tokens": 0, "output_tokens": 1_000_000}
    assert custo_usd(uso, lote=False) == pytest.approx(PRECO_SAIDA_POR_MILHAO)
    assert custo_usd(uso) == pytest.approx(PRECO_SAIDA_POR_MILHAO / 2)


def test_somar_uso_acumula_inclusive_os_detalhes():
    from senado_pipeline.lote_scoring import somar_uso
    total = {}
    somar_uso(total, {"input_tokens": 1, "cache_creation": {"ephemeral_1h_input_tokens": 5}, "service_tier": "batch"})
    somar_uso(total, {"input_tokens": 2, "cache_creation": {"ephemeral_1h_input_tokens": 1}})
    assert total == {"input_tokens": 3, "cache_creation": {"ephemeral_1h_input_tokens": 6}}


def test_gasto_da_rodada_conta_a_estimativa_do_lote_ainda_nao_coletado():
    registros = [
        {"rodada": "completa", "coletado": True, "custo_usd": 0.6},
        {"rodada": "completa", "coletado": False, "custo_usd": None, "estimativa_usd": 14.0},
    ]
    assert gasto_da_rodada(registros, "completa") == pytest.approx(14.6)


def test_id_pedido_distingue_emendas_da_mesma_materia():
    assert id_pedido("160197", "emenda-v1", 1, 1, "139") == "160197e139_emenda-v1_a1_t1"
    assert id_pedido("160197", "emenda-v1", 1, 1, "147") != id_pedido("160197", "emenda-v1", 1, 1, "139")
    assert len(id_pedido("160197", "emenda-v1", 9, 4, "2223")) <= 64


def test_planejar_trata_cada_emenda_da_materia_como_objeto_proprio():
    objetos = [("160197", "139"), ("160197", "147")]
    prontas = {("160197", "139", "emenda-v1", a) for a in range(1, 10)}
    pedidos, esgotadas = planejar_pedidos(objetos, ("emenda-v1",), AMOSTRAS_V3, prontas, {}, {})
    assert esgotadas == []
    assert {p["numero_objeto"] for p in pedidos} == {"147"}
    assert len(pedidos) == 9


def test_estimativa_cobra_o_cache_uma_vez_por_materia_mesmo_com_varias_emendas():
    uma = [{"codigo_materia": "1", "numero_objeto": "139"}] * 9
    duas = uma + [{"codigo_materia": "1", "numero_objeto": "147"}] * 9
    t = {"1": 100_000}
    # A segunda emenda paga leituras de cache, não uma nova gravação: menos que o dobro.
    assert estimar_custo(t, duas, 1000, "sincrono") < 2 * estimar_custo(t, uma, 1000, "sincrono")
