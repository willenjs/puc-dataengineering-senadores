"""PDF para texto limpo, sem a identidade de quem propôs, relatou ou assinou (spec v3, §4).

A remoção é estrutural, não só nominal. A lista de dim_senador não cobre deputados (a chancela
do presidente da Câmara), e as linhas de autenticação identificam o gabinete por URL e código
mesmo sem nome.
"""
from __future__ import annotations

import io
import re
import unicodedata

from pypdf import PdfReader

MARCADOR = "[parlamentar]"

_DESCARTAVEL = re.compile(
    r"(?i)assinad[oa]\s+(eletronicamente|por\s+chancela)|para\s+verificar\s+as\s+assinaturas"
    r"|autenticadoc-legis|infoleg-autenticidade-assinatura|^\s*data\s+do\s+documento\s*:"
    r"|^\s*gabinete\s+d[oa]\s+(senador|senadora|deputad[oa])"
)
_URL = re.compile(r"https?://\S+")
_CODIGO_SOLTO = re.compile(r"^\s*\d{6,}\s*$")
_CARGO = r"(PRESIDENTE|VICE-PRESIDENTE|RELATORA?|\d?[ºO°]?\s*SECRET[ÁA]RI[OA]|\d?[ºO°]?\s*SUPLENTE)"
_NOME_E_CARGO = re.compile(rf"^\s*[A-ZÀ-Ý][A-ZÀ-Ý .'’-]+,\s*{_CARGO}\s*$")
_SO_CARGO = re.compile(r"(?i)^\s*(presidente|vice-presidente|relatora?|\d?[ºo°]?\s*secret[áa]ri[oa])\s*$")
_CAIXA_ALTA_CURTA = re.compile(r"^\s*[A-ZÀ-Ý][A-ZÀ-Ý.'’-]*(\s+[A-ZÀ-Ý][A-ZÀ-Ý.'’-]*){0,5}\s*$")
_LOCAL_E_DATA = re.compile(
    r"(?i)^\s*(senado\s+federal|c[âa]mara\s+dos\s+deputados|sala\s+d[ae]s?\s+sess[õo]es)[^\n]*,\s*em\s+\d"
)
# "Senador Fulano", "Senadores Fulano e Beltrano", "Dep. Fulano". Exige nome em maiúscula logo
# depois, então "Senado Federal", "os senadores" e "Senhores Senadores," ficam intactos. O nome
# nunca atravessa quebra de linha nem ponto: sem isso, "Deputado Efraim Filho.\n\nA Comissão
# Diretora" levava junto "A Comissão Diretora". O único ponto aceito é o de título abreviado.
_PALAVRA_DE_NOME = r"(?:Dra?\.|Profa?\.|[A-ZÀ-Ý][\wÀ-ÿ'’-]*)"
_TRATAMENTO = re.compile(
    rf"\b(?:Senador(?:a|es|as)?|Deputad[oa]s?|Sen\.|Dep\.)[ \t]+"
    rf"{_PALAVRA_DE_NOME}(?:[ \t]+(?:d[aeo]s?[ \t]+|e[ \t]+)?{_PALAVRA_DE_NOME}){{0,4}}"
)


def extrair_texto_pdf(conteudo_pdf: bytes) -> tuple[str, int]:
    leitor = PdfReader(io.BytesIO(conteudo_pdf))
    return "\n".join((p.extract_text() or "") for p in leitor.pages), len(leitor.pages)


def _dobrar(texto: str) -> str:
    """Minúsculas sem acento, com o MESMO comprimento, para que as posições achadas no texto
    dobrado valham no original."""
    return "".join((unicodedata.normalize("NFKD", c)[:1] or c).lower() for c in texto)


def _remover_linhas_de_assinatura(texto: str) -> str:
    saida: list[str] = []
    em_bloco = False
    for linha in texto.splitlines():
        if _LOCAL_E_DATA.search(linha):
            em_bloco = True
            saida.append(linha)
            continue
        if em_bloco and not linha.strip():
            saida.append(linha)
            continue
        if em_bloco and not re.search(r"\d", linha) and (
            _CAIXA_ALTA_CURTA.match(linha) or _NOME_E_CARGO.match(linha)
        ):
            continue
        em_bloco = False
        if _DESCARTAVEL.search(linha) or _CODIGO_SOLTO.match(linha) or _NOME_E_CARGO.match(linha):
            continue
        if _SO_CARGO.match(linha) and saida and _CAIXA_ALTA_CURTA.match(saida[-1]) and saida[-1].strip():
            saida.pop()  # "ARTHUR LIRA" / "Presidente"
            continue
        saida.append(_URL.sub("", linha))
    return "\n".join(saida)


def _substituir_nomes(texto: str, nomes: list[str]) -> str:
    for nome in sorted({n.strip() for n in nomes if n and n.strip()}, key=len, reverse=True):
        padrao = re.compile(r"(?<!\w)" + r"\s+".join(re.escape(p) for p in _dobrar(nome).split()) + r"(?!\w)")
        dobrado = _dobrar(texto)
        partes, fim = [], 0
        for m in padrao.finditer(dobrado):
            partes.append(texto[fim:m.start()])
            partes.append(MARCADOR)
            fim = m.end()
        partes.append(texto[fim:])
        texto = "".join(partes)
    return texto


def higienizar(texto: str, nomes_parlamentares: list[str]) -> str:
    texto = _remover_linhas_de_assinatura(texto)
    texto = _TRATAMENTO.sub(MARCADOR, texto)
    return _substituir_nomes(texto, nomes_parlamentares)


def vazamentos(texto: str, nomes_parlamentares: list[str]) -> list[str]:
    """O que ainda identifica alguém no texto. Lista vazia é a condição para o texto virar insumo."""
    achados = []
    dobrado = _dobrar(texto)
    for nome in {n.strip() for n in nomes_parlamentares if n and n.strip()}:
        padrao = r"(?<!\w)" + r"\s+".join(re.escape(p) for p in _dobrar(nome).split()) + r"(?!\w)"
        if re.search(padrao, dobrado):
            achados.append(f"nome: {nome}")
    achados += [f"url: {m.group(0)}" for m in _URL.finditer(texto)]
    achados += [f"tratamento: {m.group(0)}" for m in re.finditer(r"\b(?:Sen|Dep)\.\s+[A-ZÀ-Ý]\w*", texto)]
    return achados
