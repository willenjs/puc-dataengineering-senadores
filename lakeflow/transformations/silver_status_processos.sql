-- lakeflow/transformations/silver_status_processos.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.silver.status_processos (
    id_processo STRING COMMENT 'Identificador do processo legislativo -- FK para materias.id_processo.',
    tramitando STRING COMMENT '"Sim" se o processo ainda está em tramitação (pode gerar novas votações), "Não" se já concluiu -- para a MATÉRIA cujo id_processo é este, não para eventuais processos relacionados (ex.: um veto pendente é um id_processo à parte, com seu próprio codigoMateria).',
    situacao_atual STRING COMMENT 'Texto da situação de tramitação atual (ex.: "TRANSFORMADA EM NORMA JURÍDICA"). Ausente para alguns tipos de matéria (ex.: MSF) mesmo quando tramitando está presente.',
    sigla_situacao_atual STRING COMMENT 'Código curto da situação atual -- FK para situacoes_materia.sigla.',
    data_situacao_atual DATE COMMENT 'Data em que a situação atual foi atingida.',
    -- Derivado aqui (não no Gold) para manter dim_processo um pass-through puro, como
    -- as demais dim_/fact_. Simplificado após investigação empírica: um veto ou
    -- matéria sucessora pendente tem seu próprio id_processo/codigoMateria à parte (ver
    -- handoff), então não ameaça a conclusão DESTE processo -- só tramitando importa.
    materia_concluida BOOLEAN COMMENT 'tramitando = "Não" -- indica que não é esperada nova votação sob este id_processo. Não garante que a matéria como um todo (incluindo eventuais processos sucessores/veto, cada um com seu próprio id_processo) tenha se resolvido.',
    CONSTRAINT id_processo_not_null EXPECT (id_processo IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Status de tramitação de cada processo legislativo referenciado por uma matéria efetivamente votada (fonte: /processo/{id}, substituto oficial de /materia/situacaoatual e /materia/{codigo} para esta finalidade, ambos descontinuados). Escopado às ~360 matérias votadas -- ver scripts/run_materia_status_fetch.py.'
AS
WITH ultimo_lote AS (
    SELECT payload
    FROM senado_votacoes.bronze.status_processos
    QUALIFY row_number() OVER (
        PARTITION BY payload:id::STRING
        ORDER BY split_part(_source_endpoint, 'dt=', -1) DESC, _loaded_at DESC
    ) = 1
)
SELECT
    payload:id::STRING AS id_processo,
    payload:tramitando::STRING AS tramitando,
    payload:situacaoAtual::STRING AS situacao_atual,
    payload:siglaSituacaoAtual::STRING AS sigla_situacao_atual,
    payload:dataSituacaoAtual::DATE AS data_situacao_atual,
    payload:tramitando::STRING = 'Não' AS materia_concluida
FROM ultimo_lote
