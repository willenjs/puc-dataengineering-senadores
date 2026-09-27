import hashlib

import pytest

from senado_pipeline.llm_scorer import (
    LLMResponseError,
    already_scored,
    build_prompt,
    construir_prompt,
    parse_llm_response,
    score_materia,
)


def test_build_prompt_inclui_a_ementa():
    prompt = build_prompt("Institui o auxílio-gás para famílias de baixa renda.")
    assert "Institui o auxílio-gás para famílias de baixa renda." in prompt


def test_parse_llm_response_aceita_json_valido():
    raw = (
        '{"nota_pobre": 0.8, "justificativa_pobre": "Beneficia famílias pobres.", '
        '"nota_classe_media": 0.1, "justificativa_classe_media": "Efeito neutro.", '
        '"nota_rico": -0.2, "justificativa_rico": "Pequeno efeito negativo."}'
    )
    resultado = parse_llm_response(raw)
    assert resultado == {
        "nota_pobre": 0.8,
        "justificativa_pobre": "Beneficia famílias pobres.",
        "nota_classe_media": 0.1,
        "justificativa_classe_media": "Efeito neutro.",
        "nota_rico": -0.2,
        "justificativa_rico": "Pequeno efeito negativo.",
    }


def test_parse_llm_response_aceita_json_envolto_em_cerca_markdown():
    raw = (
        '```json\n{"nota_pobre": 0.8, "justificativa_pobre": "x", '
        '"nota_classe_media": 0.1, "justificativa_classe_media": "y", '
        '"nota_rico": -0.2, "justificativa_rico": "z"}\n```'
    )
    resultado = parse_llm_response(raw)
    assert resultado["nota_pobre"] == 0.8
    assert resultado["justificativa_rico"] == "z"


def test_parse_llm_response_rejeita_json_invalido():
    with pytest.raises(LLMResponseError):
        parse_llm_response("isso não é json")


def test_parse_llm_response_rejeita_campo_ausente():
    with pytest.raises(LLMResponseError):
        parse_llm_response('{"nota_pobre": 0, "justificativa_pobre": "x"}')


def test_parse_llm_response_rejeita_nota_fora_do_intervalo():
    raw = (
        '{"nota_pobre": 5, "justificativa_pobre": "x", '
        '"nota_classe_media": 0, "justificativa_classe_media": "y", '
        '"nota_rico": 0, "justificativa_rico": "z"}'
    )
    with pytest.raises(LLMResponseError):
        parse_llm_response(raw)


def test_parse_llm_response_rejeita_json_valido_mas_nao_dict():
    """JSON válido que não é um objeto (array, null, número, string) deve lançar LLMResponseError."""
    with pytest.raises(LLMResponseError):
        parse_llm_response("[]")
    with pytest.raises(LLMResponseError):
        parse_llm_response("null")
    with pytest.raises(LLMResponseError):
        parse_llm_response("42")
    with pytest.raises(LLMResponseError):
        parse_llm_response('"hello"')


class FakeLLMClient:
    def __init__(self, respostas):
        self._respostas = list(respostas)

    def complete(self, prompt):
        return self._respostas.pop(0)


RESPOSTA_OK = (
    '{"nota_pobre": 0.5, "justificativa_pobre": "a", '
    '"nota_classe_media": 0.2, "justificativa_classe_media": "b", '
    '"nota_rico": -0.1, "justificativa_rico": "c"}'
)


def test_score_materia_retorna_ok_na_primeira_tentativa():
    cliente = FakeLLMClient([RESPOSTA_OK])
    resultado = score_materia({"codigo_materia": "123", "ementa": "Ementa qualquer"}, "v1", cliente)
    assert resultado["status"] == "ok"
    assert resultado["nota_pobre"] == 0.5
    assert resultado["justificativa_pobre"] == "a"
    assert resultado["codigo_materia"] == "123"
    assert resultado["prompt_version"] == "v1"


def test_score_materia_tenta_de_novo_apos_resposta_malformada():
    cliente = FakeLLMClient(["resposta quebrada", RESPOSTA_OK])
    resultado = score_materia({"codigo_materia": "123", "ementa": "Ementa qualquer"}, "v1", cliente)
    assert resultado["status"] == "ok"


def test_score_materia_marca_needs_review_apos_duas_falhas():
    cliente = FakeLLMClient(["quebrado 1", "quebrado 2"])
    resultado = score_materia({"codigo_materia": "123", "ementa": "Ementa qualquer"}, "v1", cliente)
    assert resultado["status"] == "needs_review"
    assert resultado["nota_pobre"] is None
    assert resultado["justificativa_pobre"] is None


