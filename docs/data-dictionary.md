# Dicionário de Dados — Senado Votações

## Schema `BRONZE`

### `materias_detalhe`

Payload bruto do detalhe individual de matérias referenciadas por votações mas ausentes da busca por ano (fonte: /materia/{codigo}).

| Coluna | Tipo | Descrição |
|---|---|---|
| `payload` | `variant` | _sem descrição_ |
| `_source_endpoint` | `string` | _sem descrição_ |
| `_loaded_at` | `timestamp` | _sem descrição_ |

### `materias_pesquisa`

Payload bruto da busca de matérias por ano (fonte: /materia/pesquisa/lista?ano=).

| Coluna | Tipo | Descrição |
|---|---|---|
| `payload` | `variant` | _sem descrição_ |
| `_source_endpoint` | `string` | _sem descrição_ |
| `_loaded_at` | `timestamp` | _sem descrição_ |

### `materia_llm_scores_raw`

Nota do LLM já interpretada, um arquivo por amostra: cada amostra de cada matéria e de cada emenda destacada pontuada (payload com as notas e justificativas do contrato congelado, prompt_version, amostra e status; as de emenda trazem também objeto_votado e numero_objeto). Escrita pelos scripts de pontuação. A resposta crua completa do modelo não entra aqui: fica no Volume, em materia_llm_scores_resposta_bruta/.

| Coluna | Tipo | Descrição |
|---|---|---|
| `payload` | `variant` | _sem descrição_ |
| `_source_endpoint` | `string` | _sem descrição_ |
| `_loaded_at` | `timestamp` | _sem descrição_ |

### `referencia_situacoes`

Payload bruto da lista de referência de situações de tramitação (fonte: /processo/tipos-situacao) -- domínio controlado, buscado por inteiro a cada execução.

| Coluna | Tipo | Descrição |
|---|---|---|
| `payload` | `variant` | _sem descrição_ |
| `_source_endpoint` | `string` | _sem descrição_ |
| `_loaded_at` | `timestamp` | _sem descrição_ |

### `referencia_tipos_materia`

Payload bruto da lista de referência de tipos/siglas de matéria (fonte: /processo/siglas) -- domínio controlado, buscado por inteiro a cada execução.

| Coluna | Tipo | Descrição |
|---|---|---|
| `payload` | `variant` | _sem descrição_ |
| `_source_endpoint` | `string` | _sem descrição_ |
| `_loaded_at` | `timestamp` | _sem descrição_ |

### `senadores_lista_atual`

Payload bruto da lista de parlamentares da 57ª legislatura (fonte: /senador/lista/legislatura/57).

| Coluna | Tipo | Descrição |
|---|---|---|
| `payload` | `variant` | _sem descrição_ |
| `_source_endpoint` | `string` | _sem descrição_ |
| `_loaded_at` | `timestamp` | _sem descrição_ |

### `status_processos`

Payload bruto do status de tramitação de processos legislativos referenciados por votações (fonte: /processo/{id}), escopado às matérias efetivamente votadas.

| Coluna | Tipo | Descrição |
|---|---|---|
| `payload` | `variant` | _sem descrição_ |
| `_source_endpoint` | `string` | _sem descrição_ |
| `_loaded_at` | `timestamp` | _sem descrição_ |

### `votacoes_lista_anual`

Payload bruto do arquivo anual de votações, já com os votos individuais aninhados (fonte: /arquivos/ListaVotacoes{ano}.json).

| Coluna | Tipo | Descrição |
|---|---|---|
| `payload` | `variant` | _sem descrição_ |
| `_source_endpoint` | `string` | _sem descrição_ |
| `_loaded_at` | `timestamp` | _sem descrição_ |

## Schema `GOLD`

### `dim_materia`

Star schema formal: uma matéria por linha (mesma entidade de silver.materias, sem transformação adicional).

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_materia` | `string` | Identificador único da matéria. |
| `sigla` | `string` | Sigla do tipo de matéria (PL, PEC, PLP, MPV, etc.) -- FK para dim_tipo_materia. |
| `numero` | `string` | Número da matéria dentro do seu tipo/ano. |
| `ano` | `int` | Ano de apresentação da matéria. |
| `ementa` | `string` | Título/descrição oficial da matéria. |
| `autor` | `string` | Autor da matéria. |
| `data_apresentacao` | `date` | Data de apresentação da matéria. |
| `id_processo` | `string` | Identificador do processo legislativo desta matéria -- FK para dim_processo, mas só populado lá para matérias efetivamente votadas (dim_processo é escopado, não cobre as ~18k matérias todas). |

### `dim_processo`

Star schema formal: um processo por linha (mesma entidade de silver.status_processos, sem transformação adicional). Escopado às matérias efetivamente votadas -- não cobre as ~18k matérias de dim_materia todas.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_processo` | `string` | Identificador do processo legislativo -- FK para dim_materia.id_processo. |
| `tramitando` | `string` | "Sim" se o processo ainda está em tramitação, "Não" se já concluiu. |
| `situacao_atual` | `string` | Texto da situação de tramitação atual. |
| `sigla_situacao_atual` | `string` | Código curto da situação atual -- FK para dim_situacao_materia. |
| `data_situacao_atual` | `date` | Data em que a situação atual foi atingida. |
| `materia_concluida` | `boolean` | tramitando = "Não" -- não é esperada nova votação sob este id_processo. |

### `dim_senador`

Star schema formal: um senador por linha (mesma entidade de silver.senadores, sem transformação adicional).

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_senador` | `string` | Identificador único do senador. |
| `nome_senador` | `string` | Nome parlamentar do senador. |
| `partido` | `string` | Sigla do partido do senador no momento da extração. |
| `uf` | `string` | Unidade federativa (estado) representada pelo senador. |
| `url_foto` | `string` | URL da foto oficial do senador. |
| `mandato_inicio` | `int` | Ano de início do mandato atual do senador. |
| `mandato_fim` | `int` | Ano de término do mandato atual do senador. |

### `dim_situacao_materia`

Star schema formal: domínio controlado de situações de tramitação (mesma entidade de silver.situacoes_materia, sem transformação adicional) -- dá significado a dim_processo.sigla_situacao_atual.

| Coluna | Tipo | Descrição |
|---|---|---|
| `sigla` | `string` | Código curto da situação de tramitação (ex.: TNJR, RMCD, APRVD). |
| `descricao` | `string` | Texto completo da situação de tramitação. |
| `data_inicio` | `date` | Data a partir da qual este código passou a ser usado. |
| `data_fim` | `date` | Data em que este código deixou de ser usado -- NULL quando ainda está ativo. |

### `dim_tipo_materia`

Star schema formal: domínio controlado de tipos/siglas de matéria (mesma entidade de silver.tipos_materia, sem transformação adicional) -- dá significado a dim_materia.sigla.

| Coluna | Tipo | Descrição |
|---|---|---|
| `sigla` | `string` | Sigla do tipo de matéria (ex.: PL, PEC, PLP, MPV, VET, RQS). |
| `descricao` | `string` | Nome completo do tipo de matéria. |
| `data_inicio` | `date` | Data a partir da qual esta sigla passou a ser usada. |
| `data_fim` | `date` | Data em que esta sigla deixou de ser usada -- NULL quando ainda está ativa. |
| `materia_substantiva` | `boolean` | true para tipos de matéria legislativa com conteúdo normativo próprio (PL, PLP, PEC, MPV, PLC, PLS, PLN, SCD, PRS, PDS, VET); false para atos procedimentais, nomeações e comunicações (MSF, OFS, RQS, REQ, PDL, etc.). Filtro de entrada do índice de viés distributivo (mart_contribuicao_senador_materia) e do scoring por LLM (scripts/run_llm_scoring.py). |

### `fact_emenda_scored`

Star schema formal: nota de cada emenda destacada (mesma entidade de silver.emenda_scores). A nota é de um DELTA -- o efeito de aprovar a emenda em relação ao texto-base --, e por isso não é comparável com a de fact_materia_scored, que é de nível.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_materia` | `string` | FK para dim_materia. |
| `numero_objeto` | `string` | Número da emenda destacada (fact_votacao.numero_objeto). |
| `prompt_version` | `string` | Versão do prompt (emenda-v1) -- ver silver_emenda_scores.sql. |
| `n_amostras` | `int` | Sempre 9: a mediana das 9 amostras. |
| `nota_classe_baixa` | `double` | Mediana da nota do DELTA para a classe baixa: o efeito de aprovar a emenda em relação ao texto-base. |
| `justificativa_classe_baixa` | `string` | Justificativa da amostra cuja nota de classe baixa é a mediana. |
| `amostra_justificativa_classe_baixa` | `int` | De qual amostra veio justificativa_classe_baixa (fact_materia_score_amostra). |
| `nota_classe_alta` | `double` | Mediana da nota do DELTA para a classe alta. |
| `justificativa_classe_alta` | `string` | Justificativa da amostra cuja nota de classe alta é a mediana. |
| `amostra_justificativa_classe_alta` | `int` | De qual amostra veio justificativa_classe_alta. |
| `fonte_texto` | `string` | Documento que serviu de texto-base. |
| `ids_documento` | `string` | Ids dos PDFs do texto-base, separados por vírgula. |

