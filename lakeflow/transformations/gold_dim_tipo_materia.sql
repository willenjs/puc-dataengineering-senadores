-- lakeflow/transformations/gold_dim_tipo_materia.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.dim_tipo_materia (
    sigla STRING NOT NULL PRIMARY KEY COMMENT 'Sigla do tipo de matéria (ex.: PL, PEC, PLP, MPV, VET, RQS).',
    descricao STRING COMMENT 'Nome completo do tipo de matéria.',
    data_inicio DATE COMMENT 'Data a partir da qual esta sigla passou a ser usada.',
    data_fim DATE COMMENT 'Data em que esta sigla deixou de ser usada -- NULL quando ainda está ativa.',
    materia_substantiva BOOLEAN COMMENT 'true para tipos de matéria legislativa com conteúdo normativo próprio (PL, PLP, PEC, MPV, PLC, PLS, PLN, SCD, PRS, PDS, VET); false para atos procedimentais, nomeações e comunicações (MSF, OFS, RQS, REQ, PDL, etc.). Filtro de entrada do índice de viés distributivo (mart_contribuicao_senador_materia) e do scoring por LLM (scripts/run_llm_scoring.py).'
)
COMMENT 'Star schema formal: domínio controlado de tipos/siglas de matéria (mesma entidade de silver.tipos_materia, sem transformação adicional) -- dá significado a dim_materia.sigla.'
AS SELECT * FROM senado_votacoes.silver.tipos_materia
