"""Enriquecimento por LLM: nota de alinhamento socioeconômico por matéria."""
from __future__ import annotations

import json

PROMPT_TEMPLATE = """Você é um analista legislativo imparcial. Dada a ementa de uma \
matéria em tramitação no Senado Federal do Brasil, avalie o impacto dela para três \
perfis de brasileiro: pobre, classe média e rico.

Ementa: "{ementa}"

Responda SOMENTE com um JSON no seguinte formato, sem texto adicional:
{{
  "nota_pobre": <número entre -1 e 1>,
  "justificativa_pobre": "<explicação em até 2 frases>",
  "nota_classe_media": <número entre -1 e 1>,
  "justificativa_classe_media": "<explicação em até 2 frases>",
  "nota_rico": <número entre -1 e 1>,
  "justificativa_rico": "<explicação em até 2 frases>"
}}

Onde -1 significa claramente prejudicial a esse perfil, 0 significa neutro/não se \
aplica, e 1 significa claramente benéfico."""

REQUIRED_KEYS = {
    "nota_pobre",
    "justificativa_pobre",
    "nota_classe_media",
    "justificativa_classe_media",
    "nota_rico",
    "justificativa_rico",
}


# v2 muda a ENTRADA do prompt, nunca a saída: as seis chaves de REQUIRED_KEYS são
# contrato congelado. O contexto extra (tipo, número, ano) existe
# porque a ementa sozinha é frequentemente uma frase técnica sem sujeito -- 6 de 57 PLPs,
# 2 de 24 PLs e 2 de 23 PECs substantivas saíam 0/0 com a v1.
#
# A análise é pedida DENTRO do JSON, como primeira chave, e não em prosa antes dele:
# pedir raciocínio solto e "responda SOMENTE com um JSON" na mesma instrução é
# contraditório, e qualquer texto fora do objeto faz json.loads falhar -- queimando as
# duas tentativas de score_materia. Como chave extra ela é tolerada por
# parse_llm_response (que só checa ausências) e descartada antes de gravar no Bronze.
#
# O autor NÃO entra no prompt, de propósito, embora a spec o listasse: 45 das 113 matérias
# substantivas trazem "(PARTIDO/UF)" no autor, e nomes de senadores já são pista partidária para
# um LLM. O índice compara o voto dos senadores com estas notas; se o modelo lesse ideologia pelo
# partido de quem propôs, a ordenação por partido ficaria circular. O script ainda busca `autor`,
# então reintroduzi-lo é uma mudança de uma linha aqui -- e custa uma nova rodada de scoring.
PROMPT_TEMPLATE_V2 = """Você é um analista legislativo imparcial. Abaixo está uma \
matéria votada no Senado Federal do Brasil.

Tipo: {sigla} -- {tipo_descricao}
Identificação: {sigla} {numero}/{ano}
Ementa: "{ementa}"

Avalie o impacto distributivo dela para três perfis de brasileiro: pobre, classe média e \
rico. Antes de atribuir as notas, identifique quem ganha e quem perde: que grupo recebe o \
benefício direto (transferência de renda, acesso a serviço, direito novo, redução de \
carga), quem arca com o custo (tributo, restrição de direito, perda de benefício), e se o \
efeito é concentrado ou difuso. Matéria fiscal, tributária ou de gasto público quase \
sempre tem efeito distributivo, mesmo quando a ementa é técnica e não nomeia nenhum \
grupo; só use notas próximas de 0 quando realmente não houver efeito identificável. Se o \
efeito for o mesmo para os três perfis, dê a mesma nota aos três.

Responda SOMENTE com um JSON no seguinte formato, sem nenhum texto fora do objeto. Todo o \
raciocínio deve ficar dentro do campo "analise_distributiva":
{{
  "analise_distributiva": "<quem ganha, quem perde, em até 3 frases>",
  "nota_pobre": <número entre -1 e 1>,
  "justificativa_pobre": "<explicação em até 2 frases>",
  "nota_classe_media": <número entre -1 e 1>,
  "justificativa_classe_media": "<explicação em até 2 frases>",
  "nota_rico": <número entre -1 e 1>,
  "justificativa_rico": "<explicação em até 2 frases>"
}}

Onde -1 significa claramente prejudicial a esse perfil, 0 significa neutro/não se \
aplica, e 1 significa claramente benéfico."""


class LLMResponseError(Exception):
    """A resposta do LLM não pôde ser interpretada como o JSON esperado."""


def build_prompt(ementa: str) -> str:
    return PROMPT_TEMPLATE.format(ementa=ementa)


def build_prompt_v2(materia: dict) -> str:
    return PROMPT_TEMPLATE_V2.format(
        ementa=materia["ementa"],
        sigla=materia.get("sigla") or "não informado",
        numero=materia.get("numero") or "s/n",
        ano=materia.get("ano") or "ano não informado",
        tipo_descricao=materia.get("tipo_descricao") or "tipo não informado",
    )