### `fact_emenda_score_amostra`

Star schema formal: cada amostra de nota de emenda destacada (mesma entidade de silver.emenda_scores_amostras). fact_emenda_scored é a nota publicada; esta é a matéria-prima dela e da reamostragem de mart_estabilidade_rotulo_senador.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_materia` | `string` | FK para dim_materia. |
| `numero_objeto` | `string` | Número da emenda destacada (fact_votacao.numero_objeto). |
| `prompt_version` | `string` | Versão do prompt da amostra (emenda-v1). |
| `amostra` | `int` | Índice da repetição desta (matéria, versão). |
| `nota_classe_baixa` | `double` | Nota desta amostra para a classe baixa. |
| `justificativa_classe_baixa` | `string` | Justificativa desta amostra para a classe baixa. |
| `nota_classe_alta` | `double` | Nota desta amostra para a classe alta. |
| `justificativa_classe_alta` | `string` | Justificativa desta amostra para a classe alta. |
| `fonte_texto` | `string` | Documento que serviu de texto-base. |
| `ids_documento` | `string` | Ids dos PDFs do texto-base, separados por vírgula. |

### `fact_materia_scored`

Star schema formal: nota de alinhamento por matéria (mesma entidade de silver.materia_scores, sem transformação adicional).

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_materia` | `string` | FK para dim_materia. |
| `prompt_version` | `string` | Versão do prompt da nota vigente (v3-com-empurrao, v2 ou v1) -- ver silver_materia_scores.sql. |
| `n_amostras` | `int` | Quantas amostras formam a nota: 9 na v3 (mediana), 1 na v1 e na v2. |
| `nota_classe_baixa` | `double` | Nota de -1 (prejudicial) a 1 (benéfico) do impacto da matéria para o brasileiro de classe baixa. Na v3, a mediana das 9 amostras. |
| `justificativa_classe_baixa` | `string` | Justificativa da amostra cuja nota de classe baixa é a mediana. |
| `amostra_justificativa_classe_baixa` | `int` | De qual amostra veio justificativa_classe_baixa (fact_materia_score_amostra). |
| `nota_classe_alta` | `double` | Nota de -1 a 1 do impacto da matéria para o brasileiro de classe alta. Na v3, a mediana das 9 amostras. |
| `justificativa_classe_alta` | `string` | Justificativa da amostra cuja nota de classe alta é a mediana. |
| `amostra_justificativa_classe_alta` | `int` | De qual amostra veio justificativa_classe_alta. |
| `fonte_texto` | `string` | Documento pontuado na v3 (NULL na v1/v2, que pontuavam a ementa). |
| `ids_documento` | `string` | Ids dos PDFs pontuados na v3, separados por vírgula. |

### `fact_materia_score_amostra`

Star schema formal: cada amostra de nota por LLM, de todas as versões (mesma entidade de silver.materia_scores_amostras). fact_materia_scored é a nota publicada; esta é a matéria-prima dela e da reamostragem de mart_estabilidade_rotulo_senador, e é onde se audita a variação entre amostras.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_materia` | `string` | FK para dim_materia. |
| `prompt_version` | `string` | Versão do prompt da amostra, publicada ou não (inclui v3-sem-empurrao, que perdeu o teste A/B). |
| `amostra` | `int` | Índice da repetição desta (matéria, versão). |
| `nota_classe_baixa` | `double` | Nota desta amostra para a classe baixa. |
| `justificativa_classe_baixa` | `string` | Justificativa desta amostra para a classe baixa. |
| `nota_classe_alta` | `double` | Nota desta amostra para a classe alta. |
| `justificativa_classe_alta` | `string` | Justificativa desta amostra para a classe alta. |
| `fonte_texto` | `string` | Documento pontuado (v3). |
| `ids_documento` | `string` | Ids dos PDFs pontuados (v3), separados por vírgula. |

### `fact_votacao`

Star schema formal: uma votação por linha (mesma entidade de silver.votacoes, sem transformação adicional).

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_votacao` | `string` | Identificador único da votação. |
| `codigo_materia` | `string` | FK para dim_materia -- matéria que foi objeto desta votação. |
| `data_votacao` | `date` | Data em que a votação ocorreu. |
| `sequencial_sessao` | `int` | Ordem desta votação dentro da sessão plenária -- distingue 1º/2º turno, texto principal vs. destaque. |
| `resultado` | `string` | Resultado declarado da votação: "A" aprovada, "R" rejeitada. Vem da fonte, nunca da contagem de votos -- um destaque pode ter mais Sim que Não e ser rejeitado por falta de quórum qualificado. Ver silver_votacoes.sql. |
| `descricao_votacao` | `string` | Texto descrevendo o que especificamente foi votado nesta votação (matéria como um todo, emenda, destaque, etc.). |
| `objeto_votado` | `string` | Objeto decidido nesta votação: "texto", "emenda", "artigo" ou "requerimento"; NULL quando a descrição não casa com nenhum padrão conhecido. Allowlist derivada em silver_votacoes.sql -- a expressão vive lá e só lá; consumidores leem esta coluna. |
| `numero_objeto` | `string` | Número do objeto destacado ("157" para a Emenda 157), "texto" quando o objeto é o texto da matéria, NULL quando o destaque não numera o objeto. Ver silver_votacoes.sql. |

### `fact_voto_senador`

