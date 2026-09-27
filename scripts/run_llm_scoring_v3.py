"""Pontuação v3 sobre o texto integral, pela API em lote. Subcomandos:

  preparar  --materias C1,C2 | --todas      escolhe, baixa, extrai, higieniza e conta tokens
  enviar    --rodada R --teto USD [--materias ...] [--taxa-cache X] [--saida-media N]
  coletar                                    recolhe lotes terminados e grava notas e respostas
  relatorio --rodada R                       custo, cache, legibilidade e amostras por matéria

Todos aceitam --raiz DIR (padrão: SENADO_VOLUME_ROOT ou o Volume). Um lote leva de minutos a
horas; `enviar` e `coletar` são separados para que nenhum processo fique esperando.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import anthropic
import requests
from databricks import sql
from dotenv import load_dotenv

from scripts.run_llm_scoring import (
    VOLUME_ROOT_PADRAO,
    buscar_chaves_existentes,
    chaves_no_volume,
    gravar_resposta_bruta,
    gravar_resultados,
)
from senado_pipeline.databricks_auth import (
    DATABRICKS_HTTP_PATH_PADRAO,
    DATABRICKS_SERVER_HOSTNAME_PADRAO,
    obter_secret,
)
from senado_pipeline.documento_processo import (
    FONTE_COMPOSTA,
    classificar_conteudo,
    escolher_documentos,
    etapa_da_votacao,
)
from senado_pipeline.emenda_destacada import SEM_BASE, base_da_emenda, dispositivo, remover_correspondente
from senado_pipeline.extrator_texto import extrair_texto_pdf, higienizar, vazamentos
from senado_pipeline.llm_scorer import VERSAO_EMENDA, VERSOES_V3, montar_conteudo_emenda, montar_conteudo_v3
from senado_pipeline.lote_scoring import (
    AMOSTRAS_V3,
    id_pedido,
    LIMITE_TOKENS_ENTRADA,
    MODELO_V3,
    contar_tentativas,
    custo_usd,
    estimar_custo,
    gasto_da_rodada,
    interpretar_resposta,
    montar_pedido,
    planejar_pedidos,
    modo_por_tamanho,
    sem_cache,
    somar_uso,
    texto_da_mensagem,
)

API_SENADO = "https://legis.senado.leg.br/dadosabertos"
GETTER = "https://legis.senado.gov.br/sdleg-getter/documento"
DIR_TEXTO = "materia_texto_integral"
DIR_LOTES = "materia_llm_lotes"


def conectar():
    return sql.connect(
        server_hostname=os.environ.get("DATABRICKS_SERVER_HOSTNAME") or DATABRICKS_SERVER_HOSTNAME_PADRAO,
        http_path=os.environ.get("DATABRICKS_HTTP_PATH") or DATABRICKS_HTTP_PATH_PADRAO,
        access_token=obter_secret("databricks-token", "DATABRICKS_TOKEN"),
    )


def cliente_anthropic():
    workspace_id = obter_secret("anthropic-workspace-id", "ANTHROPIC_WORKSPACE_ID", obrigatorio=False)
    return anthropic.Anthropic(
        api_key=obter_secret("anthropic-api-key", "ANTHROPIC_API_KEY"),
        default_headers={"anthropic-workspace-id": workspace_id} if workspace_id else {},
    )


def consultar(conn, comando: str) -> list[tuple]:
    cur = conn.cursor()
    try:
        cur.execute(comando)
        return cur.fetchall()
    finally:
        cur.close()


def buscar_materias_v3(conn) -> dict[str, dict]:
    """As matérias com posição no índice (objeto texto) e a votação de posição de cada uma."""
    linhas = consultar(conn, """
        WITH pos AS (SELECT DISTINCT codigo_materia, codigo_votacao FROM senado_votacoes.gold.mart_posicao_senador)
        SELECT m.codigo_materia, m.sigla, m.numero, m.ano, m.id_processo, m.ementa, t.descricao,
               CAST(fv.data_votacao AS STRING), fv.descricao_votacao
        FROM pos
        JOIN senado_votacoes.gold.dim_materia m ON m.codigo_materia = pos.codigo_materia
        JOIN senado_votacoes.gold.fact_votacao fv ON fv.codigo_votacao = pos.codigo_votacao
        JOIN senado_votacoes.gold.dim_tipo_materia t ON t.sigla = m.sigla
        WHERE t.materia_substantiva""")
    materias: dict[str, dict] = {}
    for c, sigla, numero, ano, id_proc, ementa, tipo, data_v, desc in linhas:
        if c in materias:
            raise RuntimeError(f"Matéria {c} com mais de uma votação de posição; a regra da spec §3 supõe uma.")
        materias[c] = {"codigo_materia": c, "sigla": sigla, "numero": numero, "ano": ano, "id_processo": id_proc,
                       "ementa": ementa, "tipo_descricao": tipo, "data_votacao": data_v[:10], "descricao_votacao": desc}
    return materias


def nomes_parlamentares(conn) -> list[str]:
    return [r[0] for r in consultar(conn, "SELECT DISTINCT nome_senador FROM senado_votacoes.gold.dim_senador")]


class Documentos:
    """Baixa e classifica PDFs, com cache em memória por id."""

    def __init__(self):
        self._ses = requests.Session()
        self._texto: dict[int, tuple[str, int]] = {}

    def catalogo(self, id_processo: str) -> list[dict]:
        r = self._ses.get(f"{API_SENADO}/processo/documento", params={"idProcesso": id_processo},
                          headers={"Accept": "application/json"}, timeout=300)
        r.raise_for_status()
        return r.json()

    def texto(self, id_documento: int) -> tuple[str, int]:
        if id_documento not in self._texto:
            r = self._ses.get(GETTER, params={"dm": id_documento}, timeout=900)
            r.raise_for_status()
            if "pdf" not in r.headers.get("content-type", ""):
                self._texto[id_documento] = ("", 0)
            else:
                self._texto[id_documento] = extrair_texto_pdf(r.content)
        return self._texto[id_documento]

    def emendas(self, id_processo: str) -> list[dict]:
        r = self._ses.get(f"{API_SENADO}/processo/emenda", params={"idProcesso": id_processo},
                          headers={"Accept": "application/json"}, timeout=300)
        r.raise_for_status()
        return r.json()

    def conteudo_de(self, doc: dict) -> str:
        texto, paginas = self.texto(int(doc["id"]))
        s = " ".join(texto.split())
        return classificar_conteudo(s[:6000], len(s), paginas, str(doc.get("identificacao") or ""))


def preparar(args, raiz: Path) -> int:
    if args.objeto == "emenda":
        return preparar_emendas(args, raiz)
    conn = conectar()
    try:
        materias = buscar_materias_v3(conn)
        nomes = nomes_parlamentares(conn)
    finally:
        conn.close()
    codigos = sorted(materias) if args.todas else args.materias.split(",")
    docs, cliente, falhas = Documentos(), cliente_anthropic(), []
    for codigo in codigos:
        m = materias[codigo]
        catalogo = docs.catalogo(m["id_processo"])
        escolha = escolher_documentos(codigo, m["sigla"], etapa_da_votacao(m["sigla"], m["descricao_votacao"]),
                                      date.fromisoformat(m["data_votacao"]), catalogo, docs.conteudo_de)
        if escolha is None:
            falhas.append(f"{codigo}: sem documento verificável (fica sem nota v3)")
            continue
        papeis = ["texto_recebido", "emendas_do_senado"] if escolha.fonte == FONTE_COMPOSTA else ["texto_votado"]
        documentos = [{"papel": p, "id_documento": i, "texto": higienizar(docs.texto(i)[0], nomes)}
                      for p, i in zip(papeis, escolha.ids_documento)]
        achados = [a for d in documentos for a in vazamentos(d["texto"], nomes)]
        if achados:
            falhas.append(f"{codigo}: higienização deixou {len(achados)} vazamento(s): {achados[:5]}")
            continue
        tokens = cliente.messages.count_tokens(
            model=MODELO_V3,
            messages=[{"role": "user", "content": montar_conteudo_v3(m, documentos, VERSOES_V3[0])}],
        ).input_tokens
        if tokens > LIMITE_TOKENS_ENTRADA:
            falhas.append(f"{codigo}: {tokens} tokens de entrada, acima do limite de {LIMITE_TOKENS_ENTRADA}")
            continue
        destino = raiz / DIR_TEXTO / f"{codigo}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps({"codigo_materia": codigo, "fonte": escolha.fonte,
                                       "ids_documento": list(escolha.ids_documento), "documentos": documentos,
                                       "tokens_entrada": tokens, "materia": m}, ensure_ascii=False), encoding="utf-8")
        print(f"{codigo} {m['sigla']} {m['numero']}/{m['ano']}: {escolha.fonte} {list(escolha.ids_documento)}, {tokens} tokens")
    for f in falhas:
        print(f"FALHA {f}")
    return 1 if falhas else 0


def preparar_emendas(args, raiz: Path) -> int:
    """Insumo de cada emenda destacada: o dispositivo (sem a justificação) e o texto-base, que
    depende do resultado da votação -- ver senado_pipeline/emenda_destacada.py."""
    conn = conectar()
    try:
        votacoes = consultar(conn, """
            SELECT v.codigo_materia, v.numero_objeto, v.resultado, CAST(v.data_votacao AS STRING),
                   v.descricao_votacao, m.id_processo, m.sigla, m.numero, m.ano, m.ementa, t.descricao
            FROM senado_votacoes.gold.fact_votacao v
            JOIN senado_votacoes.gold.dim_materia m ON m.codigo_materia = v.codigo_materia
            JOIN senado_votacoes.gold.dim_tipo_materia t ON t.sigla = m.sigla
            WHERE v.objeto_votado = 'emenda' AND t.materia_substantiva""")
        nomes = nomes_parlamentares(conn)
    finally:
        conn.close()
    pedidos = args.materias.split(",") if args.materias else None
    docs, cliente, falhas = Documentos(), cliente_anthropic(), []
    emendas_do_processo: dict[str, list[dict]] = {}
    for codigo, numero, resultado, data_v, desc, id_proc, sigla, num, ano, ementa, tipo in votacoes:
        if pedidos and codigo not in pedidos:
            continue
        materia = {"codigo_materia": codigo, "sigla": sigla, "numero": num, "ano": ano,
                   "ementa": ementa, "tipo_descricao": tipo}
        escolha_texto = escolher_documentos(codigo, sigla, etapa_da_votacao(sigla, desc),
                                            date.fromisoformat(data_v), docs.catalogo(id_proc),
                                            docs.conteudo_de)
        base = base_da_emenda(codigo, numero, resultado, escolha_texto)
        if base is None:
            motivo = SEM_BASE.get((codigo, numero), "aprovada sem base verificada")
            falhas.append(f"{codigo} emenda {numero}: sem base verificável ({motivo})")
            continue
        if id_proc not in emendas_do_processo:
            emendas_do_processo[id_proc] = docs.emendas(id_proc)
        alvo = [e for e in emendas_do_processo[id_proc] if str(e.get("numero")) == str(numero)]
        if not alvo:
            falhas.append(f"{codigo} emenda {numero}: não achada em /processo/emenda")
            continue
        disp = higienizar(dispositivo(docs.texto(int(alvo[0]["idDocumentoEmenda"]))[0]), nomes)
        papeis = ["texto_recebido", "emendas_do_senado"] if len(base.ids_documento) == 2 else ["texto_base"]
        documentos = []
        for papel, id_doc in zip(papeis, base.ids_documento):
            texto_doc = docs.texto(id_doc)[0]
            if base.remover_correspondente and papel == "emendas_do_senado":
                texto_doc = remover_correspondente(texto_doc, base.remover_correspondente)
            documentos.append({"papel": papel, "id_documento": id_doc,
                               "texto": higienizar(texto_doc, nomes)})
        achados = [a for d in documentos for a in vazamentos(d["texto"], nomes)] + vazamentos(disp, nomes)
        if achados:
            falhas.append(f"{codigo} emenda {numero}: higienização deixou {achados[:5]}")
            continue
        tokens = cliente.messages.count_tokens(
            model=MODELO_V3,
            messages=[{"role": "user", "content": montar_conteudo_emenda(materia, documentos, disp)}],
        ).input_tokens
        if tokens > LIMITE_TOKENS_ENTRADA:
            falhas.append(f"{codigo} emenda {numero}: {tokens} tokens, acima de {LIMITE_TOKENS_ENTRADA}")
            continue
        destino = raiz / DIR_TEXTO / f"emenda_{codigo}_{numero}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps({
            "codigo_materia": codigo, "numero_objeto": numero, "fonte": base.fonte,
            "ids_documento": list(base.ids_documento), "evidencia_base": base.evidencia,
            "resultado_votacao": resultado, "documentos": documentos, "dispositivo": disp,
            "tokens_entrada": tokens, "materia": materia}, ensure_ascii=False), encoding="utf-8")
        print(f"{codigo} emenda {numero} ({resultado}): {base.fonte} {list(base.ids_documento)}, {tokens} tokens")
    for f in falhas:
        print(f"FALHA {f}")
    return 1 if falhas else 0


def conteudo_do_insumo(t: dict, prompt_version: str) -> list[dict]:
    """O insumo preparado diz que prompt usar: quem tem numero_objeto é emenda."""
    if t.get("numero_objeto"):
        return montar_conteudo_emenda(t["materia"], t["documentos"], t["dispositivo"])
    return montar_conteudo_v3(t["materia"], t["documentos"], prompt_version)


def versoes_do_objeto(objeto: str) -> tuple[str, ...]:
    return (VERSAO_EMENDA,) if objeto == "emenda" else VERSOES_V3


def insumos(raiz: Path, objeto: str) -> dict[tuple[str, str], dict]:
    """Insumos preparados do objeto pedido, indexados por (codigo_materia, numero_objeto)."""
    achados = {}
    for p in (raiz / DIR_TEXTO).glob("*.json"):
        t = json.loads(p.read_text(encoding="utf-8"))
        e_emenda = bool(t.get("numero_objeto"))
        if e_emenda == (objeto == "emenda"):
            achados[(t["codigo_materia"], t.get("numero_objeto") or "texto")] = t
    return achados


def ler_registros(raiz: Path) -> list[dict]:
    pasta = raiz / DIR_LOTES
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(pasta.glob("*.json"))] if pasta.is_dir() else []


def gravar_registro(raiz: Path, registro: dict) -> None:
    pasta = raiz / DIR_LOTES
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{registro['id_lote']}.json").write_text(json.dumps(registro, ensure_ascii=False, indent=1), encoding="utf-8")


def registrar_resposta(raiz: Path, hoje: str, p: dict, texto: str, sucesso: bool, textos: dict,
                       origem: str, contagem: dict) -> None:
    """Grava a resposta crua de um pedido e, se legível, a nota. Serve ao lote e às chamadas comuns."""
    gravar_resposta_bruta(str(raiz), hoje, p["codigo_materia"], p["prompt_version"], p["amostra"],
                          p["tentativa"], texto, numero_objeto=p.get("numero_objeto") or "texto")
    if not sucesso:
        contagem["erro"] += 1
        return
    notas = interpretar_resposta(texto)
    if notas is None:
        contagem["ilegivel"] += 1
        return
    contagem["ok"] += 1
    t = insumo_do_pedido(textos, p)
    numero_objeto = p.get("numero_objeto") or "texto"
    gravar_resultados(str(raiz), [{
        "codigo_materia": p["codigo_materia"], "prompt_version": p["prompt_version"],
        "amostra": p["amostra"], "status": "ok", **notas,
        "objeto_votado": "emenda" if numero_objeto != "texto" else "texto",
        "numero_objeto": numero_objeto,
        "modelo": MODELO_V3, "fonte_texto": t["fonte"], "ids_documento": t["ids_documento"],
        "id_lote": origem, "tentativa": p["tentativa"],
    }], hoje)


def insumo_do_pedido(textos: dict, p: dict) -> dict:
    return textos[(p["codigo_materia"], p.get("numero_objeto") or "texto")]


def chamar(cliente, p: dict, insumo: dict):
    """Um pedido em chamada comum, com o bloco do documento marcado para cache."""
    params = montar_pedido(p, conteudo_do_insumo(insumo, p["prompt_version"]))["params"]
    # Até ~335 mil tokens de entrada: o padrão de 10 minutos do SDK pode não bastar.
    return cliente.messages.create(**params, timeout=1800)


def pontuar_sincrono(cliente, raiz: Path, rodada: str, codigo: str, pedidos: list[dict], textos: dict) -> tuple[dict, bool]:
    """Pedidos de uma matéria em chamadas comuns com cache: o primeiro sozinho grava o cache, o
    segundo sozinho confere que ele é lido, e os demais seguem 4 de cada vez. Devolve (registro,
    cache_pegou). Se o segundo não ler o cache, para ali: o resto da matéria fica para o lote."""
    hoje = date.today().isoformat()
    origem = f"sinc-{codigo}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    uso, contagem, feitos = {}, {"ok": 0, "ilegivel": 0, "erro": 0}, []

    def um(p):
        try:
            msg = chamar(cliente, p, insumo_do_pedido(textos, p))
        except Exception as exc:
            return p, f"<erro> {exc}", False, {}
        return p, texto_da_mensagem(msg), True, msg.usage.model_dump()

    def registrar(resultado):
        p, texto, sucesso, u = resultado
        somar_uso(uso, u)
        registrar_resposta(raiz, hoje, p, texto, sucesso, textos, origem, contagem)
        feitos.append(p)
        return u

    cache_pegou = True
    registrar(um(pedidos[0]))
    if len(pedidos) > 1:
        u2 = registrar(um(pedidos[1]))
        cache_pegou = (u2.get("cache_read_input_tokens") or 0) > 0
        if cache_pegou and len(pedidos) > 2:
            with ThreadPoolExecutor(max_workers=4) as ex:
                for resultado in ex.map(um, pedidos[2:]):
                    registrar(resultado)
    registro = {"id_lote": origem, "tipo": "sincrono", "rodada": rodada,
                "enviado_em": datetime.now(timezone.utc).isoformat(), "pedidos": feitos,
                "coletado": True, "uso": uso, "custo_usd": custo_usd(uso, lote=False),
                "contagem": contagem, "estimativa_usd": None}
    gravar_registro(raiz, registro)
    return registro, cache_pegou


def enviar(args, raiz: Path) -> int:
    textos = insumos(raiz, args.objeto)
    if args.materias:
        pedidas = set(args.materias.split(","))
        alvos = sorted(k for k in textos if k[0] in pedidas)
        faltando = sorted(pedidas - {k[0] for k in textos})
    else:
        # Sem lista, o modo escolhe os seus objetos pelo tamanho do insumo.
        alvos = sorted(k for k, t in textos.items() if modo_por_tamanho(t["tokens_entrada"]) == args.modo)
        faltando = []
    if faltando:
        print(f"Rode `preparar --objeto {args.objeto}` antes para: {faltando}")
        return 1
    conn = conectar()
    try:
        prontas = buscar_chaves_existentes(conn) | chaves_no_volume(str(raiz))
    finally:
        conn.close()
    registros = ler_registros(raiz)
    if args.modo == "lote" and any(not r.get("coletado") for r in registros):
        print("Há lote não coletado; rode `coletar` antes de enviar outro.")
        return 1
    total, na_rodada = contar_tentativas(registros, args.rodada)
    pedidos, esgotadas = planejar_pedidos(alvos, versoes_do_objeto(args.objeto), AMOSTRAS_V3,
                                          prontas, total, na_rodada)
    for chave in esgotadas:
        print(f"ESGOTADA na rodada {args.rodada}: {chave} (fica para a rodada seguinte)")
    if args.max_materias:
        permitidas = list(dict.fromkeys(p["codigo_materia"] for p in pedidos))[:args.max_materias]
        pedidos = [p for p in pedidos if p["codigo_materia"] in permitidas]
    if not pedidos:
        print("Nada a pedir.")
        return 0
    # Por MATÉRIA e não por objeto: as emendas destacadas de uma matéria compartilham o
    # texto-base, então gravam o cache uma vez, e o maior insumo é o que essa gravação custa.
    tokens: dict[str, int] = {}
    for (codigo_da_materia, _objeto), t in textos.items():
        tokens[codigo_da_materia] = max(tokens.get(codigo_da_materia, 0), t["tokens_entrada"])
    cliente = cliente_anthropic()

    if args.modo == "sincrono":
        # Agrupado por MATÉRIA: as emendas de uma matéria compartilham o texto-base em cache, e
        # separá-las em grupos pagaria a gravação do cache uma vez para cada emenda.
        por_materia: dict[str, list[dict]] = {}
        for p in pedidos:
            por_materia.setdefault(p["codigo_materia"], []).append(p)
        for codigo, dela in por_materia.items():
            estimativa = estimar_custo(tokens, dela, args.saida_media, "sincrono")
            gasto = gasto_da_rodada(ler_registros(raiz), args.rodada)
            if gasto + estimativa > args.teto:
                print(f"PARADO antes de {codigo}: gasto US$ {gasto:.2f} + estimativa US$ {estimativa:.2f} passa do teto US$ {args.teto:.2f}")
                return 1
            registro, cache_pegou = pontuar_sincrono(cliente, raiz, args.rodada, codigo, dela, textos)
            print(f"{codigo}: {len(registro['pedidos'])} pedidos, {registro['contagem']}; US$ {registro['custo_usd']:.3f} "
                  f"(estimado {estimativa:.3f}); cache gravado {registro['uso'].get('cache_creation_input_tokens', 0)}, "
                  f"lido {registro['uso'].get('cache_read_input_tokens', 0)}", flush=True)
            if registro["contagem"]["erro"]:
                print(f"PARADO: {registro['contagem']['erro']} chamada(s) com erro em {codigo} (saldo, limite de taxa ou rede); "
                      "a resposta crua de cada uma está em materia_llm_scores_resposta_bruta/.")
                return 1
            if not cache_pegou:
                print(f"PARADO: o cache não foi lido na segunda chamada de {codigo}. O modo síncrono deixa de compensar; "
                      "mande o restante em lote.")
                return 1
        return 0

    estimativa = estimar_custo(tokens, pedidos, args.saida_media, "lote")
    gasto = gasto_da_rodada(registros, args.rodada)
    print(f"{len(pedidos)} pedidos; estimativa US$ {estimativa:.2f}; já gasto na rodada US$ {gasto:.2f}; teto US$ {args.teto:.2f}")
    if gasto + estimativa > args.teto:
        print("RECUSADO: a estimativa passa do teto. Envie menos matérias ou revise o teto.")
        return 1
    lote = cliente.messages.batches.create(requests=[
        montar_pedido(p, sem_cache(conteudo_do_insumo(insumo_do_pedido(textos, p), p["prompt_version"])))
        for p in pedidos
    ])
    gravar_registro(raiz, {"id_lote": lote.id, "tipo": "lote", "rodada": args.rodada,
                           "enviado_em": datetime.now(timezone.utc).isoformat(), "pedidos": pedidos,
                           "coletado": False, "uso": None, "custo_usd": None, "contagem": None,
                           "estimativa_usd": estimativa})
    print(f"Lote {lote.id} enviado com {len(pedidos)} pedidos.")
    return 0


def coletar(args, raiz: Path) -> int:
    cliente = cliente_anthropic()
    hoje = date.today().isoformat()
    for registro in ler_registros(raiz):
        if registro.get("coletado"):
            continue
        lote = cliente.messages.batches.retrieve(registro["id_lote"])
        if lote.processing_status != "ended":
            print(f"Lote {lote.id}: {lote.processing_status} ({lote.request_counts})")
            continue
        textos = insumos(raiz, "texto") | insumos(raiz, "emenda")
        por_id = {id_pedido(p["codigo_materia"], p["prompt_version"], p["amostra"], p["tentativa"],
                            p.get("numero_objeto") or "texto"): p for p in registro["pedidos"]}
        uso_total, contagem = {}, {"ok": 0, "ilegivel": 0, "erro": 0}
        for item in cliente.messages.batches.results(lote.id):
            p = por_id[item.custom_id]
            sucesso = item.result.type == "succeeded"
            if sucesso:
                texto = texto_da_mensagem(item.result.message)
                somar_uso(uso_total, item.result.message.usage.model_dump())
            else:
                texto = f"<{item.result.type}> {getattr(item.result, 'error', '')}"
            registrar_resposta(raiz, hoje, p, texto, sucesso, textos, lote.id, contagem)
        registro.update({"coletado": True, "uso": uso_total, "custo_usd": custo_usd(uso_total), "contagem": contagem})
        gravar_registro(raiz, registro)
        print(f"Lote {lote.id}: {contagem}; custo US$ {registro['custo_usd']:.4f}; uso {uso_total}")
    return 0


def relatorio(args, raiz: Path) -> int:
    registros = [r for r in ler_registros(raiz) if r.get("rodada") == args.rodada and r.get("coletado")]
    uso, contagem = {}, {"ok": 0, "ilegivel": 0, "erro": 0}
    for r in registros:
        somar_uso(uso, r["uso"] or {})
        for k, v in (r["contagem"] or {}).items():
            contagem[k] += v
    n = sum(contagem.values())
    print(f"Rodada {args.rodada}: {len(registros)} lote(s), {n} pedidos, {contagem}")
    print(f"Custo apurado: US$ {gasto_da_rodada(registros, args.rodada):.4f} "
          f"(estimado: US$ {sum(r.get('estimativa_usd') or 0 for r in registros):.4f})")
    lidos = uso.get("cache_read_input_tokens", 0)
    gravados = uso.get("cache_creation_input_tokens", 0)
    print(f"Cache: {lidos} lidos, {gravados} gravados; taxa de leitura {lidos / max(lidos + gravados, 1):.0%}")
    if contagem["ok"]:
        print(f"Saída média por pedido legível: {uso.get('output_tokens', 0) / max(n - contagem['erro'], 1):.0f} tokens")
    prontas = chaves_no_volume(str(raiz))
    por_objeto: dict[tuple, int] = {}
    for c, objeto, v, _a in prontas:
        if v in VERSOES_V3 + (VERSAO_EMENDA,):
            por_objeto[(c, objeto, v)] = por_objeto.get((c, objeto, v), 0) + 1
    for (c, objeto, v), k in sorted(por_objeto.items()):
        rotulo = c if objeto == "texto" else f"{c} emenda {objeto}"
        print(f"  {rotulo} {v}: {k}/{AMOSTRAS_V3} amostras legíveis{'' if k == AMOSTRAS_V3 else '  <- INCOMPLETA'}")
    return 0


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", choices=["preparar", "enviar", "coletar", "relatorio"])
    ap.add_argument("--raiz", default=os.environ.get("SENADO_VOLUME_ROOT") or VOLUME_ROOT_PADRAO)
    ap.add_argument("--materias", default="")
    ap.add_argument("--objeto", choices=["texto", "emenda"], default="texto",
                    help="texto: a matéria na forma votada; emenda: cada emenda destacada, contra o seu texto-base")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--rodada", default="")
    ap.add_argument("--teto", type=float, default=25.0)
    ap.add_argument("--taxa-cache", type=float, default=0.0)
    ap.add_argument("--saida-media", type=int, default=1400)  # medido no piloto: 1.312
    ap.add_argument("--modo", choices=["lote", "sincrono"], default="lote",
                    help="lote: sem cache, com desconto; sincrono: chamadas comuns com cache, para documentos grandes")
    ap.add_argument("--max-materias", type=int, default=0)
    args = ap.parse_args()
    if args.comando in ("enviar", "relatorio") and not args.rodada:
        ap.error("--rodada é obrigatório")
    raiz = Path(args.raiz)
    return {"preparar": preparar, "enviar": enviar, "coletar": coletar, "relatorio": relatorio}[args.comando](args, raiz)


if __name__ == "__main__":
    sys.exit(main())