def construir_prompt(materia: dict, prompt_version: str) -> str:
    """Monta o prompt da versão pedida a partir do dict da matéria.

    v1 usa só a ementa e ignora o resto do dict de propósito: o prompt v1 é congelado,
    para que qualquer matéria já pontuada com v1 continue reproduzível byte a byte.
    """
    if prompt_version == "v1":
        return build_prompt(materia["ementa"])
    if prompt_version == "v2":
        return build_prompt_v2(materia)
    raise ValueError(f"Versão de prompt desconhecida: {prompt_version!r}")


# v3 (spec 2026-09-16): o insumo é o TEXTO votado, não a ementa. Duas variantes para o teste
# A/B do empurrão fiscal (spec §7), com critério declarado antes de ver os números. O documento
# vem primeiro, num bloco com cache de 1 hora, e as instruções depois: as 18 chamadas de uma
# matéria (9 amostras x 2 variantes) compartilham o prefixo em cache, e para documento longo
# essa é também a ordem recomendada. O contrato de saída é o mesmo da v2, agora imposto na
# geração pelo esquema (saída estruturada), o que elimina a falha do ponto e vírgula.
VERSOES_V3 = ("v3-com-empurrao", "v3-sem-empurrao")

FRASE_EMPURRAO_FISCAL = (
    "Matéria fiscal, tributária ou de gasto público quase sempre tem efeito distributivo, "
    "mesmo quando o texto é técnico e não nomeia nenhum grupo; só use notas próximas de 0 "
    "quando realmente não houver efeito identificável. "
)

BLOCO_DOCUMENTO_V3 = """Matéria votada no Senado Federal do Brasil.

Tipo: {sigla} -- {tipo_descricao}
Identificação: {sigla} {numero}/{ano}
Ementa: "{ementa}"

{documentos}"""

INSTRUCOES_V3 = """Você é um analista legislativo imparcial. {descricao_insumo}

Avalie o impacto distributivo {objeto} para três perfis de brasileiro: pobre, classe média e \
rico. Antes de atribuir as notas, identifique quem ganha e quem perde: que grupo recebe o \
benefício direto (transferência de renda, acesso a serviço, direito novo, redução de \
carga), quem arca com o custo (tributo, restrição de direito, perda de benefício), e se o \
efeito é concentrado ou difuso. {empurrao}Se o efeito for o mesmo para os três perfis, dê a \
mesma nota aos três.

Responda com um objeto JSON com os campos abaixo. Todo o raciocínio deve ficar dentro do \
campo "analise_distributiva":
- "analise_distributiva": quem ganha, quem perde, em até 3 frases
- "nota_pobre": número entre -1 e 1
- "justificativa_pobre": explicação em até 2 frases
- "nota_classe_media": número entre -1 e 1
- "justificativa_classe_media": explicação em até 2 frases
- "nota_rico": número entre -1 e 1
- "justificativa_rico": explicação em até 2 frases

Onde -1 significa claramente prejudicial a esse perfil, 0 significa neutro/não se aplica, e 1 \
significa claramente benéfico."""

_INSUMO_SIMPLES = (
    "Acima está o texto da matéria na forma em que foi votado, entre as marcas <texto_votado>.",
    "desse texto",
)
_INSUMO_COMPOSTO = (
    "Acima estão o texto recebido da Câmara dos Deputados, entre as marcas <texto_recebido>, e as "
    "emendas que o Senado aprovou a ele, entre as marcas <emendas_do_senado>. O que foi votado é o "
    "texto recebido com essas emendas aplicadas.",
    "do texto recebido tal como fica com as emendas aplicadas",
)

ESQUEMA_SAIDA_V3 = {
    "type": "object",
    "properties": {
        "analise_distributiva": {"type": "string"},
        "nota_pobre": {"type": "number"},
        "justificativa_pobre": {"type": "string"},
        "nota_classe_media": {"type": "number"},
        "justificativa_classe_media": {"type": "string"},
        "nota_rico": {"type": "number"},
        "justificativa_rico": {"type": "string"},
    },
    "required": [
        "analise_distributiva", "nota_pobre", "justificativa_pobre", "nota_classe_media",
        "justificativa_classe_media", "nota_rico", "justificativa_rico",
    ],
    "additionalProperties": False,
}