Star schema formal: um voto por linha (mesma entidade de silver.votos, sem transformação adicional).

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_votacao` | `string` | FK para fact_votacao. |
| `codigo_senador` | `string` | FK para dim_senador. |
| `voto_raw` | `string` | Valor original do campo Voto retornado pela API. |
| `voto` | `string` | Voto normalizado em 5 categorias: Sim, Não, Abstenção, Secreto (votação secreta) ou Ausente -- ver silver_votos.sql para o mapeamento completo a partir de voto_raw. |

### `mart_alinhamento_partido_uf`

Mesmo índice de viés distributivo de mart_alinhamento_senador, agregado por partido e UF, com as mesmas regras de denominador: não unânimes no índice centrado, todas nas colunas descritivas. A centragem por matéria é a do plenário inteiro, calculada uma vez em mart_contribuicao_senador_materia -- não é recalculada dentro do partido. Todo partido/UF com ao menos 1 senador aparece aqui, mesmo sem nenhuma posição -- ver nota sobre LEFT JOIN abaixo.

| Coluna | Tipo | Descrição |
|---|---|---|
| `partido` | `string` | Sigla do partido. |
| `uf` | `string` | Unidade federativa. |
| `indice_classe_baixa` | `double` | Média de contribuicao_classe_baixa sobre todas as posições dos senadores do partido/UF, unânimes incluídas (ver mart_alinhamento_senador: coluna não centrada, a posição unânime vale a nota inteira). Descritivo. |
| `indice_classe_alta` | `double` | Média de contribuicao_classe_alta sobre todas as posições dos senadores do partido/UF, unânimes incluídas. Descritivo. |
| `indice_vies_distributivo` | `double` | Média de contribuicao_centrada sobre as posições não unânimes dos senadores do partido/UF: positivo = a bancada desvia do plenário na direção da classe baixa. Média por POSIÇÃO, não média dos índices individuais -- senadores com mais posições pesam mais. |
| `n_posicoes` | `bigint` | Total de posições Sim/Não em matérias substantivas pontuadas somadas sobre os senadores do partido/UF. Denominador das duas colunas descritivas. |
| `n_posicoes_nao_unanimes` | `bigint` | Dentre n_posicoes, quantas não foram unânimes no plenário. É o denominador de indice_vies_distributivo, a mesma população que mart_alinhamento_senador promedia no índice centrado -- se as duas views usassem denominadores diferentes, a média por partido deixaria de ser comparável com a média por senador sob o mesmo nome. |
| `qtd_senadores` | `bigint` | Quantidade de senadores distintos do partido/UF, incluindo os que nunca se manifestaram Sim ou Não em nenhuma matéria substantiva pontuada (esses não contribuem pra média, mas contam aqui). |

### `mart_alinhamento_senador`

Índice de viés distributivo por senador: quanto seus votos desviam do plenário na direção da classe baixa ou da classe alta, num eixo único (nota_classe_baixa - nota_classe_alta) centrado por matéria. O índice centrado é promediado sobre as posições não unânimes (ver n_posicoes_nao_unanimes); as colunas descritivas, sobre todas. Classificação e ranks são relativos (tercis entre os elegíveis), não absolutos, e o rótulo publicado (classificacao_popular) só sai quando é estável sob o ruído do avaliador -- a normalização min-max independente por eixo usada até 2026-09-14 classificava 98 de 102 senadores como "amigo do povo" e foi removida. Todo senador de dim_senador aparece aqui; sem posição, os índices ficam NULL e as contagens 0. Nome/partido/UF/foto ficam em dim_senador -- consumidores fazem o join.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_senador` | `string` | FK para dim_senador. |
| `indice_classe_baixa` | `double` | Média de contribuicao_classe_baixa (nota da classe baixa com o sinal do voto) sobre TODAS as posições Sim/Não do senador em matérias substantivas pontuadas, unânimes incluídas. Descritivo -- "média das notas do que o senador apoiou" -- não é a base da classificação nem dos ranks. Não recebe o filtro de unanimidade de propósito: a coluna não é centrada, então numa matéria unânime a posição vale a nota inteira, e excluí-la apagaria dado real (49 das 96 matérias com posição em 2026-09-16 eram unânimes). |
| `indice_classe_alta` | `double` | Mesma lógica de indice_classe_baixa (ver acima), para nota_classe_alta. |
| `indice_vies_distributivo` | `double` | Média de contribuicao_centrada (mart_contribuicao_senador_materia) sobre as posições NÃO UNÂNIMES do senador -- a única coluna com esse filtro, porque é a única centrada: numa matéria unânime a centragem zera a contribuição de todo mundo, e mantê-la no denominador só encolheria o senador em direção a 0. Positivo = desvia do plenário na direção da classe baixa; negativo = na direção da classe alta. Base de classificacao_popular e dos dois ranks. |
| `indice_vies_bruto` | `double` | Média de contribuicao_bruta (sem centragem) sobre TODAS as posições, unânimes incluídas, pelo mesmo motivo de indice_classe_baixa. Mede a pauta em que o senador se posicionou, não seu desvio em relação aos colegas -- exposto só para transparência e comparação com indice_vies_distributivo. |
| `n_posicoes` | `bigint` | Quantidade de matérias substantivas pontuadas em que o senador votou Sim ou Não. 0 para senador sem nenhuma posição. Denominador das três colunas descritivas (indice_classe_baixa, indice_classe_alta, indice_vies_bruto); NÃO é o denominador do índice centrado nem a base da elegibilidade. |
| `n_posicoes_nao_unanimes` | `bigint` | Dentre n_posicoes, quantas tiveram ao menos um voto de cada lado no plenário (least(n_sim_plenario, n_nao_plenario) > 0). É o denominador de indice_vies_distributivo e a base de elegivel_classificacao, e só dessas duas: as colunas descritivas não são centradas e usam n_posicoes. Numa matéria unânime todo senador fez a mesma coisa e a centragem já a zera no numerador por construção: mantê-la no denominador não acrescentaria informação, só encolheria cada senador em direção a 0 na proporção de quantos consensos ele frequentou -- e deixaria um senador baixar o próprio índice comparecendo a mais votações unânimes. |
| `n_posicoes_contestadas` | `bigint` | Dentre n_posicoes, quantas em matérias com 5 ou mais votos Não no plenário -- indicador de quanto do índice vem de votações realmente disputadas. Informação para a UI e critério de candidatura em mart_destaque_senador; não é base de cálculo nem de elegibilidade aqui (o corte em 5 seria arbitrário, e a faixa de 1 a 4 dissidentes é onde mora o voto isolado, que é a declaração máxima de desvio). |
| `elegivel_classificacao` | `boolean` | n_posicoes_nao_unanimes >= 20. O mínimo amostral conta a MESMA população que os índices promediam: com o corte sobre n_posicoes, um senador com 20 posições das quais 2 informativas receberia classificação sobre uma média de 2 observações. Só senadores elegíveis recebem classificacao_popular e ranks; abaixo disso o índice existe mas é ruidoso demais para rotular (os dois únicos "inimigos" da versão anterior tinham 3 e 2 votos). |
| `classificacao_pontual` | `string` | Tercil de indice_vies_distributivo entre os senadores elegíveis, calculado sobre a nota publicada: "pro_classe_baixa" (tercil superior), "equilibrado" (tercil médio), "pro_classe_alta" (tercil inferior). É a classificação que a nota publicada dá, sem considerar o ruído do avaliador; NÃO é o rótulo publicado (ver classificacao_popular). NULL quando não elegível. |
| `classificacao_popular` | `string` | O rótulo publicável: o tercil que o senador ocupa em pelo menos 95% das 4000 reamostragens do ruído do avaliador (mart_estabilidade_rotulo_senador) -- "pro_classe_baixa", "equilibrado" ou "pro_classe_alta" --, ou "na_fronteira" quando nenhum tercil chega a 95% (ver fronteira_entre). Classificação RELATIVA aos demais senadores, não faixa fixa. NULL quando não elegível -- distingue "sem dados suficientes" de "equilibrado". Com uma única amostra por matéria, 10 de 81 senadores trocavam de tercil entre duas rodadas idênticas; por isso o rótulo só é publicado quando é estável (decisão de 2026-09-16). |
| `estabilidade_classificacao` | `double` | Fração das reamostragens em que saiu o rótulo mais frequente (mart_estabilidade_rotulo_senador.estabilidade). 0,95 ou mais publica o rótulo. NULL quando não elegível. |
| `fronteira_entre` | `string` | Quando classificacao_popular = "na_fronteira", os dois rótulos mais frequentes nas reamostragens, na ordem do eixo (ex.: "pro_classe_baixa|equilibrado"). NULL nos demais casos. |
| `rank_pro_classe_baixa` | `int` | Posição no ranking decrescente de indice_vies_distributivo entre os elegíveis (1 = maior desvio na direção da classe baixa). NULL quando não elegível. |
| `rank_pro_classe_alta` | `int` | Posição no ranking crescente de indice_vies_distributivo entre os elegíveis (1 = maior desvio na direção da classe alta). Num eixo único é o mesmo ranking em ordem oposta; os dois nomes continuam corretos. NULL quando não elegível. |

