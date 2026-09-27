# Pipeline de Análise de Votações do Senado

## Trabalho (MVP de Engenharia de Dados)

Cada tópico do roteiro está num arquivo da pasta [`trabalho/`](trabalho/), com o mesmo nome no título:

| Tópico | Arquivo |
|---|---|
| Contexto de Negócios e Perguntas (Etapa 2 e 4.1) | [2-Objetivo.md](trabalho/2-Objetivo.md) e [4_1-BuscaDeDados.md](trabalho/4_1-BuscaDeDados.md) |
| Plataforma (Etapa 3) | [3-Plataforma.md](trabalho/3-Plataforma.md) |
| Carga dos Dados (Etapa 4.2) | [4_2-Coleta.md](trabalho/4_2-Coleta.md) |
| Modelagem e Catálogo de Dados (Etapa 4.3) | [4_3-Modelagem.md](trabalho/4_3-Modelagem.md) |
| Pipeline de Dados (Etapa 4.4) | [4_4-Carga.md](trabalho/4_4-Carga.md) |
| Qualidade de Dados (Etapa 4.5) | [4_5-AnaliseDeDados.md](trabalho/4_5-AnaliseDeDados.md) |
| Análise de Dados (Etapa 4.5) | [4_5-AnaliseDeDados.md](trabalho/4_5-AnaliseDeDados.md#análise-de-dados-etapa-45) |
| Autoavaliação | [5-Autoavaliacao.md](trabalho/5-Autoavaliacao.md) |

Os screenshots ficam em [`trabalho/imagens/`](trabalho/imagens/). Nos de resultado, a consulta SQL que os gera
aparece no documento, logo acima da imagem.

Pipeline de dados (Bronze/Silver/Gold) que ingere os Dados Abertos do Senado Federal
(senadores, matérias legislativas e votações da 57ª legislatura, 2023-2027), enriquece
cada matéria com uma nota de alinhamento socioeconômico gerada por LLM, e produz
métricas de "para quem cada senador legisla": classe baixa ou classe alta.

## Arquitetura

```
Senado API (legis.senado.leg.br/dadosabertos)
        │  Python (extração)
        ▼
   Volume (Unity Catalog) — JSON bruto, particionado por entidade/data de extração
        │  Auto Loader (Lakeflow)
        ▼
   BRONZE (Databricks) — payload bruto (VARIANT) + metadados de ingestão
        │  Lakeflow Declarative Pipelines
        ▼
   SILVER (Databricks) — entidades limpas, tipadas, deduplicadas
        │  Lakeflow (formaliza o star schema) + script Python (scoring por LLM)
        ▼
   GOLD (Databricks) — star schema formal + métricas de alinhamento
```

Stack: Python (extração + orquestração), Databricks (Unity Catalog managed Volume,
Lakeflow Declarative Pipelines, Databricks Asset Bundles/Jobs), Anthropic (Claude) para
o scoring de matérias. Todo o pipeline roda no Databricks Free Edition, sem AWS/S3.

### BRONZE

Payload bruto de cada fonte externa, sem transformação — schema
`senado_votacoes.bronze`, ingerido por Auto Loader a partir do Volume:

| Tabela | Origem |
|---|---|
| `senadores_lista_atual` | `GET /senador/lista/legislatura/57` — todos os titulares e suplentes da legislatura |
| `materias_pesquisa` | `GET /materia/pesquisa/lista?ano=YYYY` (2023-2026) |
| `materias_detalhe` | `GET /materia/{codigo}` — matérias referenciadas por uma votação mas não retornadas pela busca por ano |
| `votacoes_lista_anual` | `GET /arquivos/ListaVotacoes{ano}.json` (2023-2026) — já inclui os votos individuais aninhados |
| `materia_llm_scores_raw` | Resposta bruta do LLM para cada matéria pontuada |

### SILVER

Entidades limpas — uma por fonte Bronze, flatten + tipagem + deduplicação, **sem**
nomenclatura dimensional (schema `senado_votacoes.silver`, materialized views Lakeflow):

| Modelo | Grão |
|---|---|
| `senadores` | 1 linha por parlamentar da 57ª legislatura |
| `materias` | 1 linha por matéria (união de busca por ano + detalhe individual) |
| `votacoes` | 1 linha por votação |
| `votos` | 1 linha por (votação, senador) |
| `materia_scores` | 1 linha por matéria pontuada pelo LLM |

Testes de qualidade (`CONSTRAINT ... EXPECT ... ON VIOLATION FAIL UPDATE`) vivem aqui.

### GOLD

Dois grupos de modelos (schema `senado_votacoes.gold`):

**Star schema formal** — modelos finos (`SELECT * FROM senado_votacoes.silver.<entidade>`),
sem transformação adicional, formalizando a nomenclatura dimensional:

`dim_senador`, `dim_materia`, `dim_tipo_materia`, `dim_processo`, `dim_situacao_materia`, `fact_votacao`, `fact_voto_senador`, `fact_materia_scored`

Constraints `PRIMARY KEY`/`FOREIGN KEY` informacionais vivem aqui — é o contrato final para quem consome os dados.

**Marts de negócio** (prefixo `mart_`, deliberadamente distinto de `dim_`/`fact_` — são
respostas já agregadas, não fatos atômicos) — leem do star schema acima e de duas marts-base
(`mart_posicao_senador`, `mart_contribuicao_senador_materia`). São normalizadas: nome/partido/UF/foto
ficam em `dim_senador`, e quem consome faz o join:

| Modelo | Responde |
|---|---|
| `mart_posicao_senador` | Posição definitiva de cada senador em cada matéria concluída (a votação mais recente da matéria) — base das demais marts de voto |
| `mart_contribuicao_senador_materia` | Contribuição de cada posição Sim/Não em matéria substantiva para o índice de viés distributivo: eixo único `nota_classe_baixa − nota_classe_alta`, com o sinal do voto e centrado pela média do plenário na mesma matéria — base das marts de alinhamento e de destaque |
| `mart_alinhamento_senador` | Índice de viés distributivo por senador: quanto seus votos desviam do plenário na direção da classe baixa ou da alta. Classificação relativa (`classificacao_popular`, tercis entre senadores com 20 ou mais posições) + ranking |
| `mart_alinhamento_partido_uf` | Mesmo índice agregado por partido e UF |
| `mart_alinhamento_temporal` | Evolução do índice por senador, por ano |
| `mart_participacao_senador` | Taxa de participação nas votações (voto secreto conta como participação; o presidente da sessão sai do denominador) — contexto para avaliar a confiabilidade do índice |
| `mart_concordancia_par_senadores` | Taxa de concordância de voto entre cada par de senadores |
| `mart_coesao_bancada_uf` | Índice de coesão de voto da bancada de cada UF |
| `mart_destaque_senador` | Por senador, as duas pontas do eixo distributivo entre suas posições em matérias contestadas (5 ou mais votos Não): a de maior e a de menor contribuição centrada, que alimentam os destaques `pro_classe_baixa`/`pro_classe_alta`. A ponta não garante o sinal: um senador que nunca desviou do plenário numa direção tem, naquela ponta, contribuição menor ou igual a 0 |

Colunas de índice em `mart_alinhamento_senador`: `indice_vies_distributivo` (a base da
classificação e dos ranks), `indice_vies_bruto` (sem centragem, exposto só para
transparência), `indice_classe_baixa`/`indice_classe_alta` (descritivos: média das notas do
que o senador apoiou), `n_posicoes`/`n_posicoes_contestadas`, `elegivel_classificacao`,
`classificacao_popular` (`pro_classe_baixa`/`equilibrado`/`pro_classe_alta`, NULL abaixo de
20 posições) e `rank_pro_classe_baixa`/`rank_pro_classe_alta`. Só matérias de tipo
substantivo (`dim_tipo_materia.materia_substantiva`) entram no índice. Classe média foi
removida do produto a partir da Silver — ver nota abaixo. Cada matéria pontuada carrega
também uma justificativa textual por perfil:
`justificativa_classe_baixa`/`justificativa_classe_alta` em `fact_materia_scored`.

**Nota:** o payload bruto do LLM em `senado_votacoes.bronze.materia_llm_scores_raw` e o
prompt em `src/senado_pipeline/llm_scorer.py` usam para sempre os nomes originais
`nota_pobre`/`justificativa_pobre`/`nota_rico`/`justificativa_rico` — é o contrato já
usado para pontuar as matérias, e reprocessar custaria chamadas de API reais sem
benefício. O rename para `classe_baixa`/`classe_alta` acontece só a partir de
`silver.materia_scores` em diante.

Dicionário de dados completo (gerado do `information_schema` do Unity Catalog):
[`docs/data-dictionary.md`](docs/data-dictionary.md).

## Estrutura do projeto

```
src/senado_pipeline/          # Extração da API, escrita no Volume, scoring LLM, auth de segredos
scripts/                      # Entrypoints CLI que orquestram os módulos acima
lakeflow/transformations/     # Bronze (Auto Loader, Python) + Silver/Gold (SQL) do Lakeflow
resources/jobs.yml            # Job (orquestração) e Lakeflow Pipeline do bundle
databricks.yml                # Databricks Asset Bundle (artifacts, targets)
sql/databricks_bootstrap.sql  # DDL de bootstrap (catalog, schemas, Volume) + setup do secret scope
tests/                        # Testes pytest (TDD, mockam I/O externo)
trabalho/                     # Trabalho: um arquivo por tópico do roteiro (ver tabela no início) e screenshots de evidência
docs/data-dictionary.md       # Dicionário de dados gerado do information_schema
```

## Setup

```bash
python -m venv venv
source venv/Scripts/activate   # Windows (git bash); no Linux/Mac: source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
cp .env.example .env           # preencher com credenciais reais (só para rodar localmente)
```

Databricks CLI + bootstrap do workspace (uma vez):

```bash
databricks auth login --host <url-do-seu-workspace>
```

Depois, rodar `sql/databricks_bootstrap.sql` num SQL editor (cria o catalog, os schemas
`bronze`/`silver`/`gold` e o managed Volume) e criar o secret scope `senado-votacoes` —
os comandos exatos da CLI estão documentados como comentário no final desse mesmo arquivo.

Variáveis de ambiente necessárias (`.env`, só para rodar localmente — em produção o Job
lê as credenciais do secret scope): raiz do Volume (`SENADO_VOLUME_ROOT`), hostname e
HTTP path do SQL warehouse Databricks, token de acesso, API key da Anthropic e, se sua
chave for do tipo "identity-linked", `ANTHROPIC_WORKSPACE_ID`.

## Rodando o pipeline

Via Databricks Asset Bundle (recomendado — roda tudo no workspace, na ordem certa):

```bash
databricks bundle deploy -t dev
databricks bundle run -t dev extracao_job
```

O Job roda 7 tasks em sequência: extração → refresh do Lakeflow Pipeline → gap-fill de
matérias → refresh do pipeline → scoring por LLM → refresh do pipeline → geração do
dicionário de dados.

Rodando os passos individualmente a partir de uma máquina local (contra o mesmo
workspace):

```bash
# 1. Extração Bronze (Senado API -> Volume)
python scripts/run_extraction.py

# 2. Sobe o Lakeflow Pipeline (Bronze -> Silver -> Gold)
databricks bundle run -t dev medallion_pipeline

# 3. Preenche matérias referenciadas por votações mas fora do escopo da busca por ano
python scripts/run_materias_gap_fill.py
databricks bundle run -t dev medallion_pipeline

# 4. Pontua as matérias votadas via LLM (idempotente por (codigo_materia, prompt_version))
python scripts/run_llm_scoring.py
databricks bundle run -t dev medallion_pipeline

# 5. Regenera o dicionário de dados
python scripts/generate_data_dictionary.py
```

## Testes

```bash
pytest -v
```

Todos os testes usam dependency injection / mocks para I/O externo (API do Senado,
Databricks SQL, Anthropic) — não precisam de credenciais reais para rodar.
