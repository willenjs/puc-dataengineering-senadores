"""Pontuação v3 pela API em lote (Message Batches): lógica pura, sem rede.

Uma amostra é a chave (matéria, versão, amostra); um pedido é uma tentativa de preenchê-la.
Resposta ilegível não vira "uma amostra a menos" (spec §6): a MESMA amostra é pedida de novo, até
PEDIDOS_POR_AMOSTRA_POR_RODADA vezes na rodada, e a matéria só é publicada com as 9 legíveis.
"""
from __future__ import annotations

from collections import Counter

from senado_pipeline.llm_scorer import ESQUEMA_SAIDA_V3, LLMResponseError, parse_llm_response

MODELO_V3 = "claude-sonnet-5"
# Com texto integral o raciocínio cresce; estourar max_tokens devolve JSON truncado. O lote não
# tem streaming nem o limite de tempo de uma chamada síncrona, então o teto pode ser folgado:
# só se paga o que o modelo de fato gera.
MAX_TOKENS_V3 = 16000
AMOSTRAS_V3 = 9
PEDIDOS_POR_AMOSTRA_POR_RODADA = 4  # a primeira e até 3 repetições (decisão de 2026-09-17)
LIMITE_TOKENS_ENTRADA = 400_000  # decisão de 2026-09-17: a PLP 68/2024 tem 334.913 tokens reais
# Preço de lista do modelo, em US$ por milhão de tokens. Confirmado em 2026-09-17 na página do
# modelo e na de preços: entrada 2, saída 10, gravação de cache de 1 h 4 (2x), leitura 0,20 (0,1x);
# o lote dá 50% e se soma ao cache; a janela de 1M tokens não tem preço de contexto longo.
PRECO_ENTRADA_POR_MILHAO = 2.0
PRECO_SAIDA_POR_MILHAO = 10.0
DESCONTO_LOTE = 0.5
MULTIPLICADOR_GRAVACAO_CACHE_1H = 2.0
MULTIPLICADOR_GRAVACAO_CACHE_5M = 1.25
MULTIPLICADOR_LEITURA_CACHE = 0.1
TOKENS_INSTRUCOES = 700  # instruções do prompt v3, fora do bloco em cache
LIMIAR_SINCRONO = 10_000  # tokens de entrada; ver modo_por_tamanho


def id_pedido(codigo_materia: str, prompt_version: str, amostra: int, tentativa: int,
              numero_objeto: str = "texto") -> str:
    """O objeto entra no id porque uma matéria pode ter três emendas destacadas, e cada pedido do
    lote precisa de um custom_id único (máximo de 64 caracteres, [a-zA-Z0-9_-])."""
    alvo = codigo_materia if numero_objeto == "texto" else f"{codigo_materia}e{numero_objeto}"
    return f"{alvo}_{prompt_version}_a{amostra}_t{tentativa}"


def _chave(p: dict) -> tuple[str, str, str, int]:
    return (str(p["codigo_materia"]), str(p.get("numero_objeto") or "texto"),
            p["prompt_version"], int(p["amostra"]))


def contar_tentativas(registros: list[dict], rodada: str) -> tuple[dict, dict]:
    total, na_rodada = Counter(), Counter()
    for r in registros:
        for p in r.get("pedidos", []):
            total[_chave(p)] += 1
            if r.get("rodada") == rodada:
                na_rodada[_chave(p)] += 1
    return dict(total), dict(na_rodada)


def planejar_pedidos(objetos, versoes, amostras, prontas, total, na_rodada):
    """`objetos` é uma lista de (codigo_materia, numero_objeto); "texto" é o objeto do texto da
    matéria. As chaves de `prontas`, `total` e `na_rodada` são (matéria, objeto, versão, amostra)."""
    pedidos, esgotadas = [], []
    for alvo in objetos:
        codigo, numero_objeto = (alvo if isinstance(alvo, tuple) else (alvo, "texto"))
        for versao in versoes:
            for amostra in range(1, amostras + 1):
                chave = (str(codigo), str(numero_objeto), versao, amostra)
                if chave in prontas:
                    continue
                if na_rodada.get(chave, 0) >= PEDIDOS_POR_AMOSTRA_POR_RODADA:
                    esgotadas.append(chave)
                    continue
                pedidos.append({"codigo_materia": str(codigo), "numero_objeto": str(numero_objeto),
                                "prompt_version": versao, "amostra": amostra,
                                "tentativa": total.get(chave, 0) + 1})
    return pedidos, esgotadas


def sem_cache(conteudo: list[dict]) -> list[dict]:
    """O conteúdo sem marcação de cache, para o lote. O piloto de 2026-09-17 mediu que, dentro de
    um lote, o cache quase não é lido (1 de 17 pedidos, mesmo com o cache gravado antes por uma
    chamada comum), e cada pedido que não o acha paga a gravação, o dobro da entrada."""
    return [{k: v for k, v in bloco.items() if k != "cache_control"} for bloco in conteudo]


