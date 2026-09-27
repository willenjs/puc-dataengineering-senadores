# Carga dos Dados (Etapa 4.2)

Os dados não estão disponíveis como arquivo pronto. A API de Dados Abertos do Senado entrega JSON por endpoint, então foi seguido o caminho avançado: a coleta foi escrita em Python, com requisições diretas à API. Já havia experiência com esse tipo de extração, e a coleta passou a rodar dentro do próprio Databricks. Os dados chegam à nuvem sem passar por uma máquina local.

## Da API ao Volume

Cada tipo de dado tem um módulo em [`src/senado_pipeline/`](../src/senado_pipeline/) e é chamado por [`scripts/run_extraction.py`](../scripts/run_extraction.py). A extração cobre:

- os senadores da 57ª legislatura (`/senador/lista/legislatura/57`). Foi usada essa lista e não a "atual", porque a "atual" deixa de fora quem já saiu da cadeira mas votou durante o período;
- as matérias apresentadas em cada ano do recorte (`/materia/pesquisa/lista`);
- as votações do Plenário e o voto de cada senador;
- duas listas de referência: os tipos de situação de tramitação (`/processo/tipos-situacao`) e as siglas de tipos de matéria (`/processo/siglas`);
- o status de tramitação de cada processo (`/processo/{id}`), que também é o endpoint usado para obter o texto votado.

Os arquivos não vão para uma pasta local. Um módulo de escrita grava cada resposta como JSON em um Volume gerenciado do Unity Catalog, `/Volumes/senado_votacoes/bronze/raw_landing`, organizado por fonte e por data (`dt=AAAA-MM-DD`). Guardar a resposta bruta, sem tratamento, permite refazer qualquer etapa seguinte sem chamar a API de novo. Dali o Auto Loader ingere os arquivos nas tabelas Bronze (parecido com o Snowpipe que existe no Snowflake).

As coletas foram feitas entre 03/09 e 15/09/2026. Na mais recente, de 15/09, a votação nominal mais nova registrada pela API é de 03/09/2026.

O código separa a lógica da infraestrutura. As funções recebem o cliente HTTP e o cliente do Databricks como parâmetros, e os scripts em [`scripts/`](../scripts/) só ligam os clientes reais a elas. Isso permitiu testar a extração com respostas simuladas, sem rede e sem custo.

![Volume `raw_landing` no Catalog Explorer, com uma pasta por fonte.](imagens/4_2-volume-raw-landing.png)
*Figura 1: Volume `raw_landing` no Catalog Explorer, com uma pasta por fonte.*

![Arquivos JSON de votações gravados pela extração, particionados pela data da coleta (`dt=`).](imagens/4_2-volume-arquivos-votacoes.png)
*Figura 2: Arquivos JSON de votações gravados pela extração, particionados pela data da coleta (`dt=`).*

## Rodando no Databricks

A extração é a primeira tarefa do Job do Databricks, definido por um Databricks Asset Bundle ([`resources/jobs.yml`](../resources/jobs.yml)), e roda em computação serverless. Uma consequência prática é o acesso às credenciais. No Job não há arquivo `.env`, então uma função única, `obter_secret`, lê primeiro a variável de ambiente (para execuções locais) e, se ela não existir, busca no escopo de segredos `senado-votacoes` do Databricks. Nenhuma chave fica no repositório.

O Job também volta a coletar depois da primeira atualização do pipeline. A pesquisa de matérias por ano não devolve tudo o que acaba sendo votado, e só depois dessa atualização é possível comparar as matérias das votações com as já carregadas. A etapa de preenchimento de lacunas ([`scripts/run_materias_gap_fill.py`](../scripts/run_materias_gap_fill.py)) busca cada matéria que falta pelo endpoint de detalhe e grava o resultado no mesmo Volume. O status dos processos é coletado em outra tarefa ([`scripts/run_materia_status_fetch.py`](../scripts/run_materia_status_fetch.py)), em paralelo com a pontuação, porque as duas dependem só do mesmo estado da Silver e gravam em fontes diferentes.

![Tarefa `extracao` concluída numa execução do Job, em computação serverless.](imagens/4_2-job-tarefa-extracao.png)
*Figura 3: Tarefa `extracao` concluída numa execução do Job, em computação serverless.*

## Coleta do texto votado e pontuação pelo LLM

A segunda fonte, o texto de cada matéria na forma em que foi votada, dá mais trabalho que a API. O endpoint de processo lista os documentos de cada matéria em PDF, e o tipo que o catálogo do Senado atribui a cada documento não diz qual deles é o texto votado: uma redação final, por exemplo, aparece como parecer comum. Por isso o script lê o cabeçalho de cada PDF e escolhe o documento que corresponde à etapa votada. Nas 96 matérias do índice, a origem do texto ficou assim:

| Origem do texto | Matérias |
|---|---|
| Redação final | 39 |
| Redação para o turno suplementar | 17 |
| Redação para o segundo turno (PEC) | 14 |
| Autógrafo | 12 |
| Texto inicial, aprovado sem mudança | 8 |
| Texto recebido da Câmara com as emendas do Senado | 5 |
| Substitutivo | 1 |

A matéria para a qual nenhum documento pode ser verificado fica sem nota.

Depois o texto é extraído do PDF, limpo da identidade de quem propôs ou assinou (ver 4.1) e medido em tokens pela API do LLM, para que o custo seja conhecido antes do envio. O envio usa lotes (Message Batches), que custam menos, e chamadas diretas com cache para os documentos acima de cerca de 10 mil tokens, nos quais o cache barateia as nove repetições. A resposta completa do modelo é guardada no Volume, ao lado da nota, para que qualquer nota publicada possa ser conferida sem pagar pela chamada de novo.

Esse trabalho roda pelo script [`scripts/run_llm_scoring_v3.py`](../scripts/run_llm_scoring_v3.py), em três passos: `preparar`, `enviar` e `coletar`. As 96 matérias foram pontuadas em 17 e 18/09/2026, a um custo de cerca de US$ 33,70, piloto incluído. As 29 emendas destacadas foram pontuadas em 23 e 24/09/2026, por US$ 10,57.

## Dados pessoais

Os dados são públicos e oficiais: nomes de parlamentares, partidos, votos e textos de matérias. Não há dado de empresa nem informação sensível de cidadãos, então não foi necessário anonimizar nada antes de subir para o ambiente na nuvem.
