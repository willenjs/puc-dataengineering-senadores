-- lakeflow/transformations/gold_fact_materia_score_amostra.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.fact_materia_score_amostra (
    codigo_materia STRING NOT NULL COMMENT 'FK para dim_materia.',
    prompt_version STRING NOT NULL COMMENT 'Versão do prompt da amostra, publicada ou não (inclui v3-sem-empurrao, que perdeu o teste A/B).',
    amostra INT NOT NULL COMMENT 'Índice da repetição desta (matéria, versão).',
    nota_classe_baixa DOUBLE COMMENT 'Nota desta amostra para a classe baixa.',
    justificativa_classe_baixa STRING COMMENT 'Justificativa desta amostra para a classe baixa.',
    nota_classe_alta DOUBLE COMMENT 'Nota desta amostra para a classe alta.',
    justificativa_classe_alta STRING COMMENT 'Justificativa desta amostra para a classe alta.',
    fonte_texto STRING COMMENT 'Documento pontuado (v3).',
    ids_documento STRING COMMENT 'Ids dos PDFs pontuados (v3), separados por vírgula.',
    CONSTRAINT pk_fact_materia_score_amostra PRIMARY KEY (codigo_materia, prompt_version, amostra),
    CONSTRAINT fk_score_amostra_materia FOREIGN KEY (codigo_materia) REFERENCES senado_votacoes.gold.dim_materia(codigo_materia)
)
COMMENT 'Star schema formal: cada amostra de nota por LLM, de todas as versões (mesma entidade de silver.materia_scores_amostras). fact_materia_scored é a nota publicada; esta é a matéria-prima dela e da reamostragem de mart_estabilidade_rotulo_senador, e é onde se audita a variação entre amostras.'
AS SELECT * FROM senado_votacoes.silver.materia_scores_amostras
