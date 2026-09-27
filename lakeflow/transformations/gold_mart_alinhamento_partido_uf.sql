-- lakeflow/transformations/gold_mart_alinhamento_partido_uf.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.mart_alinhamento_partido_uf (
    partido STRING NOT NULL COMMENT 'Sigla do partido.',
    uf STRING COMMENT 'Unidade federativa.',
    indice_classe_baixa DOUBLE COMMENT 'Média de contribuicao_classe_baixa sobre todas as posições dos senadores do partido/UF, unânimes incluídas (ver mart_alinhamento_senador: coluna não centrada, a posição unânime vale a nota inteira). Descritivo.',
    indice_classe_alta DOUBLE COMMENT 'Média de contribuicao_classe_alta sobre todas as posições dos senadores do partido/UF, unânimes incluídas. Descritivo.',
    indice_vies_distributivo DOUBLE COMMENT 'Média de contribuicao_centrada sobre as posições não unânimes dos senadores do partido/UF: positivo = a bancada desvia do plenário na direção da classe baixa. Média por POSIÇÃO, não média dos índices individuais -- senadores com mais posições pesam mais.',
    n_posicoes BIGINT COMMENT 'Total de posições Sim/Não em matérias substantivas pontuadas somadas sobre os senadores do partido/UF. Denominador das duas colunas descritivas.',
    n_posicoes_nao_unanimes BIGINT COMMENT 'Dentre n_posicoes, quantas não foram unânimes no plenário. É o denominador de indice_vies_distributivo, a mesma população que mart_alinhamento_senador promedia no índice centrado -- se as duas views usassem denominadores diferentes, a média por partido deixaria de ser comparável com a média por senador sob o mesmo nome.',
    qtd_senadores BIGINT COMMENT 'Quantidade de senadores distintos do partido/UF, incluindo os que nunca se manifestaram Sim ou Não em nenhuma matéria substantiva pontuada (esses não contribuem pra média, mas contam aqui).',
    CONSTRAINT partido_not_null EXPECT (partido IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Mesmo índice de viés distributivo de mart_alinhamento_senador, agregado por partido e UF, com as mesmas regras de denominador: não unânimes no índice centrado, todas nas colunas descritivas. A centragem por matéria é a do plenário inteiro, calculada uma vez em mart_contribuicao_senador_materia -- não é recalculada dentro do partido. Todo partido/UF com ao menos 1 senador aparece aqui, mesmo sem nenhuma posição -- ver nota sobre LEFT JOIN abaixo.'
AS
-- LEFT JOIN a partir de dim_senador: garante que todo partido/UF apareça mesmo se
-- nenhum de seus senadores tomou posição em matéria substantiva pontuada -- antes esse
-- grupo simplesmente sumia da view (bug reportado: algumas UFs pareciam ter só 1
-- partido).
SELECT
    s.partido,
    s.uf,
    avg(c.contribuicao_classe_baixa) AS indice_classe_baixa,
    avg(c.contribuicao_classe_alta) AS indice_classe_alta,
    avg(CASE WHEN least(c.n_sim_plenario, c.n_nao_plenario) > 0 THEN c.contribuicao_centrada END) AS indice_vies_distributivo,
    count(c.codigo_materia) AS n_posicoes,
    count(CASE WHEN least(c.n_sim_plenario, c.n_nao_plenario) > 0 THEN 1 END) AS n_posicoes_nao_unanimes,
    count(DISTINCT s.codigo_senador) AS qtd_senadores
FROM senado_votacoes.gold.dim_senador s
LEFT JOIN senado_votacoes.gold.mart_contribuicao_senador_materia c
    ON c.codigo_senador = s.codigo_senador
WHERE s.partido IS NOT NULL
GROUP BY s.partido, s.uf