### `mart_alinhamento_temporal`

Evolução do índice de viés distributivo de cada senador ao longo dos anos da legislatura, com as mesmas regras de denominador de mart_alinhamento_senador: não unânimes no índice centrado, todas nas colunas descritivas. Nome fica em dim_senador -- consumidores fazem o join. Diferente de mart_alinhamento_senador/mart_alinhamento_partido_uf, aqui não existe uma dimensão "todos os anos possíveis" pra fazer LEFT JOIN contra -- um (senador, ano) só aparece quando há posição real naquele ano; ausência de um ano é informação genuína (sem atividade pontuável), não um bug de sparsity.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_senador` | `string` | FK para dim_senador. |
| `ano` | `int` | Ano da votação que definiu a posição (fact_votacao.data_votacao, via o codigo_votacao herdado de mart_contribuicao_senador_materia). |
| `indice_classe_baixa` | `double` | Média de contribuicao_classe_baixa de todas as posições do senador naquele ano, unânimes incluídas (ver mart_alinhamento_senador). Descritivo. |
| `indice_classe_alta` | `double` | Média de contribuicao_classe_alta de todas as posições do senador naquele ano, unânimes incluídas. Descritivo. |
| `indice_vies_distributivo` | `double` | Média de contribuicao_centrada das posições não unânimes do senador naquele ano. A centragem é a do plenário na matéria, calculada uma vez em mart_contribuicao_senador_materia -- não é recalculada por ano, para que os anos continuem comparáveis entre si. |
| `n_posicoes` | `bigint` | Posições Sim/Não do senador em matérias substantivas pontuadas naquele ano. Denominador das duas colunas descritivas. |
| `n_posicoes_nao_unanimes` | `bigint` | Dentre n_posicoes, quantas não foram unânimes no plenário. É o denominador de indice_vies_distributivo, a mesma população que mart_alinhamento_senador promedia no índice centrado. Sem corte de elegibilidade nesta view: um ano com poucas posições é informação, não motivo de exclusão. Pode ser 0, e nesse caso indice_vies_distributivo fica NULL -- o senador se posicionou naquele ano, mas só em consensos, e "nenhum desvio observável" é diferente de "desvio zero". |

### `mart_coesao_bancada_uf`

Índice de coesão de voto da bancada de cada UF, considerando só votações em que a bancada completa (3 senadores distintos daquela UF) se manifestou.

| Coluna | Tipo | Descrição |
|---|---|---|
| `uf` | `string` | Unidade federativa. |
| `votacoes_com_bancada_completa` | `bigint` | Quantidade de votações em que exatamente 3 senadores distintos da UF manifestaram posição (Sim/Não/Abstenção) -- bancada avaliada por votação, não contra um roster fixo. |
| `votacoes_unanimes` | `bigint` | Dentre votacoes_com_bancada_completa, quantidade em que os 3 senadores votaram de forma idêntica. |
| `indice_coesao` | `double` | votacoes_unanimes dividido por votacoes_com_bancada_completa. |

### `mart_concordancia_par_senadores`

Taxa de concordância de voto entre cada par de senadores, contada por votação. Nome/partido/UF/foto de cada senador ficam em dim_senador -- consumidores fazem o join.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_senador_a` | `string` | FK para dim_senador -- menor dos dois códigos do par (ordem lexical de string). |
| `codigo_senador_b` | `string` | FK para dim_senador -- o outro senador do par. |
| `votacoes_em_comum` | `bigint` | Quantidade de VOTAÇÕES em que ambos os senadores do par manifestaram posição (Sim/Não/Abstenção). Uma linha por decisão do plenário: os dois turnos de uma PEC contam duas vezes, cada destaque conta por si, e requerimentos contam -- todas são decisões distintas em que os dois ou votaram igual ou não. |
| `votacoes_concordantes` | `bigint` | Dentre votacoes_em_comum, quantidade em que os dois votaram de forma idêntica. |
| `taxa_concordancia` | `double` | votacoes_concordantes dividido por votacoes_em_comum. |

### `mart_contribuicao_senador_materia`