def montar_pedido(pedido: dict, conteudo: list[dict]) -> dict:
    return {
        "custom_id": id_pedido(pedido["codigo_materia"], pedido["prompt_version"], pedido["amostra"],
                               pedido["tentativa"], pedido.get("numero_objeto") or "texto"),
        "params": {
            "model": MODELO_V3,
            "max_tokens": MAX_TOKENS_V3,
            "messages": [{"role": "user", "content": conteudo}],
            "output_config": {"format": {"type": "json_schema", "schema": ESQUEMA_SAIDA_V3}},
        },
    }


def texto_da_mensagem(message) -> str:
    for bloco in getattr(message, "content", None) or []:
        texto = getattr(bloco, "text", None)
        if texto is not None:
            return texto
    return ""


def interpretar_resposta(texto: str) -> dict | None:
    try:
        return parse_llm_response(texto)
    except LLMResponseError:
        return None


def custo_usd(uso: dict, lote: bool = True) -> float:
    pi, po = PRECO_ENTRADA_POR_MILHAO, PRECO_SAIDA_POR_MILHAO
    detalhe = uso.get("cache_creation") or {}
    g1h = detalhe.get("ephemeral_1h_input_tokens")
    g5m = detalhe.get("ephemeral_5m_input_tokens")
    if g1h is None and g5m is None:
        # Sem o detalhe, trata toda gravação como de 1 hora: é a mais cara, então o custo
        # apurado nunca fica abaixo do real.
        g1h, g5m = uso.get("cache_creation_input_tokens") or 0, 0
    bruto = (
        (uso.get("input_tokens") or 0) * pi
        + (g1h or 0) * pi * MULTIPLICADOR_GRAVACAO_CACHE_1H
        + (g5m or 0) * pi * MULTIPLICADOR_GRAVACAO_CACHE_5M
        + (uso.get("cache_read_input_tokens") or 0) * pi * MULTIPLICADOR_LEITURA_CACHE
        + (uso.get("output_tokens") or 0) * po
    )
    return (DESCONTO_LOTE if lote else 1.0) * bruto / 1e6


def estimar_custo(tokens_por_materia, pedidos, saida_media, modo) -> float:
    """Estimativa antes de enviar.

    "lote": sem cache, com o desconto de lote; cada pedido paga a entrada inteira uma vez.
    "sincrono": chamadas comuns, sem desconto; o primeiro pedido de cada matéria grava o cache
    (2x) e os demais o leem (0,1x). Supõe que o cache pega, o que o modo síncrono confere na
    segunda chamada de cada matéria."""
    pi, po = PRECO_ENTRADA_POR_MILHAO, PRECO_SAIDA_POR_MILHAO
    # Agrupado por MATÉRIA e não por objeto: as emendas destacadas de uma matéria têm o mesmo
    # texto-base, então gravam o cache uma vez e leem nas demais chamadas.
    por_materia = Counter(str(p["codigo_materia"]) for p in pedidos)
    bruto = 0.0
    for codigo, n in por_materia.items():
        t = tokens_por_materia[codigo]
        saida = n * saida_media * po
        if modo == "lote":
            bruto += DESCONTO_LOTE * (n * (t + TOKENS_INSTRUCOES) * pi + saida)
        elif modo == "sincrono":
            bruto += ((t * MULTIPLICADOR_GRAVACAO_CACHE_1H + TOKENS_INSTRUCOES) * pi
                      + (n - 1) * (t * MULTIPLICADOR_LEITURA_CACHE + TOKENS_INSTRUCOES) * pi + saida)
        else:
            raise ValueError(f"modo desconhecido: {modo!r}")
    return bruto / 1e6


def modo_por_tamanho(tokens_entrada: int) -> str:
    """Síncrono com cache compensa quando o documento é grande: a gravação (2x) e as 17 leituras
    (0,1x) custam menos que 18 entradas inteiras com desconto de lote, e a saída sem desconto
    pesa pouco perto disso. Com ~1.200 tokens de saída o empate fica em ~10 mil tokens."""
    return "sincrono" if tokens_entrada > LIMIAR_SINCRONO else "lote"


def gasto_da_rodada(registros: list[dict], rodada: str) -> float:
    """Custo apurado dos registros coletados, mais a estimativa dos lotes ainda em processamento:
    o teto tem de valer para o que já foi comprometido, não só para o que já foi cobrado."""
    return sum((r.get("custo_usd") if r.get("coletado") else r.get("estimativa_usd")) or 0.0
               for r in registros if r.get("rodada") == rodada)


def somar_uso(total: dict, uso: dict) -> dict:
    """Acumula o `usage` da API (inteiros e um nível de detalhe), ignorando o que não é contagem."""
    for k, v in uso.items():
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            total[k] = total.get(k, 0) + v
        elif isinstance(v, dict):
            sub = total.setdefault(k, {})
            for k2, v2 in v.items():
                if isinstance(v2, int) and not isinstance(v2, bool):
                    sub[k2] = sub.get(k2, 0) + v2
    return total
