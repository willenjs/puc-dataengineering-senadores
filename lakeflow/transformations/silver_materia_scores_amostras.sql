-- lakeflow/transformations/silver_materia_scores_amostras.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.silver.materia_scores_amostras (
    codigo_materia STRING COMMENT 'Matéria a que esta amostra se refere.',
    prompt_version STRING COMMENT 'Versão do prompt que gerou a amostra. Inclui versões em avaliação (as duas variantes da v3 do teste A/B do empurrão fiscal); quem decide o que é publicado é silver.materia_scores.',
    amostra INT COMMENT 'Índice da repetição desta (matéria, versão). O modelo é um avaliador estocástico, e a v3 grava 9 amostras por matéria e versão. Arquivos anteriores ao campo contam como amostra 1.',
    nota_classe_baixa DOUBLE COMMENT 'Nota de -1 (prejudicial) a 1 (benéfico) desta amostra para a classe baixa (chave congelada nota_pobre).',
    justificativa_classe_baixa STRING COMMENT 'Justificativa desta amostra para a nota de classe baixa.',
    nota_classe_alta DOUBLE COMMENT 'Nota de -1 a 1 desta amostra para a classe alta (chave congelada nota_rico).',
    justificativa_classe_alta STRING COMMENT 'Justificativa desta amostra para a nota de classe alta.',
    fonte_texto STRING COMMENT 'Documento de onde veio o texto pontuado (v3): RF_TEXTO, RF_TURNO_SUPLEMENTAR, RF_2TURNO, AUT_TEXTO, INICIAL_VERIFICADO, CASO_B_SUBSTITUTIVO ou COMPOSTO_INICIAL_MAIS_EMENDAS_DO_SENADO. NULL na v1 e na v2, que pontuavam a ementa.',
    ids_documento STRING COMMENT 'Ids dos PDFs pontuados, separados por vírgula, no Senado (sdleg-getter/documento?dm=<id>). Permite rastrear qualquer nota v3 até o documento exato. NULL na v1 e na v2.',
    CONSTRAINT codigo_materia_not_null EXPECT (codigo_materia IS NOT NULL) ON VIOLATION FAIL UPDATE,
    CONSTRAINT nota_classe_baixa_range EXPECT (nota_classe_baixa BETWEEN -1 AND 1) ON VIOLATION FAIL UPDATE,
    CONSTRAINT nota_classe_alta_range EXPECT (nota_classe_alta BETWEEN -1 AND 1) ON VIOLATION FAIL UPDATE
)
COMMENT 'Todas as amostras legíveis (status ok) de nota por LLM, uma linha por (matéria, versão de prompt, amostra), de todas as versões, publicadas ou não. É a base da mediana de silver.materia_scores e da reamostragem de gold.mart_estabilidade_rotulo_senador.'
AS
-- Chaves congeladas no Bronze (nota_pobre/nota_rico); o rename para classe_baixa/classe_alta é
-- aqui, como sempre foi em silver.materia_scores.
WITH notas AS (
    SELECT
        payload:codigo_materia::STRING AS codigo_materia,
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
      -- Só o texto da matéria: as amostras de emenda destacada têm numero_objeto e vivem em
      -- silver.emenda_scores_amostras, com chave própria.
      AND coalesce(payload:objeto_votado::STRING, 'texto') = 'texto'
)
-- Mesma ordenação de dedup dos irmãos Silver: a data embutida no caminho primeiro, `_loaded_at`
-- só como desempate. Resolve a regravação da MESMA amostra, nunca a escolha entre amostras.
SELECT
    codigo_materia,
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
    PARTITION BY codigo_materia, prompt_version, amostra
    ORDER BY dt_particao DESC, _loaded_at DESC
) = 1