Contribuição de cada posição (senador x objeto votado) para o índice de viés distributivo: eixo único nota_classe_baixa - nota_classe_alta, com o sinal do voto e centrado pela média do plenário no mesmo objeto. O objeto é o texto da matéria (nota de nível, de fact_materia_scored) ou uma emenda destacada (nota de delta, de fact_emenda_scored); a centragem é feita dentro do objeto, porque o plenário de uma emenda não é o do texto. Só matérias substantivas (dim_tipo_materia.materia_substantiva), pontuadas e concluídas (mart_posicao_senador já garante a conclusão). Base de mart_alinhamento_senador, mart_alinhamento_partido_uf, mart_alinhamento_temporal e mart_destaque_senador -- a lógica de sinal/viés/centragem vive só aqui, no mesmo papel que mart_posicao_senador já cumpre para a resolução de posição definitiva.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_senador` | `string` | FK para dim_senador. |
| `codigo_materia` | `string` | FK para dim_materia. |
| `objeto_votado` | `string` | Objeto que o senador votou: "texto" (o texto da matéria) ou "emenda" (emenda destacada). A nota do texto é de NÍVEL e a da emenda é de DELTA (o efeito de aprová-la em relação ao texto-base), mas as duas entram no índice do mesmo jeito: com o sinal do voto e centradas pela média do plenário NAQUELE objeto. |
| `numero_objeto` | `string` | Número do objeto: "texto" ou o número da emenda destacada. |
| `codigo_votacao` | `string` | FK para fact_votacao -- a votação que definiu a posição (herdada de mart_posicao_senador). |
| `voto` | `string` | Sim ou Não (posição definitiva, de mart_posicao_senador). Abstenção/Ausente/Secreto não geram linha -- sem sentido de voto não há direção a atribuir. |
| `nota_classe_baixa` | `double` | Nota do objeto para a classe baixa: de fact_materia_scored quando o objeto é o texto (nível), de fact_emenda_scored quando é uma emenda destacada (delta). |
| `nota_classe_alta` | `double` | Nota do objeto para a classe alta: de fact_materia_scored quando o objeto é o texto (nível), de fact_emenda_scored quando é uma emenda destacada (delta). |
| `vies_distributivo` | `double` | nota_classe_baixa - nota_classe_alta, em [-2, 2]. Positivo = o objeto favorece a classe baixa mais que a alta. Eixo único: uma matéria boa para as duas classes tem viés ~0 e deixa de inflar o índice, ao contrário dos dois eixos independentes usados até 2026-09-14. |
| `contribuicao_classe_baixa` | `double` | nota_classe_baixa com o sinal do voto (Sim mantém, Não inverte). |
| `contribuicao_classe_alta` | `double` | nota_classe_alta com o sinal do voto (Sim mantém, Não inverte). |
| `contribuicao_bruta` | `double` | vies_distributivo com o sinal do voto: apoiar matéria pró-classe-baixa ou bloquear matéria pró-classe-alta é positivo; o inverso é negativo. |
| `contribuicao_centrada` | `double` | contribuicao_bruta menos a média de contribuicao_bruta entre todos os senadores que se posicionaram (Sim/Não) neste objeto. Mede o desvio do senador em relação ao plenário; objeto votado por unanimidade dá exatamente 0 para todo mundo, por construção. |
| `n_sim_plenario` | `bigint` | Quantidade de senadores que votaram Sim neste objeto (posição definitiva). |
| `n_nao_plenario` | `bigint` | Quantidade de senadores que votaram Não neste objeto (posição definitiva). Um objeto é considerado "contestado" a partir de 5 votos Não -- limiar usado por mart_alinhamento_senador.n_posicoes_contestadas e como filtro de candidatas em mart_destaque_senador. |

### `mart_convergencia_senado`

Convergência do Senado com cada classe: quanto o plenário, como um todo, aprovou o que beneficia aquela classe. Alimenta o medidor "Convergência Média do Senado" da Tríade no site. Substitui a média das médias por senador de indice_classe_baixa/indice_classe_alta que o site calculava até 2026-09-16, que tinha dois defeitos: pesava igualmente um senador com 2 posições e um com 90, e, enquanto aquelas colunas excluíam as posições unânimes, deixava de fora exatamente as votações em que o Senado convergiu. É uma medida por matéria e não por senador, e por isso lê mart_contribuicao_senador_materia, onde o sinal do voto e as contagens do plenário já estão resolvidos.

| Coluna | Tipo | Descrição |
|---|---|---|
| `classe` | `string` | Classe a que o indicador se refere: "baixa" ou "alta". Os nomes seguem nota_classe_baixa/nota_classe_alta e o tipo Classe do site. |
| `indice_convergencia` | `double` | Em [-1, 1]. Para cada matéria substantiva pontuada com posição, o apoio líquido do plenário, (votos Sim - votos Não) / (Sim + Não), multiplicado pela nota da matéria para a classe; depois a média simples entre as matérias. Positivo = o Senado aprovou mais o que beneficia a classe e barrou mais o que a prejudica; 0 = neutro. Escala ABSOLUTA e sem constante calibrada: os limites -1 e +1 são os da própria nota, não os do intervalo observado, então o número não muda de significado quando as notas da v3 chegarem. É pequeno em módulo porque o efeito é pequeno, não por defeito de escala. |
| `n_materias` | `bigint` | Quantidade de matérias na média. Cada matéria pesa igual, qualquer que seja o número de senadores que votou nela: a pergunta é o que o Senado decidiu, não o que cada senador fez. |
| `n_materias_unanimes` | `bigint` | Dentre n_materias, quantas não tiveram nenhum voto contrário ou nenhum favorável. Elas ENTRAM na média, de propósito, ao contrário do índice por senador: aqui não há centragem, uma votação unânime tem apoio líquido de +1 ou -1 e é a expressão mais forte de convergência do plenário. Excluí-las inverteria a comparação entre as classes (medido em 2026-09-16: com todas, baixa +0,135 e alta +0,086; sem as 49 unânimes de 96, baixa +0,041 e alta +0,056). |

### `mart_destaque_senador`

Para cada senador, as duas pontas do eixo distributivo entre suas posições em matérias contestadas (5 ou mais votos Não no plenário): a de maior e a de menor contribuição centrada. Esta tabela existe para ser PROVA -- a afirmação que ela sustenta é "este senador desviou do plenário nesta direção, e foi neste voto" -- então uma ponta só vira linha quando o sinal confirma a direção do rótulo. Zero é ausência de desvio, não desvio, por isso o predicado é estrito. Um senador sem desvio numa direção simplesmente não tem linha naquele quadrante, e isso é informação verdadeira ("não há evidência"): a UI trata a ausência. Substitui os 4 quadrantes classe x sentido usados até 2026-09-14 -- com o eixo único, "Sim em matéria pró-classe-baixa" e "Não em matéria pró-classe-alta" são a mesma evidência. Restringir a contestadas evita que uma matéria unânime seja o destaque de 60 senadores ao mesmo tempo. NÃO há mínimo de posições aqui, de propósito: o índice exige 20 porque afirma um padrão, o destaque afirma um voto específico, verdadeiro mesmo com uma posição só.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_senador` | `string` | FK para dim_senador. |
| `quadrante` | `string` | "pro_classe_baixa": a posição do senador, entre as matérias contestadas, com maior contribuicao_centrada, e só quando essa contribuição é positiva. "pro_classe_alta": a de menor contribuicao_centrada, e só quando é negativa. O rótulo é verdadeiro por construção: a linha existe apenas quando é de fato desvio naquela direção. |
| `codigo_materia` | `string` | FK para dim_materia -- matéria que define este quadrante para o senador. Sigla/número/ano/ementa ficam em dim_materia; consumidores fazem o join. |
| `voto` | `string` | Sim ou Não -- como o senador votou nessa matéria. Permite à UI escrever "votou Não em ..." em vez de só "matéria de maior nota". |
| `nota_classe_baixa` | `double` | Nota da matéria para a classe baixa. |
| `nota_classe_alta` | `double` | Nota da matéria para a classe alta. |
| `vies_distributivo` | `double` | nota_classe_baixa - nota_classe_alta da matéria. |
| `contribuicao_centrada` | `double` | Contribuição centrada desta posição (ver mart_contribuicao_senador_materia) -- o critério de escolha do quadrante. Estritamente positiva nas linhas pro_classe_baixa e estritamente negativa nas pro_classe_alta. |
| `n_sim_plenario` | `bigint` | Quantos senadores votaram Sim nesta matéria -- contexto para a UI ("contra 48 votos Sim"). |
| `n_nao_plenario` | `bigint` | Quantos senadores votaram Não nesta matéria. Sempre 5 ou mais aqui: só matérias contestadas são candidatas. |
| `justificativa_classe_baixa` | `string` | Justificativa do LLM para nota_classe_baixa. |
| `justificativa_classe_alta` | `string` | Justificativa do LLM para nota_classe_alta. |

### `mart_estabilidade_rotulo_senador`

Estabilidade do rótulo de cada senador sob o ruído do avaliador (spec da v3, seção 5). As 9 amostras de cada objeto votado (o texto de uma matéria ou uma emenda destacada dela) são reamostradas com reposição 4000 vezes; em cada reamostragem a nota da matéria é a mediana das sorteadas, o índice centrado e os tercis são recalculados com as mesmas regras de mart_contribuicao_senador_materia e mart_alinhamento_senador, e conta-se em que tercil cada senador caiu. O sorteio é determinístico (hash com semente fixa), então o resultado só muda se as notas ou as posições mudarem. Objeto com nota de amostra única (v1/v2) entra com a própria nota em todas as reamostragens: o ruído dela não foi medido, então não entra na conta -- em 2026-09-18 todas as matérias com posição têm as 9 amostras da v3, e a checagem 13b da verificação acusa se isso deixar de valer.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_senador` | `string` | FK para dim_senador. Só senadores elegíveis à classificação (20 ou mais posições não unânimes). |
| `n_replicas` | `int` | Reamostragens feitas: 4000. Eram 1000 até 2026-09-23, quando a entrada das emendas mudou a semente do sorteio e um senador a 0,959 de estabilidade trocou de lado: com 1000 reamostragens o erro do próprio sorteio é de cerca de 0,7%, da ordem da distância ao corte de 0,95. Com 4000 ele cai à metade. |
| `frac_pro_classe_baixa` | `double` | Fração das reamostragens em que o senador caiu no tercil superior do índice (pro_classe_baixa). |
| `frac_equilibrado` | `double` | Fração das reamostragens em que caiu no tercil médio (equilibrado). |
| `frac_pro_classe_alta` | `double` | Fração das reamostragens em que caiu no tercil inferior (pro_classe_alta). |
| `rotulo_mais_frequente` | `string` | O rótulo que mais saiu nas reamostragens. |
| `estabilidade` | `double` | Fração do rótulo mais frequente. O rótulo só é publicado com 0,95 ou mais (mart_alinhamento_senador.classificacao_popular); abaixo disso o senador fica na fronteira. |
| `segundo_rotulo` | `string` | O segundo rótulo mais frequente: com o mais frequente, forma a fronteira em que o senador está quando a estabilidade fica abaixo de 0,95. |

### `mart_participacao_senador`

Taxa de participação de cada senador nas votações do período -- métrica de contexto para avaliar a confiabilidade do índice de alinhamento. Nome fica em dim_senador -- consumidores fazem o join. Todo senador de dim_senador aparece aqui, mesmo quem nunca teve nenhum registro de voto (total_votacoes = 0, taxa_participacao = 0) -- ver nota sobre LEFT JOIN abaixo.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_senador` | `string` | FK para dim_senador. |
| `total_votacoes` | `bigint` | Votações em que o senador poderia ter votado: todas as que têm registro para ele, exceto as em que presidia a sessão (voto_raw = "Presidente (art. 51 RISF)") -- o presidente não vota por regra, e contá-las penalizaria quem preside. |
| `votacoes_participadas` | `bigint` | Dentre total_votacoes, quantas em que o senador votou: Sim, Não, Abstenção ou Secreto (votação secreta, em que votou mas o sentido não é público). P-NRV (presente, não registrou voto) e ausências não contam -- para uma métrica chamada participação em votações, não votar é não participar. |
| `taxa_participacao` | `double` | votacoes_participadas dividido por total_votacoes. 0 quando o senador não tem nenhum registro de voto. |