def montar_conteudo_v3(materia: dict, documentos: list[dict], prompt_version: str) -> list[dict]:
    """Conteúdo da mensagem `user` do prompt v3: [bloco do documento em cache, instruções].

    A faixa [-1, 1] não vai para o esquema de propósito: nem toda restrição numérica é aceita
    pela saída estruturada, e `parse_llm_response` já a verifica."""
    if prompt_version not in VERSOES_V3:
        raise ValueError(f"Versão de prompt v3 desconhecida: {prompt_version!r}")
    composto = {d["papel"] for d in documentos} == {"texto_recebido", "emendas_do_senado"}
    descricao_insumo, objeto = _INSUMO_COMPOSTO if composto else _INSUMO_SIMPLES
    bloco = BLOCO_DOCUMENTO_V3.format(
        sigla=materia.get("sigla") or "não informado",
        tipo_descricao=materia.get("tipo_descricao") or "tipo não informado",
        numero=materia.get("numero") or "s/n",
        ano=materia.get("ano") or "ano não informado",
        ementa=materia["ementa"],
        documentos="\n\n".join(f"<{d['papel']}>\n{d['texto']}\n</{d['papel']}>" for d in documentos),
    )
    instrucoes = INSTRUCOES_V3.format(
        descricao_insumo=descricao_insumo,
        objeto=objeto,
        empurrao=FRASE_EMPURRAO_FISCAL if prompt_version == "v3-com-empurrao" else "",
    )
    return [
        {"type": "text", "text": bloco, "cache_control": {"type": "ephemeral", "ttl": "1h"}},
        {"type": "text", "text": instrucoes},
    ]


# Emenda destacada: a nota é de um DELTA. O texto-base vai primeiro, em cache, porque as 9
# amostras de todas as emendas da mesma matéria compartilham o mesmo texto-base; o dispositivo da
# emenda vem depois, junto das instruções, porque muda de emenda para emenda.
VERSAO_EMENDA = "emenda-v1"

BLOCO_BASE_EMENDA = """Texto em discussão no Senado Federal do Brasil, na forma em que estava quando a emenda abaixo foi votada.

Tipo: {sigla} -- {tipo_descricao}
Identificação: {sigla} {numero}/{ano}
Ementa: "{ementa}"

{documentos}"""

INSTRUCOES_EMENDA = """Você é um analista legislativo imparcial. Acima está o texto-base, {marcas}. Abaixo está a parte normativa de uma emenda a esse texto, entre as marcas <emenda>; ela foi destacada para votação em separado.

<emenda>
{dispositivo}
</emenda>

Avalie o impacto distributivo de APROVAR a emenda, em relação ao texto-base, para três perfis de \
brasileiro: pobre, classe média e rico. A nota é da MUDANÇA que a emenda faz, não do texto-base: \
se a emenda melhora a situação de um perfil em relação ao texto-base, a nota dele é positiva; se \
piora, negativa; se não muda nada para ele, 0. Antes de atribuir as notas, identifique o que a \
emenda altera no texto-base, quem ganha e quem perde com essa alteração, e se o efeito é \
concentrado ou difuso. {empurrao}Se o efeito for o mesmo para os três perfis, dê a mesma nota aos três.

Responda com um objeto JSON com os campos abaixo. Todo o raciocínio deve ficar dentro do campo \
"analise_distributiva":
- "analise_distributiva": o que a emenda muda, quem ganha, quem perde, em até 3 frases
- "nota_pobre": número entre -1 e 1
- "justificativa_pobre": explicação em até 2 frases
- "nota_classe_media": número entre -1 e 1
- "justificativa_classe_media": explicação em até 2 frases
- "nota_rico": número entre -1 e 1
- "justificativa_rico": explicação em até 2 frases

Onde -1 significa que aprovar a emenda é claramente prejudicial a esse perfil, 0 que não muda \
nada para ele, e 1 que é claramente benéfico."""


def montar_conteudo_emenda(materia: dict, documentos_base: list[dict], dispositivo_emenda: str) -> list[dict]:
    """Conteúdo da mensagem `user` do prompt de emenda: [texto-base em cache, emenda + instruções]."""
    papeis = [d["papel"] for d in documentos_base]
    marcas = (" e ".join(f"entre as marcas <{p}>" for p in papeis)
              if len(papeis) > 1 else f"entre as marcas <{papeis[0]}>")
    bloco = BLOCO_BASE_EMENDA.format(
        sigla=materia.get("sigla") or "não informado",
        tipo_descricao=materia.get("tipo_descricao") or "tipo não informado",
        numero=materia.get("numero") or "s/n",
        ano=materia.get("ano") or "ano não informado",
        ementa=materia["ementa"],
        documentos="\n\n".join(f"<{d['papel']}>\n{d['texto']}\n</{d['papel']}>" for d in documentos_base),
    )
    instrucoes = INSTRUCOES_EMENDA.format(
        marcas=marcas, dispositivo=dispositivo_emenda, empurrao=FRASE_EMPURRAO_FISCAL)
    return [
        {"type": "text", "text": bloco, "cache_control": {"type": "ephemeral", "ttl": "1h"}},
        {"type": "text", "text": instrucoes},
    ]


