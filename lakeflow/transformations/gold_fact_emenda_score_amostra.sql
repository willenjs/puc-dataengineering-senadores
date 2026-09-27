-- lakeflow/transformations/gold_fact_emenda_score_amostra.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.fact_emenda_score_amostra (
    codigo_materia STRING NOT NULL COMMENT 'FK para dim_materia.',
    numero_objeto STRING NOT NULL COMMENT 'Número da emenda destacada (fact_votacao.numero_objeto).',
    prompt_version STRING NOT NULL COMMENT 'Versão do prompt da amostra (emenda-v1).',
    amostra INT NOT NULL COMMENT 'Índice da repetição desta (matéria, versão).',
    nota_classe_baixa DOUBLE COMMENT 'Nota desta amostra para a classe baixa.',
    justificativa_classe_baixa STRING COMMENT 'Justificativa desta amostra para a classe baixa.',
    nota_classe_alta DOUBLE COMMENT 'Nota desta amostra para a classe alta.',
    justificativa_classe_alta STRING COMMENT 'Justificativa desta amostra para a classe alta.',
    fonte_texto STRING COMMENT 'Documento que serviu de texto-base.',
    ids_documento STRING COMMENT 'Ids dos PDFs do texto-base, separados por vírgula.',
    CONSTRAINT pk_fact_emenda_score_amostra PRIMARY KEY (codigo_materia, numero_objeto, prompt_version, amostra),
    CONSTRAINT fk_emenda_score_amostra_materia FOREIGN KEY (codigo_materia) REFERENCES senado_votacoes.gold.dim_materia(codigo_materia)
)
COMMENT 'Star schema formal: cada amostra de nota de emenda destacada (mesma entidade de silver.emenda_scores_amostras). fact_emenda_scored é a nota publicada; esta é a matéria-prima dela e da reamostragem de mart_estabilidade_rotulo_senador.'
AS SELECT * FROM senado_votacoes.silver.emenda_scores_amostras