### `mart_posicao_senador`

Posição definitiva de cada senador sobre cada OBJETO votado, não sobre a matéria como um todo. Até 2026-09-16 a posição era a votação mais recente da matéria, qualquer que fosse o objeto: em 29 das 111 matérias isso era um destaque, e o índice multiplicava a nota da matéria inteira pelo sinal de um voto sobre outro objeto (na PLP 210/2024, um "Não" à Emenda 20 destacada, que suprimia parte do ajuste fiscal, era lido como voto contra o pacote). Entram as votações do texto e das emendas destacadas, os dois objetos com nota própria; cada emenda é um objeto separado, identificado por numero_objeto. Artigos destacados ficam fora, sem nota, e emendas sem número ou sem nota também. Requerimentos (adiamento, preferência, urgência) ficam fora em definitivo -- decidir quando votar não tem conteúdo distributivo. Só inclui matérias com dim_processo.materia_concluida = true: sem essa garantia, a "mais recente de hoje" pode não ser a última. 1º e 2º turno de PEC são o mesmo objeto, então continuam contando uma vez. Base das marts de alinhamento e destaque.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_senador` | `string` | FK para dim_senador. |
| `codigo_materia` | `string` | FK para dim_materia. |
| `objeto_votado` | `string` | Objeto sobre o qual esta posição se manifesta (fact_votacao.objeto_votado): "texto" (o texto da matéria) ou "emenda" (emenda destacada), os dois objetos que têm nota. Artigos destacados e requerimentos ficam fora. |
| `numero_objeto` | `string` | Número do objeto votado: "texto" para o texto da matéria, o número da emenda destacada ("157") para a emenda. Entra na chave porque uma matéria pode ter três emendas destacadas, cada uma com a sua votação e a sua nota. |
| `codigo_votacao` | `string` | FK para fact_votacao -- a votação que determinou esta posição (a mais recente entre as que decidiram este objeto). |
| `voto` | `string` | Posição definitiva do senador sobre este objeto (Sim/Não/Abstenção/Secreto/Ausente). Secreto = votação secreta: o senador votou mas o sentido não é público, então essa posição não tem direção e as marts que usam o sentido do voto a descartam. |

## Schema `SILVER`

### `emenda_scores`

Nota de cada emenda destacada que teve votação nominal, uma linha por (matéria, emenda). A nota é a de um DELTA: o efeito de APROVAR a emenda em relação ao texto-base, que é o texto como estava quando o destaque foi votado -- por isso ela NÃO é comparável com a nota de uma matéria, que é de nível. Mediana de 9 amostras, com a justificativa da amostra mediana, e nunca publicada com menos de 9. Emenda sem base verificável fica fora: a 804 da PEC 45/2019, aprovada por subemenda oral, e a subemenda sem número da PLP 175/2024.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_materia` | `string` | Matéria a que a emenda destacada pertence. |
| `numero_objeto` | `string` | Número da emenda destacada, que com a matéria forma a chave. |
| `prompt_version` | `string` | Versão do prompt (emenda-v1): o dispositivo da emenda mais o texto-base. |
| `n_amostras` | `int` | Quantas amostras formam a nota: sempre 9, porque a emenda só é publicada com as 9 (decisão de 2026-09-17). |
| `nota_classe_baixa` | `double` | Mediana das 9 amostras da nota do DELTA para a classe baixa: -1 é aprovar a emenda piorar claramente a situação dela em relação ao texto-base, 0 é não mudar nada, 1 é melhorar claramente. |
| `justificativa_classe_baixa` | `string` | Justificativa da amostra cuja nota de classe baixa é a mediana (menor índice em caso de empate): texto que o modelo escreveu para exatamente a nota publicada ao lado. |
| `amostra_justificativa_classe_baixa` | `int` | De qual amostra veio justificativa_classe_baixa, para a auditoria fechar contra silver.materia_scores_amostras e a resposta crua no Volume. |
| `nota_classe_alta` | `double` | Mediana das 9 amostras da nota do DELTA para a classe alta, na mesma escala. |
| `justificativa_classe_alta` | `string` | Justificativa da amostra cuja nota de classe alta é a mediana (menor índice em caso de empate). |
| `amostra_justificativa_classe_alta` | `int` | De qual amostra veio justificativa_classe_alta. |
| `fonte_texto` | `string` | Documento que serviu de texto-base. Ver senado_pipeline/emenda_destacada.py. |
| `ids_documento` | `string` | Ids dos PDFs do texto-base, separados por vírgula. |

### `emenda_scores_amostras`

Todas as amostras legíveis (status ok) de nota de EMENDA DESTACADA, uma linha por (matéria, emenda, versão de prompt, amostra). A nota de uma emenda é a de um delta: o efeito de aprová-la em relação ao texto-base. É a base da mediana de silver.emenda_scores e da reamostragem de gold.mart_estabilidade_rotulo_senador.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_materia` | `string` | Matéria a que a emenda destacada pertence. |
| `numero_objeto` | `string` | Número da emenda destacada (fact_votacao.numero_objeto), o que distingue as três emendas de uma mesma matéria. |
| `prompt_version` | `string` | Versão do prompt que gerou a amostra (emenda-v1). |
| `amostra` | `int` | Índice da repetição desta (matéria, emenda, versão), de 1 a 9. O modelo é um avaliador estocástico, e cada emenda recebe 9 amostras independentes. |
| `nota_classe_baixa` | `double` | Nota de -1 (prejudicial) a 1 (benéfico) desta amostra para a classe baixa (chave congelada nota_pobre). |
| `justificativa_classe_baixa` | `string` | Justificativa desta amostra para a nota de classe baixa. |
| `nota_classe_alta` | `double` | Nota de -1 a 1 desta amostra para a classe alta (chave congelada nota_rico). |
| `justificativa_classe_alta` | `string` | Justificativa desta amostra para a nota de classe alta. |
| `fonte_texto` | `string` | Documento que serviu de TEXTO-BASE da emenda: RF_TEXTO, RF_TURNO_SUPLEMENTAR, RF_2TURNO, AUT_TEXTO, INICIAL_VERIFICADO, CASO_B_SUBSTITUTIVO ou COMPOSTO_INICIAL_MAIS_EMENDAS_DO_SENADO. Ver senado_pipeline/emenda_destacada.py. |
| `ids_documento` | `string` | Ids dos PDFs do texto-base, separados por vírgula (sdleg-getter/documento?dm=<id>). |

### `fila_materias_detalhe`

Fila da tarefa gap_fill_materias: matérias referenciadas por alguma votação mas ausentes de silver.materias, porque a busca por ano (/materia/pesquisa/lista?ano=) não devolve toda matéria que depois é votada -- um projeto apresentado antes de 2023 e votado em 2024, por exemplo. Fica vazia quando não há nada a buscar, e é assim que a tarefa decide não chamar a API.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_materia` | `string` | Código da matéria que precisa ser buscada individualmente em /materia/{codigo}. Herda a restrição de not null de silver.votacoes. |