def test_already_scored():
    existentes = {("123", "texto", "v1", 1)}
    assert already_scored("123", "v1", 1, existentes) is True
    assert already_scored("456", "v1", 1, existentes) is False


def test_already_scored_distingue_amostras():
    """A chave passou a ser (matéria, versão, amostra) porque a mesma matéria é pontuada
    mais de uma vez na mesma versão: o modelo é um avaliador estocástico, e sem o índice
    de amostra uma segunda rodada seria pulada como se já estivesse pronta."""
    existentes = {("123", "texto", "v2", 1)}
    assert already_scored("123", "v2", 1, existentes) is True
    assert already_scored("123", "v2", 2, existentes) is False


MATERIA_V2 = {
    "codigo_materia": "123",
    "ementa": "Altera a Lei 8.212/1991 para elevar a alíquota patronal do setor financeiro.",
    "sigla": "PLP",
    "numero": "68",
    "ano": 2024,
    "tipo_descricao": "Projeto de Lei Complementar",
    "autor": "Senador Fulano de Tal",
}


def test_construir_prompt_v1_ignora_o_contexto_extra():
    # O prompt v1 é congelado: tudo que já foi pontuado com v1 tem que continuar
    # reproduzível byte a byte, então o contexto extra da matéria não pode vazar nele.
    prompt = construir_prompt(MATERIA_V2, "v1")
    assert prompt == build_prompt(MATERIA_V2["ementa"])
    assert "PLP" not in prompt
    assert "Fulano" not in prompt


def test_construir_prompt_v2_inclui_tipo_numero_ano_e_ementa_sem_autor():
    prompt = construir_prompt(MATERIA_V2, "v2")
    assert MATERIA_V2["ementa"] in prompt
    assert "PLP" in prompt
    assert "68" in prompt
    assert "2024" in prompt
    assert "Projeto de Lei Complementar" in prompt
    # O autor fica de fora de propósito: nome e partido de quem propôs são pista ideológica, e o
    # índice compara o voto dos senadores com estas notas -- ver o comentário em llm_scorer.py.
    assert "Senador Fulano de Tal" not in prompt
    assert "Autor:" not in prompt


def test_construir_prompt_v2_pede_quem_ganha_e_quem_perde_dentro_do_json():
    prompt = construir_prompt(MATERIA_V2, "v2")
    assert "ganha" in prompt and "perde" in prompt
    # A análise tem de ser a PRIMEIRA chave DENTRO do esqueleto JSON. Procurar só o nome no prompt
    # não serve: a linha em prosa acima do esqueleto também contém "analise_distributiva":, então
    # a asserção passaria mesmo se a chave sumisse do JSON ou se a análise fosse pedida em prosa.
    inicio_json = prompt.index("{\n")
    assert prompt.index('"analise_distributiva":', inicio_json) < prompt.index('"nota_pobre":', inicio_json)


def test_construir_prompt_v2_mantem_as_seis_chaves_congeladas():
    prompt = construir_prompt(MATERIA_V2, "v2")
    for chave in (
        "nota_pobre", "justificativa_pobre",
        "nota_classe_media", "justificativa_classe_media",
        "nota_rico", "justificativa_rico",
    ):
        assert chave in prompt


def test_construir_prompt_rejeita_versao_desconhecida():
    with pytest.raises(ValueError, match="v99"):
        construir_prompt(MATERIA_V2, "v99")


def test_score_materia_ignora_chave_extra_da_v2():
    resposta = (
        '{"analise_distributiva": "Setor financeiro arca com o custo.", '
        '"nota_pobre": 0.4, "justificativa_pobre": "a", '
        '"nota_classe_media": 0.1, "justificativa_classe_media": "b", '
        '"nota_rico": -0.6, "justificativa_rico": "c"}'
    )
    resultado = score_materia(MATERIA_V2, "v2", FakeLLMClient([resposta]))
    assert resultado["status"] == "ok"
    assert resultado["amostra"] == 1
    assert resultado["codigo_materia"] == "123"
    assert resultado["prompt_version"] == "v2"
    assert resultado["nota_rico"] == -0.6
    # A chave extra não vai para o Bronze: o payload gravado mantém o contrato congelado.
    assert set(resultado) == {
        "codigo_materia", "prompt_version", "amostra", "status",
        "nota_pobre", "justificativa_pobre",
        "nota_classe_media", "justificativa_classe_media",
        "nota_rico", "justificativa_rico",
    }


