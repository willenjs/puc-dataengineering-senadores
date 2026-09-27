-- lakeflow/transformations/gold_mart_coesao_bancada_uf.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.mart_coesao_bancada_uf (
    uf STRING NOT NULL PRIMARY KEY COMMENT 'Unidade federativa.',
    votacoes_com_bancada_completa BIGINT COMMENT 'Quantidade de votações em que exatamente 3 senadores distintos da UF manifestaram posição (Sim/Não/Abstenção) -- bancada avaliada por votação, não contra um roster fixo.',
    votacoes_unanimes BIGINT COMMENT 'Dentre votacoes_com_bancada_completa, quantidade em que os 3 senadores votaram de forma idêntica.',
    indice_coesao DOUBLE COMMENT 'votacoes_unanimes dividido por votacoes_com_bancada_completa.',
    CONSTRAINT indice_coesao_not_null EXPECT (indice_coesao IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Índice de coesão de voto da bancada de cada UF, considerando só votações em que a bancada completa (3 senadores distintos daquela UF) se manifestou.'
AS
WITH votos_uf AS (
    SELECT
        v.codigo_votacao,
        s.uf,
        v.codigo_senador,
        v.voto
    FROM senado_votacoes.gold.fact_voto_senador v
    JOIN senado_votacoes.gold.dim_senador s ON s.codigo_senador = v.codigo_senador
    WHERE v.voto IN ('Sim', 'Não', 'Abstenção')
),
agregado_por_votacao AS (
    SELECT
        codigo_votacao,
        uf,
        count(DISTINCT codigo_senador) AS qtd_senadores,
        count(DISTINCT voto) AS qtd_votos_distintos
    FROM votos_uf
    GROUP BY codigo_votacao, uf
)
SELECT
    uf,
    count(*) AS votacoes_com_bancada_completa,
    count(CASE WHEN qtd_votos_distintos = 1 THEN 1 END) AS votacoes_unanimes,
    nvl(try_divide(count(CASE WHEN qtd_votos_distintos = 1 THEN 1 END), count(*)), 0) AS indice_coesao
FROM agregado_por_votacao
WHERE qtd_senadores = 3
GROUP BY uf
