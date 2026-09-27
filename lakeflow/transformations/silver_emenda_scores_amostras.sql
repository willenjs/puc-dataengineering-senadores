-- lakeflow/transformations/silver_emenda_scores_amostras.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.silver.emenda_scores_amostras (
    codigo_materia STRING COMMENT 'Matéria a que a emenda destacada pertence.',
    numero_objeto STRING COMMENT 'Número da emenda destacada (fact_votacao.numero_objeto), o que distingue as três emendas de uma mesma matéria.',
    prompt_version STRING COMMENT 'Versão do prompt que gerou a amostra (emenda-v1).',
    amostra INT COMMENT 'Índice da repetição desta (matéria, emenda, versão), de 1 a 9. O modelo é um avaliador estocástico, e cada emenda recebe 9 amostras independentes.',
    nota_classe_baixa DOUBLE COMMENT 'Nota de -1 (prejudicial) a 1 (benéfico) desta amostra para a classe baixa (chave congelada nota_pobre).',
    justificativa_classe_baixa STRING COMMENT 'Justificativa desta amostra para a nota de classe baixa.',
    nota_classe_alta DOUBLE COMMENT 'Nota de -1 a 1 desta amostra para a classe alta (chave congelada nota_rico).',
    justificativa_classe_alta STRING COMMENT 'Justificativa desta amostra para a nota de classe alta.',
    fonte_texto STRING COMMENT 'Documento que serviu de TEXTO-BASE da emenda: RF_TEXTO, RF_TURNO_SUPLEMENTAR, RF_2TURNO, AUT_TEXTO, INICIAL_VERIFICADO, CASO_B_SUBSTITUTIVO ou COMPOSTO_INICIAL_MAIS_EMENDAS_DO_SENADO. Ver senado_pipeline/emenda_destacada.py.',
    ids_documento STRING COMMENT 'Ids dos PDFs do texto-base, separados por vírgula (sdleg-getter/documento?dm=<id>).',
    CONSTRAINT codigo_materia_not_null EXPECT (codigo_materia IS NOT NULL) ON VIOLATION FAIL UPDATE,
    CONSTRAINT nota_classe_baixa_range EXPECT (nota_classe_baixa BETWEEN -1 AND 1) ON VIOLATION FAIL UPDATE,
    CONSTRAINT nota_classe_alta_range EXPECT (nota_classe_alta BETWEEN -1 AND 1) ON VIOLATION FAIL UPDATE
)
COMMENT 'Todas as amostras legíveis (status ok) de nota de EMENDA DESTACADA, uma linha por (matéria, emenda, versão de prompt, amostra). A nota de uma emenda é a de um delta: o efeito de aprová-la em relação ao texto-base. É a base da mediana de silver.emenda_scores e da reamostragem de gold.mart_estabilidade_rotulo_senador.'
AS
-- Chaves congeladas no Bronze (nota_pobre/nota_rico); o rename para classe_baixa/classe_alta é
-- aqui, como sempre foi em silver.materia_scores.
WITH notas AS (
    SELECT
        payload:codigo_materia::STRING AS codigo_materia,
        payload:numero_objeto::STRING AS numero_objeto,
        payload:prompt_version::STRING AS prompt_version,
        coalesce(payload:amostra::INT, 1) AS amostra,
        payload:nota_pobre::DOUBLE AS nota_classe_baixa,
        payload:justificativa_pobre::STRING AS justificativa_classe_baixa,
        payload:nota_rico::DOUBLE AS nota_classe_alta,
        payload:justificativa_rico::STRING AS justificativa_classe_alta,
        payload:fonte_texto::STRING AS fonte_texto,
        -- O payload grava uma lista JSON de inteiros ([9190700, 9549355]); fica "9190700,9549355".
        nullif(regexp_replace(payload:ids_documento::STRING, r'[\[\]\s"]', ''), '') AS ids_documento,
        split_part(_source_endpoint, 'dt=', -1) AS dt_particao,
        _loaded_at
    FROM senado_votacoes.bronze.materia_llm_scores_raw
    WHERE payload:status::STRING = 'ok'
      AND payload:objeto_votado::STRING = 'emenda'
)
-- Mesma ordenação de dedup dos irmãos Silver: a data embutida no caminho primeiro, `_loaded_at`
-- só como desempate. Resolve a regravação da MESMA amostra, nunca a escolha entre amostras.
SELECT
    codigo_materia,
    numero_objeto,
    prompt_version,
    amostra,
    nota_classe_baixa,
    justificativa_classe_baixa,
    nota_classe_alta,
    justificativa_classe_alta,
    fonte_texto,
    ids_documento
FROM notas
QUALIFY row_number() OVER (
    PARTITION BY codigo_materia, numero_objeto, prompt_version, amostra
    ORDER BY dt_particao DESC, _loaded_at DESC
) = 1