### `fila_materias_pontuacao`

Fila da tarefa llm_scoring: matérias com ementa, de tipo substantivo e com pelo menos uma votação registrada. Uma linha por matéria elegível, independentemente de já ter score -- o que já foi pontuado é descartado pelo próprio script, que cruza esta fila com as chaves (codigo_materia, prompt_version, amostra) já gravadas na Bronze e no Volume.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_materia` | `string` | Código da matéria a pontuar -- metade da chave do score, junto com prompt_version e amostra. |
| `ementa` | `string` | Ementa da matéria, o texto que os prompts v1/v2 pontuam. Nunca nula nesta view. |
| `sigla` | `string` | Sigla do tipo da matéria (PL, PEC, ...), usada na identificação que vai no prompt. |
| `numero` | `string` | Número da matéria dentro do ano, usado na identificação que vai no prompt. |
| `ano` | `int` | Ano de apresentação da matéria, usado na identificação que vai no prompt. |
| `autor` | `string` | Autoria da matéria, como o Senado publica. |
| `tipo_descricao` | `string` | Nome completo do tipo de matéria (de silver.tipos_materia), que o prompt v2 usa como contexto. |

### `fila_processos_status`

Fila da tarefa status_processos_fetch: o processo de cada matéria que já gerou votação. Mesmo recorte de custo das outras duas filas -- consulta o processo das matérias votadas, não o das ~18k matérias apresentadas.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_processo` | `string` | Identificador do processo legislativo a consultar em /processo/{id}. Nunca nulo nesta view. |

### `materias`

Uma matéria legislativa (projeto de lei, PEC, etc.) por linha, apresentada entre 2023 e 2026 ou referenciada por uma votação do período.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_materia` | `string` | Identificador único da matéria na API do Senado. |
| `sigla` | `string` | Sigla do tipo de matéria (PL, PEC, PLP, MPV, etc.). |
| `numero` | `string` | Número da matéria dentro do seu tipo/ano. |
| `ano` | `int` | Ano de apresentação da matéria. |
| `ementa` | `string` | Título/descrição oficial da matéria -- texto usado como entrada para o scoring por LLM. |
| `autor` | `string` | Autor da matéria (senador, comissão ou bancada); serializado como string quando é uma estrutura complexa. |
| `data_apresentacao` | `date` | Data de apresentação da matéria. |
| `id_processo` | `string` | Identificador do processo legislativo desta matéria (IdentificacaoProcesso) -- chave para status_processos (tramitando/situação atual) e para o substituto oficial /processo/{id} dos endpoints de matéria descontinuados. |

### `materia_scores`

Nota de alinhamento socioeconômico por matéria, gerada por LLM, uma linha por matéria. Versão vigente por prioridade explícita: v3-com-empurrao, a mediana de 9 amostras sobre o texto integral votado, quando a matéria tem as 9; senão v2 (ementa, sigla, número, ano e tipo); senão v1 (só a ementa). A v3-sem-empurrao, que perdeu o teste A/B do empurrão fiscal pelo critério declarado antes, fica em silver.materia_scores_amostras e não é publicada. O autor nunca entra no prompt, e na v3 a identidade de quem propôs, relatou ou assinou é retirada do texto.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_materia` | `string` | Matéria a que esta nota se refere. |
| `prompt_version` | `string` | Versão do prompt da nota vigente: v3-com-empurrao (texto integral, mediana de 9 amostras) quando a matéria tem as 9, senão v2, senão v1. |
| `n_amostras` | `int` | Quantas amostras formam a nota. 9 na v3, que publica a mediana e nunca publica com menos de 9 (decisão de 2026-09-17); 1 na v1 e na v2, que publicam a menor amostra. |
| `nota_classe_baixa` | `double` | Nota de -1 (prejudicial) a 1 (benéfico) do impacto da matéria para o brasileiro de classe baixa. Na v3, a mediana das 9 amostras. |
| `justificativa_classe_baixa` | `string` | Justificativa da amostra cuja nota de classe baixa é a mediana (menor índice em caso de empate): texto que o modelo escreveu para exatamente a nota publicada ao lado. |
| `amostra_justificativa_classe_baixa` | `int` | De qual amostra veio justificativa_classe_baixa, para a auditoria fechar contra silver.materia_scores_amostras e a resposta crua no Volume. |
| `nota_classe_alta` | `double` | Nota de -1 a 1 do impacto da matéria para o brasileiro de classe alta. Na v3, a mediana das 9 amostras. |
| `justificativa_classe_alta` | `string` | Justificativa da amostra cuja nota de classe alta é a mediana (menor índice em caso de empate). |
| `amostra_justificativa_classe_alta` | `int` | De qual amostra veio justificativa_classe_alta. |
| `fonte_texto` | `string` | Documento pontuado (v3; NULL na v1/v2, que pontuavam a ementa). Ver silver.materia_scores_amostras. |
| `ids_documento` | `string` | Ids dos PDFs pontuados (v3), separados por vírgula. |

### `materia_scores_amostras`

Todas as amostras legíveis (status ok) de nota por LLM, uma linha por (matéria, versão de prompt, amostra), de todas as versões, publicadas ou não. É a base da mediana de silver.materia_scores e da reamostragem de gold.mart_estabilidade_rotulo_senador.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_materia` | `string` | Matéria a que esta amostra se refere. |
| `prompt_version` | `string` | Versão do prompt que gerou a amostra. Inclui versões em avaliação (as duas variantes da v3 do teste A/B do empurrão fiscal); quem decide o que é publicado é silver.materia_scores. |
| `amostra` | `int` | Índice da repetição desta (matéria, versão). O modelo é um avaliador estocástico, e a v3 grava 9 amostras por matéria e versão. Arquivos anteriores ao campo contam como amostra 1. |
| `nota_classe_baixa` | `double` | Nota de -1 (prejudicial) a 1 (benéfico) desta amostra para a classe baixa (chave congelada nota_pobre). |
| `justificativa_classe_baixa` | `string` | Justificativa desta amostra para a nota de classe baixa. |
| `nota_classe_alta` | `double` | Nota de -1 a 1 desta amostra para a classe alta (chave congelada nota_rico). |
| `justificativa_classe_alta` | `string` | Justificativa desta amostra para a nota de classe alta. |
| `fonte_texto` | `string` | Documento de onde veio o texto pontuado (v3): RF_TEXTO, RF_TURNO_SUPLEMENTAR, RF_2TURNO, AUT_TEXTO, INICIAL_VERIFICADO, CASO_B_SUBSTITUTIVO ou COMPOSTO_INICIAL_MAIS_EMENDAS_DO_SENADO. NULL na v1 e na v2, que pontuavam a ementa. |
| `ids_documento` | `string` | Ids dos PDFs pontuados, separados por vírgula, no Senado (sdleg-getter/documento?dm=<id>). Permite rastrear qualquer nota v3 até o documento exato. NULL na v1 e na v2. |

### `senadores`

Um senador por linha, com os dados de identificação vigentes na extração mais recente (tipo-1, sem histórico de troca de partido).

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_senador` | `string` | Identificador único do senador na API do Senado (IdentificacaoParlamentar.CodigoParlamentar). |
| `nome_senador` | `string` | Nome parlamentar do senador. |
| `partido` | `string` | Sigla do partido do senador no momento da extração. |
| `uf` | `string` | Unidade federativa (estado) representada pelo senador. |
| `url_foto` | `string` | URL da foto oficial do senador. |
| `mandato_inicio` | `int` | Ano de início do mandato atual do senador (DataInicio da primeira legislatura do mandato). |
| `mandato_fim` | `int` | Ano de término do mandato atual do senador (DataFim da segunda legislatura do mandato). |

