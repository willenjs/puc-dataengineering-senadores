-- lakeflow/transformations/gold_fact_emenda_scored.sql
-- Formaliza o nome dimensional sobre a entidade limpa da Silver, incluindo o rename
-- nota_pobre/nota_rico -> nota_classe_baixa/nota_classe_alta e as justificativas por
-- perfil (ver silver_materia_scores.sql).
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.fact_emenda_scored (
    codigo_materia STRING NOT NULL COMMENT 'FK para dim_materia.',
    numero_objeto STRING NOT NULL COMMENT 'Número da emenda destacada (fact_votacao.numero_objeto).',
    prompt_version STRING COMMENT 'Versão do prompt (emenda-v1) -- ver silver_emenda_scores.sql.',
    n_amostras INT COMMENT 'Sempre 9: a mediana das 9 amostras.',
    nota_classe_baixa DOUBLE COMMENT 'Mediana da nota do DELTA para a classe baixa: o efeito de aprovar a emenda em relação ao texto-base.',
    justificativa_classe_baixa STRING COMMENT 'Justificativa da amostra cuja nota de classe baixa é a mediana.',
    amostra_justificativa_classe_baixa INT COMMENT 'De qual amostra veio justificativa_classe_baixa (fact_materia_score_amostra).',
    nota_classe_alta DOUBLE COMMENT 'Mediana da nota do DELTA para a classe alta.',
    justificativa_classe_alta STRING COMMENT 'Justificativa da amostra cuja nota de classe alta é a mediana.',
    amostra_justificativa_classe_alta INT COMMENT 'De qual amostra veio justificativa_classe_alta.',
    fonte_texto STRING COMMENT 'Documento que serviu de texto-base.',
    ids_documento STRING COMMENT 'Ids dos PDFs do texto-base, separados por vírgula.',
    CONSTRAINT pk_fact_emenda_scored PRIMARY KEY (codigo_materia, numero_objeto),
    CONSTRAINT fk_emenda_scored_materia FOREIGN KEY (codigo_materia) REFERENCES senado_votacoes.gold.dim_materia(codigo_materia)
)
COMMENT 'Star schema formal: nota de cada emenda destacada (mesma entidade de silver.emenda_scores). A nota é de um DELTA -- o efeito de aprovar a emenda em relação ao texto-base --, e por isso não é comparável com a de fact_materia_scored, que é de nível.'
AS SELECT * FROM senado_votacoes.silver.emenda_scores
