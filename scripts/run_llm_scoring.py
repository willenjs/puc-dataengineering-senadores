"""Orquestra o scoring de matérias via LLM e grava os resultados brutos na camada Bronze."""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import anthropic
from databricks import sql
from dotenv import load_dotenv

from senado_pipeline.databricks_auth import (
    DATABRICKS_HTTP_PATH_PADRAO,
    DATABRICKS_SERVER_HOSTNAME_PADRAO,
    obter_secret,
)
from senado_pipeline.llm_scorer import already_scored, score_materia
from senado_pipeline.volume_writer import build_bronze_relative_path, write_json_to_volume

PROMPT_VERSION = "v2"
VOLUME_ROOT_PADRAO = "/Volumes/senado_votacoes/bronze/raw_landing"
# Quantas vezes cada matéria é pontuada na mesma versão de prompt. 1 é o padrão porque
# rodar o Job sem pedir nada não pode multiplicar o custo de API; a rodada de
# repetibilidade (decisão 1.2) pede 2, e a v3 usará N com a mediana como nota.
AMOSTRAS_PADRAO = 1
# Diretório IRMÃO de materia_llm_scores_raw, nunca dentro dele: o Auto Loader de
# bronze_materia_llm_scores_raw.py ingere como nota tudo que cai naquele caminho, e a
# resposta crua do modelo não é uma nota. Nenhuma tabela lê este diretório hoje -- ele é
# trilha de auditoria, e é o que permite reexaminar uma nota sem pagar a chamada de novo.
ENTIDADE_RESPOSTA_BRUTA = "materia_llm_scores_resposta_bruta"


class AnthropicLLMClient:
    """Adapta o SDK da Anthropic para a interface `.complete(prompt) -> str`."""

    def __init__(self, client: anthropic.Anthropic, model: str = "claude-sonnet-5"):
        self._client = client
        self._model = model

    def complete(self, prompt: str) -> str:
        # O SDK anthropic instalado (1.3.0) não aceita mais `temperature` em
        # messages.create() -- removido da API dessa versão do cliente.
        # max_tokens=300 (valor original) estava baixo demais: claude-sonnet-5 às vezes
        # gasta parte do orçamento em thinking antes de responder, e mesmo sem isso a
        # resposta completa (fences + JSON com 3 notas/justificativas) passa de 300
        # tokens -- confirmado via stop_reason="max_tokens" em 100% das matérias que
        # ficaram needs_review (diagnóstico ad-hoc, não a ementa sendo longa demais).
        # 2048 (era 1024) porque o prompt v2 pede um campo analise_distributiva a mais
        # dentro do mesmo JSON, e estourar o orçamento devolve needs_review para o lote
        # inteiro -- exatamente o que a v2 existe para evitar.
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        # `content[0]` nem sempre é o bloco de texto -- às vezes o modelo emite um
        # ThinkingBlock antes, então procuramos o primeiro bloco com atributo `text`.
        for bloco in response.content:
            texto = getattr(bloco, "text", None)
            if texto is not None:
                return texto
        return ""


