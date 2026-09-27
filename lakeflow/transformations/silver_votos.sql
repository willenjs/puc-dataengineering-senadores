-- lakeflow/transformations/silver_votos.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.silver.votos (
    codigo_votacao STRING COMMENT 'Votação em que este voto foi registrado.',
    codigo_senador STRING COMMENT 'Senador que registrou o voto.',
    voto_raw STRING COMMENT 'Valor original do campo Voto retornado pela API (inclui códigos de ausência como LS, NCom, P-NRV, e "Votou" para votação secreta).',
    voto STRING COMMENT 'Voto normalizado em 5 categorias: Sim, Não, Abstenção, Secreto (voto_raw = "Votou": votação secreta, o senador votou mas o sentido não é público) ou Ausente (qualquer outro código: licenças LS/LP/LAP, missão MIS, NCom, AP, NA, P-NRV -- presente mas não registrou voto -- e o presidente da sessão, que não vota por regra, art. 51 do RISF). Só Sim/Não carregam direção; Secreto conta como participação mas não como posição.',
    CONSTRAINT codigo_votacao_not_null EXPECT (codigo_votacao IS NOT NULL) ON VIOLATION FAIL UPDATE,
    CONSTRAINT codigo_senador_not_null EXPECT (codigo_senador IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Um voto individual de um senador em uma votação, um por linha.'
AS
WITH ultimo_lote_por_ano AS (
    SELECT payload
    FROM senado_votacoes.bronze.votacoes_lista_anual
    QUALIFY row_number() OVER (
        PARTITION BY split_part(split_part(_source_endpoint, '_', -1), '.json', 1)
        ORDER BY split_part(_source_endpoint, 'dt=', -1) DESC, _loaded_at DESC
    ) = 1
),

votacoes AS (
    SELECT value AS votacao
    FROM ultimo_lote_por_ano, LATERAL variant_explode(payload:ListaVotacoes.Votacoes.Votacao) AS t
),

votos AS (
    SELECT
        votacao:CodigoSessaoVotacao::STRING AS codigo_votacao,
        v.value AS voto_parlamentar
    FROM votacoes, LATERAL variant_explode(votacao:Votos.VotoParlamentar) AS v
)

SELECT
    codigo_votacao,
    voto_parlamentar:CodigoParlamentar::STRING AS codigo_senador,
    voto_parlamentar:Voto::STRING AS voto_raw,
    CASE
        WHEN voto_parlamentar:Voto::STRING IN ('Sim', 'Não', 'Abstenção')
            THEN voto_parlamentar:Voto::STRING
        WHEN voto_parlamentar:Voto::STRING = 'Votou'
            THEN 'Secreto'
        ELSE 'Ausente'
    END AS voto
FROM votos
