-- lakeflow/transformations/gold_mart_alinhamento_temporal.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.mart_alinhamento_temporal (
    codigo_senador STRING COMMENT 'FK para dim_senador.',
    ano INT COMMENT 'Ano da votação que definiu a posição (fact_votacao.data_votacao, via o codigo_votacao herdado de mart_contribuicao_senador_materia).',
    indice_classe_baixa DOUBLE COMMENT 'Média de contribuicao_classe_baixa de todas as posições do senador naquele ano, unânimes incluídas (ver mart_alinhamento_senador). Descritivo.',
    indice_classe_alta DOUBLE COMMENT 'Média de contribuicao_classe_alta de todas as posições do senador naquele ano, unânimes incluídas. Descritivo.',
    indice_vies_distributivo DOUBLE COMMENT 'Média de contribuicao_centrada das posições não unânimes do senador naquele ano. A centragem é a do plenário na matéria, calculada uma vez em mart_contribuicao_senador_materia -- não é recalculada por ano, para que os anos continuem comparáveis entre si.',
    n_posicoes BIGINT COMMENT 'Posições Sim/Não do senador em matérias substantivas pontuadas naquele ano. Denominador das duas colunas descritivas.',
    n_posicoes_nao_unanimes BIGINT COMMENT 'Dentre n_posicoes, quantas não foram unânimes no plenário. É o denominador de indice_vies_distributivo, a mesma população que mart_alinhamento_senador promedia no índice centrado. Sem corte de elegibilidade nesta view: um ano com poucas posições é informação, não motivo de exclusão. Pode ser 0, e nesse caso indice_vies_distributivo fica NULL -- o senador se posicionou naquele ano, mas só em consensos, e "nenhum desvio observável" é diferente de "desvio zero".',
    CONSTRAINT codigo_senador_not_null EXPECT (codigo_senador IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Evolução do índice de viés distributivo de cada senador ao longo dos anos da legislatura, com as mesmas regras de denominador de mart_alinhamento_senador: não unânimes no índice centrado, todas nas colunas descritivas. Nome fica em dim_senador -- consumidores fazem o join. Diferente de mart_alinhamento_senador/mart_alinhamento_partido_uf, aqui não existe uma dimensão "todos os anos possíveis" pra fazer LEFT JOIN contra -- um (senador, ano) só aparece quando há posição real naquele ano; ausência de um ano é informação genuína (sem atividade pontuável), não um bug de sparsity.'
AS
SELECT
    c.codigo_senador,
    year(fv.data_votacao) AS ano,
    avg(c.contribuicao_classe_baixa) AS indice_classe_baixa,
    avg(c.contribuicao_classe_alta) AS indice_classe_alta,
    avg(CASE WHEN least(c.n_sim_plenario, c.n_nao_plenario) > 0 THEN c.contribuicao_centrada END) AS indice_vies_distributivo,
    count(*) AS n_posicoes,
    count(CASE WHEN least(c.n_sim_plenario, c.n_nao_plenario) > 0 THEN 1 END) AS n_posicoes_nao_unanimes
FROM senado_votacoes.gold.mart_contribuicao_senador_materia c
JOIN senado_votacoes.gold.fact_votacao fv ON fv.codigo_votacao = c.codigo_votacao
GROUP BY 1, 2
