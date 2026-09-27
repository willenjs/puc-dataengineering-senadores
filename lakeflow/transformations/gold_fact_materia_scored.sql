-- lakeflow/transformations/gold_fact_materia_scored.sql
-- Formaliza o nome dimensional sobre a entidade limpa da Silver, incluindo o rename
-- nota_pobre/nota_rico -> nota_classe_baixa/nota_classe_alta e as justificativas por
-- perfil (ver silver_materia_scores.sql).
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.fact_materia_scored (
    codigo_materia STRING NOT NULL PRIMARY KEY COMMENT 'FK para dim_materia.',
    prompt_version STRING COMMENT 'Versão do prompt da nota vigente (v3-com-empurrao, v2 ou v1) -- ver silver_materia_scores.sql.',
    n_amostras INT COMMENT 'Quantas amostras formam a nota: 9 na v3 (mediana), 1 na v1 e na v2.',
    nota_classe_baixa DOUBLE COMMENT 'Nota de -1 (prejudicial) a 1 (benéfico) do impacto da matéria para o brasileiro de classe baixa. Na v3, a mediana das 9 amostras.',
    justificativa_classe_baixa STRING COMMENT 'Justificativa da amostra cuja nota de classe baixa é a mediana.',
    amostra_justificativa_classe_baixa INT COMMENT 'De qual amostra veio justificativa_classe_baixa (fact_materia_score_amostra).',
    nota_classe_alta DOUBLE COMMENT 'Nota de -1 a 1 do impacto da matéria para o brasileiro de classe alta. Na v3, a mediana das 9 amostras.',
    justificativa_classe_alta STRING COMMENT 'Justificativa da amostra cuja nota de classe alta é a mediana.',
    amostra_justificativa_classe_alta INT COMMENT 'De qual amostra veio justificativa_classe_alta.',
    fonte_texto STRING COMMENT 'Documento pontuado na v3 (NULL na v1/v2, que pontuavam a ementa).',
    ids_documento STRING COMMENT 'Ids dos PDFs pontuados na v3, separados por vírgula.',
    CONSTRAINT fk_scored_materia FOREIGN KEY (codigo_materia) REFERENCES senado_votacoes.gold.dim_materia(codigo_materia)
)
COMMENT 'Star schema formal: nota de alinhamento por matéria (mesma entidade de silver.materia_scores, sem transformação adicional).'
AS SELECT * FROM senado_votacoes.silver.materia_scores