### `situacoes_materia`

Domínio controlado (referência oficial) de todas as situações de tramitação possíveis para uma matéria/processo -- dá significado a dim_materia.sigla_situacao_atual. Fonte: /processo/tipos-situacao (175 códigos, ativos e históricos, confirmados sem sigla duplicada).

| Coluna | Tipo | Descrição |
|---|---|---|
| `sigla` | `string` | Código curto da situação de tramitação (ex.: TNJR, RMCD, APRVD). |
| `descricao` | `string` | Texto completo da situação de tramitação. |
| `data_inicio` | `date` | Data a partir da qual este código passou a ser usado. |
| `data_fim` | `date` | Data em que este código deixou de ser usado -- NULL quando ainda está ativo. |

### `status_processos`

Status de tramitação de cada processo legislativo referenciado por uma matéria efetivamente votada (fonte: /processo/{id}, substituto oficial de /materia/situacaoatual e /materia/{codigo} para esta finalidade, ambos descontinuados). Escopado às ~360 matérias votadas -- ver scripts/run_materia_status_fetch.py.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_processo` | `string` | Identificador do processo legislativo -- FK para materias.id_processo. |
| `tramitando` | `string` | "Sim" se o processo ainda está em tramitação (pode gerar novas votações), "Não" se já concluiu -- para a MATÉRIA cujo id_processo é este, não para eventuais processos relacionados (ex.: um veto pendente é um id_processo à parte, com seu próprio codigoMateria). |
| `situacao_atual` | `string` | Texto da situação de tramitação atual (ex.: "TRANSFORMADA EM NORMA JURÍDICA"). Ausente para alguns tipos de matéria (ex.: MSF) mesmo quando tramitando está presente. |
| `sigla_situacao_atual` | `string` | Código curto da situação atual -- FK para situacoes_materia.sigla. |
| `data_situacao_atual` | `date` | Data em que a situação atual foi atingida. |
| `materia_concluida` | `boolean` | tramitando = "Não" -- indica que não é esperada nova votação sob este id_processo. Não garante que a matéria como um todo (incluindo eventuais processos sucessores/veto, cada um com seu próprio id_processo) tenha se resolvido. |

### `tipos_materia`

Domínio controlado (referência oficial) de todos os tipos/siglas de matéria possíveis -- dá significado a dim_materia.sigla. Fonte: /processo/siglas (184 códigos, ativos e históricos, confirmados sem sigla duplicada). materia_substantiva é uma allowlist, não denylist: a maioria dos 184 códigos é procedimental, e uma sigla nova desconhecida deve cair fora do índice por padrão.

| Coluna | Tipo | Descrição |
|---|---|---|
| `sigla` | `string` | Sigla do tipo de matéria (ex.: PL, PEC, PLP, MPV, VET, RQS). |
| `descricao` | `string` | Nome completo do tipo de matéria. |
| `data_inicio` | `date` | Data a partir da qual esta sigla passou a ser usada. |
| `data_fim` | `date` | Data em que esta sigla deixou de ser usada -- NULL quando ainda está ativa. |
| `materia_substantiva` | `boolean` | true para tipos de matéria legislativa com conteúdo normativo próprio (PL, PLP, PEC, MPV, PLC, PLS, PLN, SCD, PRS, PDS, VET); false para atos procedimentais, nomeações e comunicações (MSF, OFS, RQS, REQ, PDL, etc.) -- estes não entram no scoring por LLM nem no índice de alinhamento, porque a ementa não descreve impacto distributivo. |

### `votacoes`

Uma votação plenária por linha, vinculada à matéria votada e classificada pelo objeto que foi decidido.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_votacao` | `string` | Identificador único da votação (Votacao.CodigoSessaoVotacao). |
| `codigo_materia` | `string` | Matéria que foi objeto desta votação. |
| `data_votacao` | `date` | Data em que a votação ocorreu. |
| `sequencial_sessao` | `int` | Ordem desta votação dentro da sessão plenária (Votacao.SequencialSessao) -- distingue, por exemplo, o 1º do 2º turno de uma PEC, ou o texto principal de um destaque votado depois. |
| `resultado` | `string` | Resultado declarado da votação (Votacao.Resultado): "A" aprovada, "R" rejeitada. Vem da fonte e NÃO é inferido da contagem de votos: três destaques com mais Sim que Não foram rejeitados por falta de quórum qualificado (a Emenda 2.203 à PLP 68/2024, por 33 a 32; a 2.223, por 37 a 24; a Emenda 587 à PLP 108/2024, por 33 a 27). É o campo que diz se uma emenda destacada entrou ou não no texto, e por isso decide qual documento é o texto-base ao pontuar a emenda. |
| `descricao_votacao` | `string` | Texto descrevendo o que especificamente foi votado nesta votação (Votacao.DescricaoVotacao) -- ex.: "nos termos do parecer, ressalvados os destaques" vs. "Emenda nº 8... destacada". Complementa a ementa da matéria (que descreve a matéria como um todo, não a votação específica). |
| `objeto_votado` | `string` | Que objeto o plenário decidiu nesta votação, derivado de descricao_votacao: "texto" (o texto da matéria, incluindo substitutivo, 1º/2º turno e PLV de MPV), "emenda" (emenda ou subemenda destacada), "artigo" (artigo, parágrafo ou expressão destacados) ou "requerimento" (adiamento, preferência, urgência, calendário -- sem conteúdo distributivo, fora do índice em definitivo). NULL quando a descrição não casa com nenhum padrão conhecido: é uma ALLOWLIST, então objeto desconhecido fica fora do índice por padrão, mesma regra de dim_tipo_materia.materia_substantiva. Existe porque a posição de um senador numa matéria precisa ser o voto sobre o objeto que recebeu a nota: até 2026-09-16 a posição vinha da votação mais recente, e em 29 matérias isso era um destaque, cujo sentido pode ser o oposto do texto (na PLP 210/2024 a Emenda 20 destacada suprimia parte do ajuste fiscal, e um "Não" a ela era apoio ao corte). |
| `numero_objeto` | `string` | Número do objeto destacado, extraído de descricao_votacao: "157" para a Emenda 157 destacada, "30" para o art. 30 destacado. Vale "texto" quando objeto_votado = "texto", porque o texto é objeto único da matéria. NULL quando a descrição destaca um objeto mas não o numera -- caso da subemenda ao substitutivo da PLP 175/2024, que por isso fica fora do índice pela regra de allowlist. É o que distingue as três emendas destacadas de uma mesma matéria, e sem ele a chave de mart_posicao_senador não fecha. |

### `votos`

Um voto individual de um senador em uma votação, um por linha.

| Coluna | Tipo | Descrição |
|---|---|---|
| `codigo_votacao` | `string` | Votação em que este voto foi registrado. |
| `codigo_senador` | `string` | Senador que registrou o voto. |
| `voto_raw` | `string` | Valor original do campo Voto retornado pela API (inclui códigos de ausência como LS, NCom, P-NRV, e "Votou" para votação secreta). |
| `voto` | `string` | Voto normalizado em 5 categorias: Sim, Não, Abstenção, Secreto (voto_raw = "Votou": votação secreta, o senador votou mas o sentido não é público) ou Ausente (qualquer outro código: licenças LS/LP/LAP, missão MIS, NCom, AP, NA, P-NRV -- presente mas não registrou voto -- e o presidente da sessão, que não vota por regra, art. 51 do RISF). Só Sim/Não carregam direção; Secreto conta como participação mas não como posição. |