def _remover_cercas_markdown(texto: str) -> str:
    """Remove um bloco de código Markdown (ex: ```json ... ```) ao redor do JSON.

    Modelos frequentemente envolvem a resposta em cercas de código mesmo quando o
    prompt pede JSON puro sem texto adicional.
    """
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.removeprefix("```json").removeprefix("```")
        texto = texto.removesuffix("```")
        texto = texto.strip()
    return texto


def parse_llm_response(raw_text: str) -> dict:
    """Valida e converte a resposta do LLM no dict de notas/justificativas esperado."""
    try:
        data = json.loads(_remover_cercas_markdown(raw_text))
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"Resposta não é um JSON válido: {exc}") from exc

    if not isinstance(data, dict):
        raise LLMResponseError(
            f"Resposta do LLM não é um objeto JSON, é um {type(data).__name__}: {data!r}"
        )

    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise LLMResponseError(f"Campos ausentes na resposta do LLM: {missing}")

    for campo in ("nota_pobre", "nota_classe_media", "nota_rico"):
        valor = data[campo]
        if not isinstance(valor, (int, float)) or not (-1 <= valor <= 1):
            raise LLMResponseError(f"Campo '{campo}' fora do intervalo [-1, 1]: {valor!r}")

    return {
        "nota_pobre": float(data["nota_pobre"]),
        "justificativa_pobre": str(data["justificativa_pobre"]),
        "nota_classe_media": float(data["nota_classe_media"]),
        "justificativa_classe_media": str(data["justificativa_classe_media"]),
        "nota_rico": float(data["nota_rico"]),
        "justificativa_rico": str(data["justificativa_rico"]),
    }


def score_materia(
    materia: dict,
    prompt_version: str,
    llm_client,
    amostra: int = 1,
    registrar_resposta=None,
) -> dict:
    """Pontua uma matéria via LLM, com 1 retry em caso de resposta malformada.

    `materia` precisa ter `codigo_materia` e `ementa`; a v2 usa também `sigla`,
    `numero`, `ano` e `tipo_descricao` (ausentes viram "não informado").
    `llm_client` precisa expor `.complete(prompt: str) -> str`.

    `amostra` é o índice da repetição desta mesma (matéria, versão de prompt). O modelo é
    um avaliador estocástico: a mesma entrada não devolve sempre a mesma nota, e medir esse
    ruído (e, depois, tomar a mediana de várias amostras) exige poder gravar mais de uma
    resposta para a mesma chave. É uma ADIÇÃO ao payload do Bronze, nunca uma renomeação
    das seis chaves congeladas. Arquivos gravados antes desta coluna existir não têm o
    campo e são lidos como amostra 1.

    `registrar_resposta(texto_cru, tentativa)`, quando fornecido, recebe a resposta do
    modelo de CADA tentativa, inclusive as ilegíveis. É a trilha de auditoria da nota: o
    parser descarta tudo que não são as seis chaves congeladas (na v2, o campo
    analise_distributiva, que é justamente o raciocínio), e auditoria não pode depender de
    pagar a chamada de novo. Fica por conta de quem chama decidir onde gravar.
    """
    codigo_materia = materia["codigo_materia"]
    prompt = construir_prompt(materia, prompt_version)

    for tentativa in (1, 2):
        raw_text = llm_client.complete(prompt)
        if registrar_resposta is not None:
            registrar_resposta(raw_text, tentativa)
        try:
            notas = parse_llm_response(raw_text)
        except LLMResponseError:
            continue
        # `notas` traz exatamente as seis chaves congeladas -- qualquer chave extra da
        # resposta (analise_distributiva na v2) fica de fora do que vai para o Bronze.
        return {
            "codigo_materia": codigo_materia,
            "prompt_version": prompt_version,
            "amostra": amostra,
            "status": "ok",
            **notas,
        }

    return {
        "codigo_materia": codigo_materia,
        "prompt_version": prompt_version,
        "amostra": amostra,
        "status": "needs_review",
        "nota_pobre": None,
        "justificativa_pobre": None,
        "nota_classe_media": None,
        "justificativa_classe_media": None,
        "nota_rico": None,
        "justificativa_rico": None,
    }


def already_scored(
    codigo_materia: str,
    prompt_version: str,
    amostra: int,
    existing_keys: set[tuple[str, str, str, int]],
    numero_objeto: str = "texto",
) -> bool:
    """A chave inclui o OBJETO desde 2026-09-23: uma matéria pode ter três emendas destacadas com
    nota própria, e sem ele a segunda seria tomada por já pontuada. O texto da matéria é o objeto
    "texto", que é o padrão porque a v1 e a v2 só pontuam texto."""
    return (codigo_materia, numero_objeto, prompt_version, amostra) in existing_keys
