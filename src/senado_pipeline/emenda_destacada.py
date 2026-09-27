"""Texto-base de uma emenda destacada (spec da v3, seção 12).

A nota de uma emenda é a de um delta: o efeito de APROVAR a emenda em relação ao texto como
estava quando o destaque foi votado. Qual é esse texto depende do resultado da votação, e por
isso `fact_votacao.resultado` é pré-requisito: a emenda REJEITADA não está no texto final da
etapa, que serve de base; a APROVADA está, e usar o texto final como base mediria a diferença
entre o texto e ele mesmo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from senado_pipeline.documento_processo import Escolha


@dataclass(frozen=True)
class BaseEmenda:
    fonte: str
    ids_documento: tuple[int, ...]
    evidencia: str
    # Número da emenda destacada cujo bloco tem de SAIR do documento de emendas antes de virar
    # base. Uma emenda aprovada está dentro da redação final das Emendas do Senado, e deixá-la
    # ali faria o modelo comparar o texto com ele mesmo: o delta sairia zero por construção.
    remover_correspondente: str | None = None


# Emendas aprovadas, com a base verificada documento a documento (spec 12, verificação de
# 2026-09-17), e as duas matérias cuja base não sai da regra geral (verificação de 2026-09-23).
BASES_VERIFICADAS: dict[tuple[str, str], BaseEmenda] = {
    ("160197", "139"): BaseEmenda(
        "COMPOSTO_RECEBIDO_MAIS_OUTRAS_EMENDAS", (9459661, 9526122),
        "PL 3.626/2023: texto recebido da Câmara mais as outras Emendas do Senado; a redação final "
        "das Emendas mapeia a 139 como Emenda 3 do Senado, e as demais foram aprovadas na votação "
        "principal, ressalvados os destaques", remover_correspondente="139"),
    ("160197", "147"): BaseEmenda(
        "COMPOSTO_RECEBIDO_MAIS_OUTRAS_EMENDAS", (9459661, 9526122),
        "PL 3.626/2023: mesma base da Emenda 139; a redação final mapeia a 147 como Emenda 1 do Senado",
        remover_correspondente="147"),
    ("162696", "45"): BaseEmenda(
        "COMPOSTO_RECEBIDO_MAIS_OUTRAS_EMENDAS", (9568879, 9799870),
        "PL 528/2020: texto recebido mais as outras Emendas do Senado; a redação final mapeia a 45 "
        "como Emenda 1 do Senado", remover_correspondente="45"),
    ("161961", "58"): BaseEmenda(
        "EMENDA_SUBSTITUTIVA", (9843514,),
        "PL 182/2024: o substitutivo da relatora, registrado como Emenda 59; a redação para o turno "
        "suplementar declara consolidar a Emenda 59 com a 25 e a 58, e nenhuma diferença não "
        "explicada pela 58 cai no art. 30, que é o que ela altera"),
    ("166801", "1"): BaseEmenda(
        "INICIAL_VERIFICADO", (9876820,),
        "PL 4.932/2024: não há parecer nem redação final no processo; o projeto veio da Câmara e foi "
        "enviado à sanção (norma em 14/01/2025), e projeto revisto emendado no mérito volta à "
        "Câmara -- logo o texto recebido é o que foi votado"),
}

# Emendas que ficam sem nota, cada uma com o motivo (regra de allowlist).
SEM_BASE: dict[tuple[str, str | None], str] = {
    ("158930", "804"): "PEC 45/2019: aprovada nos termos de subemenda do Relator oferecida em "
                       "Plenário, cuja redação não está em nenhum documento legível",
    ("166053", None): "PLP 175/2024: subemenda ao substitutivo sem número na descrição da votação, "
                      "que não casa com /processo/emenda pelo número",
}

_JUSTIFICACAO = re.compile(r"(?i)JUSTIFICA(?:Ç|C)(?:Ã|A)O")
# Cabeçalho de cada emenda dentro da redação final das Emendas do Senado, com o mapeamento
# oficial para a emenda de Plenário: "EMENDA Nº 3 (Corresponde à Emenda nº 139 – Plen)".
_BLOCO_EMENDA = re.compile(r"EMENDA\s*N\s*[ºo°]?\s*(\d+)\s*\(\s*Corresponde\s*[àa]\s*(.{0,160}?)\)", re.S)


def dispositivo(texto_emenda: str) -> str:
    """A parte normativa da emenda: o que foi votado. A justificação fica de fora porque é
    advocacia sobre o conteúdo, escrita por quem propôs, e identifica o proponente em 30 de 30
    das emendas medidas."""
    corte = _JUSTIFICACAO.search(texto_emenda)
    return texto_emenda[:corte.start()] if corte else texto_emenda


def remover_correspondente(texto_emendas: str, numero_plen: str) -> str:
    """Tira da redação final das Emendas do Senado o bloco que corresponde à emenda destacada.

    O documento numera as emendas do Senado e diz, em cada uma, a qual emenda de Plenário ela
    corresponde. Pontuar uma emenda aprovada contra um texto que já a contém mediria a diferença
    entre o texto e ele mesmo."""
    blocos = list(_BLOCO_EMENDA.finditer(texto_emendas))
    alvo = re.compile(rf"emenda\s*n\s*[ºo°]?\s*{re.escape(numero_plen)}(?!\d)", re.I)
    for i, m in enumerate(blocos):
        if not alvo.search(m.group(2)):
            continue
        fim = blocos[i + 1].start() if i + 1 < len(blocos) else len(texto_emendas)
        return texto_emendas[:m.start()] + texto_emendas[fim:]
    raise ValueError(f"Emenda {numero_plen} não aparece mapeada na redação final das Emendas")


def base_da_emenda(codigo_materia, numero, resultado, escolha_do_texto: Escolha | None) -> BaseEmenda | None:
    """O texto-base, ou None quando a emenda fica sem nota.

    `resultado` é `fact_votacao.resultado` ("A" ou "R"); `escolha_do_texto` é o documento da
    etapa, de `documento_processo.escolher_documentos`."""
    if (codigo_materia, numero) in SEM_BASE:
        return None
    verificada = BASES_VERIFICADAS.get((codigo_materia, numero))
    if verificada is not None:
        return verificada
    if numero is None or resultado != "R" or escolha_do_texto is None:
        # Aprovada sem base verificada, ou sem número, ou sem documento da etapa: sem nota.
        return None
    return BaseEmenda(escolha_do_texto.fonte, escolha_do_texto.ids_documento,
                      "texto final da etapa; emenda rejeitada, o texto não a contém")