class ClienteQueGravaPrompt:
    """Fake que guarda o prompt recebido e devolve uma resposta válida."""

    def __init__(self):
        self.prompts = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return RESPOSTA_OK


def test_score_materia_envia_o_prompt_da_versao_pedida():
    cliente_v2 = ClienteQueGravaPrompt()
    score_materia(MATERIA_V2, "v2", cliente_v2)
    assert cliente_v2.prompts == [construir_prompt(MATERIA_V2, "v2")]
    assert "PLP" in cliente_v2.prompts[0]

    cliente_v1 = ClienteQueGravaPrompt()
    score_materia(MATERIA_V2, "v1", cliente_v1)
    assert cliente_v1.prompts == [build_prompt(MATERIA_V2["ementa"])]


def test_prompt_v1_continua_byte_a_byte_identico_ao_de_antes_da_v2():
    # Hash do prompt v1 calculado a partir do commit c911092, anterior a toda esta branch. Se esta
    # asserção falhar, o prompt v1 mudou e nenhuma nota v1 já gravada é mais reproduzível.
    referencia = "Ementa de referência para fixar o prompt v1."
    digest = hashlib.sha256(build_prompt(referencia).encode("utf-8")).hexdigest()
    assert digest == "e61540286c3b77ceed6575a058a05e677dbd0be86eecf703a166a4ceedc017d1"


# --- amostra e trilha da resposta crua (decisões 1.2 e 4.4) ---


def test_score_materia_marca_a_amostra_no_resultado():
    cliente = FakeLLMClient([RESPOSTA_OK])
    resultado = score_materia({"codigo_materia": "123", "ementa": "E"}, "v2", cliente, amostra=2)
    assert resultado["amostra"] == 2


def test_score_materia_usa_amostra_1_por_padrao():
    """Os arquivos v1/v2 já gravados não têm o campo; 1 é a leitura correta deles."""
    cliente = FakeLLMClient([RESPOSTA_OK])
    resultado = score_materia({"codigo_materia": "123", "ementa": "E"}, "v2", cliente)
    assert resultado["amostra"] == 1


def test_score_materia_registra_a_resposta_crua_de_cada_tentativa():
    """A resposta crua é a trilha de auditoria da nota, e auditoria não pode depender de
    pagar de novo. A primeira tentativa aqui é ilegível: é justamente a que some se só a
    resposta aproveitada for registrada."""
    registradas = []
    cliente = FakeLLMClient(["nao e json", RESPOSTA_OK])

    resultado = score_materia(
        {"codigo_materia": "123", "ementa": "E"},
        "v2",
        cliente,
        amostra=1,
        registrar_resposta=lambda texto, tentativa: registradas.append((tentativa, texto)),
    )

    assert resultado["status"] == "ok"
    assert registradas == [(1, "nao e json"), (2, RESPOSTA_OK)]


def test_score_materia_registra_as_duas_respostas_quando_vira_needs_review():
    registradas = []
    cliente = FakeLLMClient(["quebrado 1", "quebrado 2"])

    resultado = score_materia(
        {"codigo_materia": "123", "ementa": "E"},
        "v2",
        cliente,
        registrar_resposta=lambda texto, tentativa: registradas.append((tentativa, texto)),
    )

    assert resultado["status"] == "needs_review"
    assert registradas == [(1, "quebrado 1"), (2, "quebrado 2")]


def test_score_materia_sem_registrador_continua_funcionando():
    cliente = FakeLLMClient([RESPOSTA_OK])
    resultado = score_materia({"codigo_materia": "123", "ementa": "E"}, "v1", cliente)
    assert resultado["status"] == "ok"


def test_score_materia_nao_grava_a_analise_no_bronze_mas_ela_sobrevive_na_trilha():
    """O parser descarta analise_distributiva para preservar o contrato congelado do
    Bronze. A trilha da 4.4 é o único lugar onde esse raciocínio continua existindo."""
    resposta = (
        '{"analise_distributiva": "quem ganha e quem perde", '
        '"nota_pobre": 0.5, "justificativa_pobre": "a", '
        '"nota_classe_media": 0.2, "justificativa_classe_media": "b", '
        '"nota_rico": -0.1, "justificativa_rico": "c"}'
    )
    registradas = []
    cliente = FakeLLMClient([resposta])

    resultado = score_materia(
        {"codigo_materia": "123", "ementa": "E"},
        "v2",
        cliente,
        registrar_resposta=lambda texto, tentativa: registradas.append(texto),
    )

    assert "analise_distributiva" not in resultado
    assert "analise_distributiva" in registradas[0]