def buscar_materias_sem_ementa_vazia(conn) -> list[dict]:
    """Lê a fila de controle do scoring: matérias votadas, substantivas e com ementa.

    Os três filtros moram em `silver_fila_materias_pontuacao.sql`, não aqui. Só pontuar
    o que foi efetivamente votado é a regra de custo (~360 matérias em vez das ~18k
    apresentadas); `materia_substantiva` exclui MSF, OFS, RQS, REQ, PDL e afins, cuja
    ementa não descreve impacto distributivo nenhum e que eram 2/3 do custo de API; e a
    allowlist de siglas continua vivendo em `silver_tipos_materia.sql`, lida pela fila
    com um join, nunca repetida. A fila também traz `tipo_descricao`, que o prompt v2
    usa como contexto.
    """
    cursor = conn.cursor()
    try:
        cursor.execute(
            "select codigo_materia, ementa, sigla, numero, ano, autor, tipo_descricao "
            "from senado_votacoes.silver.fila_materias_pontuacao"
        )
        return [
            {
                "codigo_materia": row[0],
                "ementa": row[1],
                "sigla": row[2],
                "numero": row[3],
                "ano": row[4],
                # Buscado mas NÃO enviado ao modelo: o prompt v2 deixa o autor de fora de
                # propósito (pista partidária -- ver llm_scorer.py). Mantido aqui para que
                # reintroduzi-lo seja uma mudança de uma linha no prompt.
                "autor": row[5],
                "tipo_descricao": row[6],
            }
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()


def buscar_chaves_existentes(conn) -> set[tuple[str, str, str, int]]:
    """Chaves (codigo_materia, numero_objeto, prompt_version, amostra) já pontuadas com sucesso.

    O OBJETO entrou na chave em 2026-09-23: uma matéria pode ter três emendas destacadas, cada
    uma com nota própria, e sem ele a segunda emenda seria tomada por já pontuada. Arquivo sem
    `numero_objeto` (tudo que é anterior) conta como objeto "texto".

    O coalesce existe porque os arquivos gravados antes do índice de amostra (todas as
    linhas v1 e as 113 da v2 de 2026-09-15) não têm o campo: sem ele voltariam com NULL,
    nunca casariam com (código, versão, 1), e a rodada seguinte repontuaria -- e repagaria
    -- tudo de novo.
    """
    cursor = conn.cursor()
    try:
        cursor.execute(
            "select payload:codigo_materia::string, "
            "coalesce(payload:numero_objeto::string, 'texto'), payload:prompt_version::string, "
            "coalesce(payload:amostra::int, 1) "
            "from senado_votacoes.bronze.materia_llm_scores_raw "
            "where payload:status::string = 'ok'"
        )
        return {(row[0], row[1], row[2], int(row[3])) for row in cursor.fetchall()}
    finally:
        cursor.close()


def ler_amostras_pedidas(argv: list[str], env: dict) -> int:
    """Quantas amostras por matéria esta execução deve garantir.

    Ordem: `--amostras N` na linha de comando, depois SENADO_SCORING_AMOSTRAS, depois o
    padrão. A linha de comando existe porque um `spark_python_task` em compute serverless
    não tem como receber variável de ambiente pelo Jobs API (só cluster clássico tem
    spark_env_vars) -- `--python-params` no run é o caminho que sobra. Argumentos de outras
    tasks do Job chegam no mesmo sys.argv, então nada que não seja `--amostras` é lido.
    Valor vazio cai no padrão: `.env.example` embarca chaves vazias, e int("") derrubaria a
    task inteira.
    """
    if "--amostras" in argv:
        indice = argv.index("--amostras")
        if indice + 1 < len(argv) and argv[indice + 1].strip().isdigit():
            return int(argv[indice + 1])
    do_ambiente = (env.get("SENADO_SCORING_AMOSTRAS") or "").strip()
    if do_ambiente.isdigit():
        return int(do_ambiente)
    return AMOSTRAS_PADRAO


def chaves_no_volume(volume_root: str) -> set[tuple[str, str, str, int]]:
    """Chaves (codigo_materia, numero_objeto, prompt_version, amostra) já gravadas com sucesso
    (status "ok") como arquivo no Volume.

    `buscar_chaves_existentes` sozinha não basta para retomar uma execução que morreu
    no meio: a tabela Bronze é alimentada por Auto Loader e só reflete os arquivos
    depois do próximo refresh do Lakeflow Pipeline (uma task *posterior* no Job). Se a
    task `llm_scoring` cai e o Databricks a reexecuta num processo novo, nada do que a
    tentativa anterior gravou no Volume aparece ainda na tabela -- e as matérias seriam
    repontuadas (e repagas). O Volume, montado como filesystem normal no compute do
    Databricks, reflete as escritas na hora, então basta varrê-lo.

    Só conta o arquivo se `status == "ok"` dentro dele -- um arquivo `needs_review` de
    uma execução anterior nunca é removido/sobrescrito, então contá-lo só pela
    existência do nome bloquearia a matéria para sempre (nenhuma execução futura a
    re-tentaria, mesmo com `buscar_chaves_existentes` corretamente ignorando
    needs_review na tabela Bronze). Ver teste de regressão
    `test_chaves_no_volume_ignora_arquivos_needs_review`.

    A chave sai de DENTRO do payload, não do nome do arquivo. Enquanto o nome tinha dois
    segmentos (`{codigo}_{versao}.json`) quebrá-lo no último underscore era inequívoco,
    porque `codigo_materia` é puramente numérico; com a amostra o nome passou a ter três
    (`{codigo}_{versao}_amostra{n}.json`) e o mesmo `rpartition` devolveria ("123_v2",
    "amostra2"). O arquivo já é lido para checar o status, então ler a chave dali não custa
    nada e não depende de convenção de nome. Arquivo sem `amostra` (todo v1 e os 113 v2 de
    2026-09-15) conta como amostra 1.
    """
    raiz = Path(volume_root) / "materia_llm_scores_raw"
    if not raiz.is_dir():
        return set()
    chaves = set()
    for arquivo in raiz.rglob("*.json"):
        try:
            conteudo = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(conteudo, dict) or conteudo.get("status") != "ok":
            continue
        codigo = conteudo.get("codigo_materia")
        prompt_version = conteudo.get("prompt_version")
        if codigo is None or prompt_version is None:
            continue
        chaves.add((str(codigo), str(conteudo.get("numero_objeto") or "texto"),
                    str(prompt_version), int(conteudo.get("amostra") or 1)))
    return chaves


def sufixo_objeto(numero_objeto) -> str:
    """Sufixo do nome de arquivo para o objeto votado: vazio no texto da matéria (para não mudar
    o caminho de nada que já foi gravado), "_emenda139" numa emenda destacada."""
    return "" if not numero_objeto or numero_objeto == "texto" else f"_emenda{numero_objeto}"


def gravar_resultados(
    volume_root: str,
    resultados: list[dict],
    extraction_date: str,
    write=write_json_to_volume,
) -> None:
    """Grava cada resultado como um arquivo JSON em materia_llm_scores_raw/, um arquivo
    por (codigo_materia, objeto, prompt_version, amostra) -- o Auto Loader recolhe no próximo
    refresh do Lakeflow Pipeline, igual às outras 4 fontes Bronze.

    O objeto entra no NOME desde 2026-09-23: duas emendas destacadas da mesma matéria, na mesma
    versão e amostra, se sobrescreveriam. O objeto "texto" fica fora do nome para que os arquivos
    anteriores continuem com o mesmo caminho."""
    for resultado in resultados:
        amostra = resultado.get("amostra") or 1
        relative_path = build_bronze_relative_path(
            "materia_llm_scores_raw",
            extraction_date,
            f"{resultado['codigo_materia']}{sufixo_objeto(resultado.get('numero_objeto'))}"
            f"_{resultado['prompt_version']}_amostra{amostra}",
        )
        write(volume_root, relative_path, resultado)


def gravar_resposta_bruta(
    volume_root: str,
    extraction_date: str,
    codigo_materia: str,
    prompt_version: str,
    amostra: int,
    tentativa: int,
    resposta_bruta: str,
    write=write_json_to_volume,
    numero_objeto: str = "texto",
) -> None:
    """Grava a resposta crua do modelo, como veio, num caminho próprio do Volume.

    Chave (matéria, versão de prompt, amostra, tentativa): a tentativa entra porque uma
    matéria que vira `needs_review` tem DUAS respostas ilegíveis, e são exatamente elas que
    alguém vai querer examinar depois.

    Não vai para o log do Job de propósito: log é efêmero e não é trilha de auditoria. Não
    vai para dentro de materia_llm_scores_raw/ de propósito: aquele caminho é ingerido pelo
    Auto Loader como se todo arquivo ali fosse uma nota.
    """
    relative_path = build_bronze_relative_path(
        ENTIDADE_RESPOSTA_BRUTA,
        extraction_date,
        f"{codigo_materia}{sufixo_objeto(numero_objeto)}_{prompt_version}"
        f"_amostra{amostra}_tentativa{tentativa}",
    )
    write(
        volume_root,
        relative_path,
        {
            "codigo_materia": codigo_materia,
            "numero_objeto": numero_objeto,
            "prompt_version": prompt_version,
            "amostra": amostra,
            "tentativa": tentativa,
            "resposta_bruta": resposta_bruta,
        },
    )


def pontuar_e_gravar_incrementalmente(
    volume_root: str,
    extraction_date: str,
    materias: list[dict],
    existentes: set[tuple[str, str, int]],
    llm_client,
    prompt_version: str,
    amostras: int = AMOSTRAS_PADRAO,
    score=score_materia,
    gravar=gravar_resultados,
    registrar_bruta=gravar_resposta_bruta,
) -> int:
    """Pontua cada matéria e grava o resultado imediatamente, uma de cada vez.

    Diferente de rodar o lote inteiro em memória e só persistir no final: uma
    exceção inesperada da API (rate limit, erro de rede, etc.) numa matéria não
    derruba as que já foram pontuadas e gravadas antes dela.

    Percorre as amostras 1..`amostras` de cada matéria e pula individualmente as que já
    estão prontas, então uma rodada de repetibilidade sobre matérias que já têm a amostra 1
    paga só a amostra 2.

    Retorna o número de (matéria, amostra) efetivamente pontuados e gravados.
    """
    pontuadas = 0
    for materia in materias:
        codigo = materia["codigo_materia"]
        for amostra in range(1, amostras + 1):
            if already_scored(codigo, prompt_version, amostra, existentes):
                continue
            try:
                resultado = score(
                    materia,
                    prompt_version,
                    llm_client,
                    amostra=amostra,
                    registrar_resposta=lambda texto, tentativa, _c=codigo, _a=amostra: registrar_bruta(
                        volume_root,
                        extraction_date,
                        codigo_materia=_c,
                        prompt_version=prompt_version,
                        amostra=_a,
                        tentativa=tentativa,
                        resposta_bruta=texto,
                    ),
                )
            except Exception as exc:
                print(
                    f"Falha inesperada ao pontuar {codigo} (amostra {amostra}), "
                    f"será retentada na próxima execução: {exc}"
                )
                continue
            gravar(volume_root, [resultado], extraction_date)
            pontuadas += 1
    return pontuadas


def main() -> None:
    load_dotenv()
    # `or` em vez do default de dois argumentos: `.get(k, PADRAO)` devolve "" quando a
    # chave existe mas está vazia -- exatamente o que `.env.example` produz depois de
    # `cp .env.example .env` + `load_dotenv()`.
    conn = sql.connect(
        server_hostname=os.environ.get("DATABRICKS_SERVER_HOSTNAME") or DATABRICKS_SERVER_HOSTNAME_PADRAO,
        http_path=os.environ.get("DATABRICKS_HTTP_PATH") or DATABRICKS_HTTP_PATH_PADRAO,
        access_token=obter_secret("databricks-token", "DATABRICKS_TOKEN"),
    )
    volume_root = os.environ.get("SENADO_VOLUME_ROOT") or VOLUME_ROOT_PADRAO
    extraction_date = date.today().isoformat()

    workspace_id = obter_secret("anthropic-workspace-id", "ANTHROPIC_WORKSPACE_ID", obrigatorio=False)
    anthropic_client = anthropic.Anthropic(
        api_key=obter_secret("anthropic-api-key", "ANTHROPIC_API_KEY"),
        default_headers={"anthropic-workspace-id": workspace_id} if workspace_id else {},
    )
    llm_client = AnthropicLLMClient(anthropic_client)

    amostras = ler_amostras_pedidas(sys.argv[1:], os.environ)

    try:
        materias = buscar_materias_sem_ementa_vazia(conn)
        # A tabela Bronze (via Auto Loader) só enxerga o que já passou por um refresh
        # do Pipeline; o Volume enxerga o que foi gravado agora há pouco, inclusive por
        # uma tentativa anterior desta mesma task que morreu no meio.
        existentes = buscar_chaves_existentes(conn) | chaves_no_volume(volume_root)
        pontuadas = pontuar_e_gravar_incrementalmente(
            volume_root,
            extraction_date,
            materias,
            existentes,
            llm_client,
            PROMPT_VERSION,
            amostras=amostras,
        )
        print(
            f"{pontuadas} pontuações gravadas nesta execução "
            f"({len(materias)} matérias, {amostras} amostra(s) por matéria, prompt {PROMPT_VERSION})."
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
