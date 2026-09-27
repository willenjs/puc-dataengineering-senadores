"""Gera tests/fixtures/v3/documentos_96.json. Roda uma vez, com rede; não é teste.

Entrada: o resultado verificado da spec v3 §3 (classifica_conteudo_final.json, produzido e
conferido documento a documento em 2026-09-16/17) e o cache de texto dos PDFs. Para cada
matéria grava o catálogo INTEIRO de /processo/documento (a regra de candidatos é testada
contra ele, não contra uma lista já filtrada), a descrição da votação de posição e, para
cada documento cujo texto está no cache, o início do texto normalizado, o tamanho, as
páginas e o rótulo de conteúdo verificado.

Uso: python tests/fixtures/v3/gerar_fixture_documentos.py <classifica_conteudo_final.json> <posicao_votacao.json> <pdf_cache/>
"""
import json
import os
import sys
import time

import requests

API = "https://legis.senado.leg.br/dadosabertos"
RAIZ = os.path.dirname(os.path.abspath(__file__))
# Correções ao resultado de 2026-09-16/17, cada uma com o motivo. PL 2.159/2021 tem dois
# documentos só com as emendas, a redação final (9957469) e o autógrafo delas (9958995), com
# ~90% do texto em comum; o script de então pegou o primeiro da lista. A spec §3 nomeia a
# redação final, e as outras 4 matérias compostas usam a redação final.
CORRECOES_ESPERADO = {"148785": {"fonte": "COMPOSTO_INICIAL_MAIS_EMENDAS_DO_SENADO", "ids_documento": [8970277, 9957469]}}


def catalogo(id_processo: str) -> list[dict]:
    for tentativa in range(3):
        try:
            r = requests.get(f"{API}/processo/documento", params={"idProcesso": id_processo},
                             headers={"Accept": "application/json"}, timeout=300)
            r.raise_for_status()
            return [{"id": int(d["id"]), "siglaTipo": d.get("siglaTipo"),
                     "identificacao": d.get("identificacao"), "dataRecebimento": d.get("dataRecebimento")}
                    for d in r.json()]
        except Exception:
            if tentativa == 2:
                raise
            time.sleep(5)


def main(caminho_final: str, caminho_posicoes: str, cache: str) -> None:
    final = json.load(open(caminho_final, encoding="utf-8"))
    posicoes = {p["codigo_materia"]: p for p in json.load(open(caminho_posicoes, encoding="utf-8"))["posicoes"]}
    saida = []
    for item in final:
        pos = posicoes[item["codigo_materia"]]
        rotulos = {int(d["id"]): d["conteudo"] for d in item["docs"]}
        docs = {}
        cat = catalogo(pos["id_processo"])
        for d in cat:
            txt = os.path.join(cache, f"{d['id']}.txt")
            pags = os.path.join(cache, f"{d['id']}.pages")
            if os.path.exists(txt) and os.path.exists(pags):
                s = " ".join(open(txt, encoding="utf-8").read().split())
                docs[str(d["id"])] = {"inicio": s[:6000], "chars": len(s), "paginas": int(open(pags).read()),
                                      "conteudo_verificado": rotulos.get(d["id"])}
        ids = item["doc"] if isinstance(item["doc"], list) else [item["doc"]]
        fonte = {"INICIAL_A_VERIFICAR": "INICIAL_VERIFICADO"}.get(item["fonte"], item["fonte"])
        saida.append({
            "codigo_materia": item["codigo_materia"], "materia": item["materia"], "sigla": pos["sigla"],
            "data_votacao": item["data_votacao"], "descricao_votacao": pos["descricao_votacao"],
            "etapa_verificada": item["etapa"], "catalogo": cat, "textos": docs,
            "esperado": CORRECOES_ESPERADO.get(item["codigo_materia"],
                                               {"fonte": fonte, "ids_documento": [int(i) for i in ids]}),
        })
    json.dump(saida, open(os.path.join(RAIZ, "documentos_96.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"{len(saida)} matérias gravadas")


if __name__ == "__main__":
    main(*sys.argv[1:4])
