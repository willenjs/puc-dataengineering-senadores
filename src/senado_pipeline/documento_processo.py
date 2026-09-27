"""Escolha do documento que contém o texto na forma votada (spec v3, seção 3).

O tipo do catálogo (`siglaTipo`) não identifica o documento: redações finais aparecem como
PARECER comum, o texto de um substitutivo da Câmara aparece como autógrafo de tipo EMENDA. Quem
identifica é o cabeçalho do PDF, lido sem espaços e sem acentos porque a extração quebra
palavras ("da s Emendas", "turn o"). A regra é uma allowlist: documento que não se encaixa em
nenhum caso não vira insumo, e matéria sem documento verificável fica sem nota.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

JANELA_DIAS = 30
CHARS_POR_PAGINA_MIN = 300
TIPOS_PARECER = {"PARECER_REDACAO", "PARECER"}
TIPOS_INICIAIS = {
    "PROJETO_LEI_ORDINARIA", "PROJETO_LEI_COMPLEMENTAR", "PROPOSTA_EMENDA_CONSTITUICAO",
    "MEDIDA_PROVISORIA", "PROJETO_RESOLUCAO", "PROJETO_DECRETO_LEGISLATIVO",
}
FONTE_COMPOSTA = "COMPOSTO_INICIAL_MAIS_EMENDAS_DO_SENADO"
# Fonte por etapa da votação de posição, em ordem de preferência (spec §3, tabela).
ORDEM_POR_ETAPA = {
    "PEC_2TURNO": ("RF_2TURNO", "RF_TEXTO", "AUT_TEXTO"),
    "SUBSTITUTIVO_1TURNO": ("RF_TURNO_SUPLEMENTAR", "RF_TEXTO", "AUT_TEXTO"),
    "TEXTO": ("RF_TEXTO", "RF_TURNO_SUPLEMENTAR", "AUT_TEXTO"),
}


@dataclass(frozen=True)
class Escolha:
    fonte: str
    ids_documento: tuple[int, ...]


# Exceções verificadas à mão, fixadas pelo id do documento verificado (spec §3). As 8 pelo
# documento inicial dependem de evidência que nenhuma regra lê (conclusão dos pareceres,
# `decisoes` das emendas, envio à sanção); a PLP 175/2024 votou o texto antes dos destaques
# que o mudaram, e o texto que ela votou é o da Emenda 45 (Substitutivo).
VERIFICADAS: dict[str, Escolha] = {
    "171481": Escolha("INICIAL_VERIFICADO", (10096124,)),  # PEC 169/2019
    "170850": Escolha("INICIAL_VERIFICADO", (10073477,)),  # PEC 14/2021
    "155131": Escolha("INICIAL_VERIFICADO", (9211194,)),   # PEC 26/2022
    "169614": Escolha("INICIAL_VERIFICADO", (9997370,)),   # PEC 66/2023, fase de retorno da Câmara
    "157888": Escolha("INICIAL_VERIFICADO", (9376825,)),   # PL 2.903/2023
    "160102": Escolha("INICIAL_VERIFICADO", (9462841,)),   # PLP 136/2023
    "162245": Escolha("INICIAL_VERIFICADO", (9552240,)),   # PLP 175/2023
    "166865": Escolha("INICIAL_VERIFICADO", (9880336,)),   # PLP 210/2024
    "166053": Escolha("CASO_B_SUBSTITUTIVO", (9844178,)),  # PLP 175/2024, Emenda 45
}


def compactar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", "", t)


def classificar_conteudo(inicio: str, chars: int, paginas: int, identificacao: str) -> str:
    """Tipo de conteúdo pelo cabeçalho. `inicio` é o texto normalizado (espaços colapsados),
    ao menos os 6000 primeiros caracteres; `chars` é o tamanho do texto inteiro."""
    if not paginas or chars / paginas < CHARS_POR_PAGINA_MIN:
        return "ILEGIVEL"
    cab = compactar(inicio[:1500])
    if re.search(r"redacaofinald[ao]s?emendas|redacaod[ao]s?emendasdosenado", cab):
        return "RF_EMENDAS"
    if "redacaoparaoturnosuplementar" in cab:
        return "RF_TURNO_SUPLEMENTAR"
    if re.search(r"redacaoparaosegundoturno|redacaoparao2oturno", cab):
        return "RF_2TURNO"
    if "redacaofinal" in cab:
        return "RF_TEXTO"
    if identificacao.lower().startswith("aut"):
        if re.search(r"emendasdosenado|emendan[o]?\d+\(correspondea", cab):
            return "AUT_EMENDAS"
        if re.search(r"decreta|promulgam|promulgo", compactar(inicio[:4000])) and re.search(
            r"art\.?1", compactar(inicio[:6000])
        ):
            return "AUT_TEXTO"
        return "AUT_OUTRO"
    # Parecer com análise: ao menos dois dos títulos "I – RELATÓRIO", "II – ANÁLISE", "III – VOTO",
    # com o numeral isolado. Sem o isolamento, "VI – relatório" de um inciso casava.
    secoes = set(re.findall(r"(?<![a-z])(i|ii|iii)\s*[–-]\s*(?:relat[óo]rio|an[áa]lise|voto)\b", inicio.lower()))
    if len(secoes) >= 2:
        return "PARECER_ANALISE"
    return "TEXTO"


def etapa_da_votacao(sigla: str, descricao: str) -> str:
    """Etapa da votação de posição. A posição é a votação de texto mais recente; numa PEC ela
    é o 2º turno, salvo quando a descrição diz o contrário."""
    c = compactar(descricao or "")
    if sigla == "PEC":
        return "TEXTO" if re.search(r"1oturno|primeiroturno", c) else "PEC_2TURNO"
    if re.search(r"emenda(n[o.]*)?[\d.]+\(substitutivo", c):
        return "SUBSTITUTIVO_1TURNO"
    return "TEXTO"


def _data(doc: dict) -> date | None:
    bruto = str(doc.get("dataRecebimento") or "")[:10]
    return date.fromisoformat(bruto) if bruto else None


def candidatos(catalogo: list[dict], data_votacao: date) -> tuple[list[dict], list[dict]]:
    """(finais, inicial). Finais: pareceres e autógrafos da votação até 30 dias depois, e todo
    PLV (o autógrafo do PLV pode chegar da Câmara na véspera da votação no Senado). Inicial: o
    documento de proposição mais antigo."""
    fim = data_votacao + timedelta(days=JANELA_DIAS)
    finais = []
    for d in catalogo:
        dr = _data(d)
        ident = str(d.get("identificacao") or "")
        if d.get("siglaTipo") == "PROJETO_LEI_CONVERSAO":
            finais.append(d)
        elif dr and data_votacao <= dr <= fim and (
            d.get("siglaTipo") in TIPOS_PARECER or re.match(r"(?i)^aut[óo]grafo\s*-", ident)
        ):
            finais.append(d)
    iniciais = sorted((d for d in catalogo if d.get("siglaTipo") in TIPOS_INICIAIS),
                      key=lambda d: d.get("dataRecebimento") or "")
    return finais, iniciais[:1]


def _mais_recente(docs: list[dict]) -> dict:
    """O mais recente; empate de data resolvido pelo maior id. Dois documentos do mesmo tipo no
    mesmo dia são o original e a republicação, e vale a republicação: no PL 2.308/2023 as duas
    redações finais das Emendas do Senado saíram em 2024-07-03, e a P.S 102 (id maior) traz 11
    emendas e contém 97% da P.S 100. Sem o desempate a escolha dependia da ordem do catálogo."""
    return max(docs, key=lambda d: ((d.get("dataRecebimento") or ""), int(d["id"])))


def escolher_documentos(
    codigo_materia: str,
    sigla: str,
    etapa: str,
    data_votacao: date,
    catalogo: list[dict],
    conteudo_de: Callable[[dict], str],
) -> Escolha | None:
    """Documento(s) com o texto na forma votada, ou None quando não há fonte verificável.

    `conteudo_de(doc)` devolve o tipo de conteúdo do documento (baixar e classificar é de
    quem chama); só é chamado para candidatos, então o custo de rede fica nos candidatos."""
    if codigo_materia in VERIFICADAS:
        return VERIFICADAS[codigo_materia]
    finais, inicial = candidatos(catalogo, data_votacao)
    classificados = [(d, conteudo_de(d)) for d in finais]
    for tipo in ORDEM_POR_ETAPA[etapa]:
        cs = [d for d, c in classificados if c == tipo]
        if cs:
            return Escolha(tipo, (int(_mais_recente(cs)["id"]),))
    if sigla == "MPV":
        plv = [d for d, c in classificados if d.get("siglaTipo") == "PROJETO_LEI_CONVERSAO" and c != "ILEGIVEL"]
        if plv:
            return Escolha("PLV", (int(_mais_recente(plv)["id"]),))
    # Projeto da Câmara emendado pelo Senado: o votado é o texto recebido mais as emendas.
    # A redação final das emendas é preferida ao autógrafo delas.
    for tipo in ("RF_EMENDAS", "AUT_EMENDAS"):
        emendas = [d for d, c in classificados if c == tipo]
        if emendas and inicial and conteudo_de(inicial[0]) != "ILEGIVEL":
            return Escolha(FONTE_COMPOSTA, (int(inicial[0]["id"]), int(_mais_recente(emendas)["id"])))
    return None
