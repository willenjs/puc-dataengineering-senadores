-- lakeflow/transformations/gold_mart_alinhamento_senador.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.mart_alinhamento_senador (
    codigo_senador STRING NOT NULL PRIMARY KEY COMMENT 'FK para dim_senador.',
    indice_classe_baixa DOUBLE COMMENT 'Média de contribuicao_classe_baixa (nota da classe baixa com o sinal do voto) sobre TODAS as posições Sim/Não do senador em matérias substantivas pontuadas, unânimes incluídas. Descritivo -- "média das notas do que o senador apoiou" -- não é a base da classificação nem dos ranks. Não recebe o filtro de unanimidade de propósito: a coluna não é centrada, então numa matéria unânime a posição vale a nota inteira, e excluí-la apagaria dado real (49 das 96 matérias com posição em 2026-09-16 eram unânimes).',
    indice_classe_alta DOUBLE COMMENT 'Mesma lógica de indice_classe_baixa (ver acima), para nota_classe_alta.',
    indice_vies_distributivo DOUBLE COMMENT 'Média de contribuicao_centrada (mart_contribuicao_senador_materia) sobre as posições NÃO UNÂNIMES do senador -- a única coluna com esse filtro, porque é a única centrada: numa matéria unânime a centragem zera a contribuição de todo mundo, e mantê-la no denominador só encolheria o senador em direção a 0. Positivo = desvia do plenário na direção da classe baixa; negativo = na direção da classe alta. Base de classificacao_popular e dos dois ranks.',
    indice_vies_bruto DOUBLE COMMENT 'Média de contribuicao_bruta (sem centragem) sobre TODAS as posições, unânimes incluídas, pelo mesmo motivo de indice_classe_baixa. Mede a pauta em que o senador se posicionou, não seu desvio em relação aos colegas -- exposto só para transparência e comparação com indice_vies_distributivo.',
    n_posicoes BIGINT COMMENT 'Quantidade de matérias substantivas pontuadas em que o senador votou Sim ou Não. 0 para senador sem nenhuma posição. Denominador das três colunas descritivas (indice_classe_baixa, indice_classe_alta, indice_vies_bruto); NÃO é o denominador do índice centrado nem a base da elegibilidade.',
    n_posicoes_nao_unanimes BIGINT COMMENT 'Dentre n_posicoes, quantas tiveram ao menos um voto de cada lado no plenário (least(n_sim_plenario, n_nao_plenario) > 0). É o denominador de indice_vies_distributivo e a base de elegivel_classificacao, e só dessas duas: as colunas descritivas não são centradas e usam n_posicoes. Numa matéria unânime todo senador fez a mesma coisa e a centragem já a zera no numerador por construção: mantê-la no denominador não acrescentaria informação, só encolheria cada senador em direção a 0 na proporção de quantos consensos ele frequentou -- e deixaria um senador baixar o próprio índice comparecendo a mais votações unânimes.',
    n_posicoes_contestadas BIGINT COMMENT 'Dentre n_posicoes, quantas em matérias com 5 ou mais votos Não no plenário -- indicador de quanto do índice vem de votações realmente disputadas. Informação para a UI e critério de candidatura em mart_destaque_senador; não é base de cálculo nem de elegibilidade aqui (o corte em 5 seria arbitrário, e a faixa de 1 a 4 dissidentes é onde mora o voto isolado, que é a declaração máxima de desvio).',
    elegivel_classificacao BOOLEAN COMMENT 'n_posicoes_nao_unanimes >= 20. O mínimo amostral conta a MESMA população que os índices promediam: com o corte sobre n_posicoes, um senador com 20 posições das quais 2 informativas receberia classificação sobre uma média de 2 observações. Só senadores elegíveis recebem classificacao_popular e ranks; abaixo disso o índice existe mas é ruidoso demais para rotular (os dois únicos "inimigos" da versão anterior tinham 3 e 2 votos).',
    classificacao_pontual STRING COMMENT 'Tercil de indice_vies_distributivo entre os senadores elegíveis, calculado sobre a nota publicada: "pro_classe_baixa" (tercil superior), "equilibrado" (tercil médio), "pro_classe_alta" (tercil inferior). É a classificação que a nota publicada dá, sem considerar o ruído do avaliador; NÃO é o rótulo publicado (ver classificacao_popular). NULL quando não elegível.',
    classificacao_popular STRING COMMENT 'O rótulo publicável: o tercil que o senador ocupa em pelo menos 95% das 4000 reamostragens do ruído do avaliador (mart_estabilidade_rotulo_senador) -- "pro_classe_baixa", "equilibrado" ou "pro_classe_alta" --, ou "na_fronteira" quando nenhum tercil chega a 95% (ver fronteira_entre). Classificação RELATIVA aos demais senadores, não faixa fixa. NULL quando não elegível -- distingue "sem dados suficientes" de "equilibrado". Com uma única amostra por matéria, 10 de 81 senadores trocavam de tercil entre duas rodadas idênticas; por isso o rótulo só é publicado quando é estável (decisão de 2026-09-16).',
    estabilidade_classificacao DOUBLE COMMENT 'Fração das reamostragens em que saiu o rótulo mais frequente (mart_estabilidade_rotulo_senador.estabilidade). 0,95 ou mais publica o rótulo. NULL quando não elegível.',
    fronteira_entre STRING COMMENT 'Quando classificacao_popular = "na_fronteira", os dois rótulos mais frequentes nas reamostragens, na ordem do eixo (ex.: "pro_classe_baixa|equilibrado"). NULL nos demais casos.',
    rank_pro_classe_baixa INT COMMENT 'Posição no ranking decrescente de indice_vies_distributivo entre os elegíveis (1 = maior desvio na direção da classe baixa). NULL quando não elegível.',
    rank_pro_classe_alta INT COMMENT 'Posição no ranking crescente de indice_vies_distributivo entre os elegíveis (1 = maior desvio na direção da classe alta). Num eixo único é o mesmo ranking em ordem oposta; os dois nomes continuam corretos. NULL quando não elegível.'
)
COMMENT 'Índice de viés distributivo por senador: quanto seus votos desviam do plenário na direção da classe baixa ou da classe alta, num eixo único (nota_classe_baixa - nota_classe_alta) centrado por matéria. O índice centrado é promediado sobre as posições não unânimes (ver n_posicoes_nao_unanimes); as colunas descritivas, sobre todas. Classificação e ranks são relativos (tercis entre os elegíveis), não absolutos, e o rótulo publicado (classificacao_popular) só sai quando é estável sob o ruído do avaliador -- a normalização min-max independente por eixo usada até 2026-09-14 classificava 98 de 102 senadores como "amigo do povo" e foi removida. Todo senador de dim_senador aparece aqui; sem posição, os índices ficam NULL e as contagens 0. Nome/partido/UF/foto ficam em dim_senador -- consumidores fazem o join.'
AS
WITH
-- LEFT JOIN a partir de dim_senador (não de mart_contribuicao_senador_materia): garante
-- que todo senador apareça, inclusive os que nunca tomaram posição Sim/Não em matéria
-- substantiva pontuada -- antes da correção dessa mesma classe de bug, bancadas inteiras
-- sumiam da view. Toda a lógica de sinal/viés/centragem já está na base compartilhada.
--
-- O CASE dentro do avg() do índice centrado é o denominador não unânime: avg() ignora
-- NULL, então a posição unânime sai do numerador E do denominador de uma vez.
-- least(n_sim, n_nao) > 0 é a definição de "houve os dois lados". Só a coluna centrada
-- recebe o CASE: o argumento que o justifica ("a centragem já zera a unânime") é falso
-- para as colunas não centradas, em que a posição unânime vale a nota inteira. Até
-- 2026-09-16 as quatro colunas recebiam o filtro, e o medidor do site, que lia as
-- descritivas, excluía exatamente as votações em que o Senado convergiu.
indices AS (
    SELECT
        s.codigo_senador,
        avg(c.contribuicao_classe_baixa) AS indice_classe_baixa,
        avg(c.contribuicao_classe_alta) AS indice_classe_alta,
        avg(CASE WHEN least(c.n_sim_plenario, c.n_nao_plenario) > 0 THEN c.contribuicao_centrada END) AS indice_vies_distributivo,
        avg(c.contribuicao_bruta) AS indice_vies_bruto,
        count(c.codigo_materia) AS n_posicoes,
        count(CASE WHEN least(c.n_sim_plenario, c.n_nao_plenario) > 0 THEN 1 END) AS n_posicoes_nao_unanimes,
        count(CASE WHEN c.n_nao_plenario >= 5 THEN 1 END) AS n_posicoes_contestadas
    FROM senado_votacoes.gold.dim_senador s
    LEFT JOIN senado_votacoes.gold.mart_contribuicao_senador_materia c
        ON c.codigo_senador = s.codigo_senador
    GROUP BY s.codigo_senador
),
-- O WHERE é aplicado antes das window functions, então ntile/rank enxergam apenas os
-- senadores elegíveis: os tercis dividem os elegíveis (81 na base de 2026-09-16), não 245.
elegiveis AS (
    SELECT
        codigo_senador,
        ntile(3) OVER (ORDER BY indice_vies_distributivo DESC, codigo_senador) AS tercil,
        rank() OVER (ORDER BY indice_vies_distributivo DESC) AS rank_pro_classe_baixa,
        rank() OVER (ORDER BY indice_vies_distributivo ASC) AS rank_pro_classe_alta
    FROM indices
    WHERE n_posicoes_nao_unanimes >= 20
)
SELECT
    i.codigo_senador,
    i.indice_classe_baixa,
    i.indice_classe_alta,
    i.indice_vies_distributivo,
    i.indice_vies_bruto,
    i.n_posicoes,
    i.n_posicoes_nao_unanimes,
    i.n_posicoes_contestadas,
    i.n_posicoes_nao_unanimes >= 20 AS elegivel_classificacao,
    -- LEFT JOIN deixa e.tercil NULL para quem não é elegível, e o CASE sem ELSE devolve
    -- NULL -- "sem dados suficientes" é informação diferente de "equilibrado".
    CASE e.tercil
        WHEN 1 THEN 'pro_classe_baixa'
        WHEN 2 THEN 'equilibrado'
        WHEN 3 THEN 'pro_classe_alta'
    END AS classificacao_pontual,
    CASE
        WHEN e.tercil IS NULL THEN NULL
        WHEN est.estabilidade >= 0.95 THEN est.rotulo_mais_frequente
        ELSE 'na_fronteira'
    END AS classificacao_popular,
    CASE WHEN e.tercil IS NOT NULL THEN est.estabilidade END AS estabilidade_classificacao,
    CASE
        WHEN e.tercil IS NOT NULL AND NOT (est.estabilidade >= 0.95) THEN
            array_join(array_sort(array(est.rotulo_mais_frequente, est.segundo_rotulo),
                (a, b) -> CASE WHEN array_position(array('pro_classe_baixa', 'equilibrado', 'pro_classe_alta'), a)
                                  < array_position(array('pro_classe_baixa', 'equilibrado', 'pro_classe_alta'), b) THEN -1 ELSE 1 END), '|')
    END AS fronteira_entre,
    e.rank_pro_classe_baixa,
    e.rank_pro_classe_alta
FROM indices i
LEFT JOIN elegiveis e ON e.codigo_senador = i.codigo_senador
LEFT JOIN senado_votacoes.gold.mart_estabilidade_rotulo_senador est ON est.codigo_senador = i.codigo_senador
