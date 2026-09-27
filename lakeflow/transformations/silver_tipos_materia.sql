-- lakeflow/transformations/silver_tipos_materia.sql
-- Payload bruto é um array JSON no nível raiz (não um objeto com namespace, diferente
-- das demais fontes Bronze deste pipeline) -- variant_explode direto no payload.
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.silver.tipos_materia (
    sigla STRING COMMENT 'Sigla do tipo de matéria (ex.: PL, PEC, PLP, MPV, VET, RQS).',
    descricao STRING COMMENT 'Nome completo do tipo de matéria.',
    data_inicio DATE COMMENT 'Data a partir da qual esta sigla passou a ser usada.',
    data_fim DATE COMMENT 'Data em que esta sigla deixou de ser usada -- NULL quando ainda está ativa.',
    -- Derivado aqui (não no Gold) para manter dim_tipo_materia um pass-through puro,
    -- como materia_concluida em silver_status_processos.sql. Fica no domínio de tipos, e
    -- não hardcoded em cada mart ou no script Python, para que o scoring por LLM e as
    -- marts do Gold leiam exatamente a mesma lista.
    materia_substantiva BOOLEAN COMMENT 'true para tipos de matéria legislativa com conteúdo normativo próprio (PL, PLP, PEC, MPV, PLC, PLS, PLN, SCD, PRS, PDS, VET); false para atos procedimentais, nomeações e comunicações (MSF, OFS, RQS, REQ, PDL, etc.) -- estes não entram no scoring por LLM nem no índice de alinhamento, porque a ementa não descreve impacto distributivo.',
    CONSTRAINT sigla_not_null EXPECT (sigla IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Domínio controlado (referência oficial) de todos os tipos/siglas de matéria possíveis -- dá significado a dim_materia.sigla. Fonte: /processo/siglas (184 códigos, ativos e históricos, confirmados sem sigla duplicada). materia_substantiva é uma allowlist, não denylist: a maioria dos 184 códigos é procedimental, e uma sigla nova desconhecida deve cair fora do índice por padrão.'
AS
WITH ultimo_lote AS (
    SELECT payload
    FROM senado_votacoes.bronze.referencia_tipos_materia
    QUALIFY row_number() OVER (
        ORDER BY split_part(_source_endpoint, 'dt=', -1) DESC, _loaded_at DESC
    ) = 1
),
itens AS (
    SELECT value AS item
    FROM ultimo_lote, LATERAL variant_explode(payload) AS t
)
SELECT
    item:sigla::STRING AS sigla,
    item:descricao::STRING AS descricao,
    item:dataInicio::DATE AS data_inicio,
    item:dataFim::DATE AS data_fim,
    item:sigla::STRING IN ('PL', 'PLP', 'PEC', 'MPV', 'PLC', 'PLS', 'PLN', 'SCD', 'PRS', 'PDS', 'VET') AS materia_substantiva
FROM itens