from senado_pipeline.llm_scorer import ESQUEMA_SAIDA_V3, REQUIRED_KEYS, VERSOES_V3, montar_conteudo_v3

MATERIA_V3 = {"codigo_materia": "1", "ementa": "Institui X.", "sigla": "PLP", "numero": "00068",
              "ano": 2024, "tipo_descricao": "Projeto de Lei Complementar"}


def test_v3_documento_vem_primeiro_em_bloco_com_cache_de_uma_hora():
    conteudo = montar_conteudo_v3(MATERIA_V3, [{"papel": "texto_votado", "texto": "Art. 1º ..."}], "v3-com-empurrao")
    assert len(conteudo) == 2
    assert conteudo[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert "<texto_votado>\nArt. 1º ...\n</texto_votado>" in conteudo[0]["text"]
    assert "cache_control" not in conteudo[1]
    assert "analista legislativo" in conteudo[1]["text"]


def test_v3_as_duas_variantes_compartilham_o_bloco_em_cache_e_diferem_so_no_empurrao():
    docs = [{"papel": "texto_votado", "texto": "Art. 1º ..."}]
    com = montar_conteudo_v3(MATERIA_V3, docs, "v3-com-empurrao")
    sem = montar_conteudo_v3(MATERIA_V3, docs, "v3-sem-empurrao")
    assert com[0] == sem[0]
    assert "quase sempre tem efeito distributivo" in com[1]["text"]
    assert "quase sempre tem efeito distributivo" not in sem[1]["text"]
    assert "dê a mesma nota aos três" in com[1]["text"] and "dê a mesma nota aos três" in sem[1]["text"]


def test_v3_insumo_composto_identifica_os_dois_documentos():
    docs = [{"papel": "texto_recebido", "texto": "A"}, {"papel": "emendas_do_senado", "texto": "B"}]
    conteudo = montar_conteudo_v3(MATERIA_V3, docs, "v3-sem-empurrao")
    assert "<texto_recebido>\nA\n</texto_recebido>" in conteudo[0]["text"]
    assert "<emendas_do_senado>\nB\n</emendas_do_senado>" in conteudo[0]["text"]
    assert "emendas aplicadas" in conteudo[1]["text"]


def test_v3_versao_desconhecida_e_erro():
    with pytest.raises(ValueError):
        montar_conteudo_v3(MATERIA_V3, [{"papel": "texto_votado", "texto": "x"}], "v3")


def test_esquema_v3_exige_as_seis_chaves_congeladas_e_a_analise():
    assert set(ESQUEMA_SAIDA_V3["required"]) == REQUIRED_KEYS | {"analise_distributiva"}
    assert ESQUEMA_SAIDA_V3["additionalProperties"] is False
    assert set(VERSOES_V3) == {"v3-com-empurrao", "v3-sem-empurrao"}


from senado_pipeline.llm_scorer import VERSAO_EMENDA, montar_conteudo_emenda


def test_emenda_poe_o_texto_base_em_cache_e_a_emenda_fora_dele():
    conteudo = montar_conteudo_emenda(MATERIA_V3, [{"papel": "texto_base", "texto": "Art. 30 ..."}],
                                      "Dê-se ao art. 30 a seguinte redação: ...")
    assert conteudo[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert "<texto_base>\nArt. 30 ...\n</texto_base>" in conteudo[0]["text"]
    assert "cache_control" not in conteudo[1]
    assert "<emenda>\nDê-se ao art. 30 a seguinte redação: ...\n</emenda>" in conteudo[1]["text"]


def test_emenda_pergunta_pelo_efeito_de_aprovar_e_nao_pelo_texto_base():
    conteudo = montar_conteudo_emenda(MATERIA_V3, [{"papel": "texto_base", "texto": "x"}], "y")
    instrucoes = conteudo[1]["text"]
    assert "aprovar a emenda" in instrucoes
    assert "em relação ao texto-base" in instrucoes
    assert "quase sempre tem efeito distributivo" in instrucoes  # o empurrão fiscal, decidido em 2026-09-18
    assert VERSAO_EMENDA == "emenda-v1"


def test_emenda_com_base_composta_identifica_os_dois_documentos():
    conteudo = montar_conteudo_emenda(
        MATERIA_V3,
        [{"papel": "texto_recebido", "texto": "A"}, {"papel": "emendas_do_senado", "texto": "B"}], "y")
    assert "<texto_recebido>\nA\n</texto_recebido>" in conteudo[0]["text"]
    assert "<emendas_do_senado>\nB\n</emendas_do_senado>" in conteudo[0]["text"]
