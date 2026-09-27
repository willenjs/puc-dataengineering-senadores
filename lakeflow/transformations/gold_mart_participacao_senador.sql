-- lakeflow/transformations/gold_mart_participacao_senador.sql
-- div0(a, b) do Snowflake -> nvl(try_divide(a, b), 0) no Databricks: try_divide
-- retorna NULL em vez de lançar erro na divisão por zero; nvl troca esse NULL por 0,
-- igual ao comportamento do div0 de hoje.
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.mart_participacao_senador (
    codigo_senador STRING NOT NULL PRIMARY KEY COMMENT 'FK para dim_senador.',
    total_votacoes BIGINT COMMENT 'Votações em que o senador poderia ter votado: todas as que têm registro para ele, exceto as em que presidia a sessão (voto_raw = "Presidente (art. 51 RISF)") -- o presidente não vota por regra, e contá-las penalizaria quem preside.',
    votacoes_participadas BIGINT COMMENT 'Dentre total_votacoes, quantas em que o senador votou: Sim, Não, Abstenção ou Secreto (votação secreta, em que votou mas o sentido não é público). P-NRV (presente, não registrou voto) e ausências não contam -- para uma métrica chamada participação em votações, não votar é não participar.',
    taxa_participacao DOUBLE COMMENT 'votacoes_participadas dividido por total_votacoes. 0 quando o senador não tem nenhum registro de voto.',
    CONSTRAINT taxa_participacao_not_null EXPECT (taxa_participacao IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Taxa de participação de cada senador nas votações do período -- métrica de contexto para avaliar a confiabilidade do índice de alinhamento. Nome fica em dim_senador -- consumidores fazem o join. Todo senador de dim_senador aparece aqui, mesmo quem nunca teve nenhum registro de voto (total_votacoes = 0, taxa_participacao = 0) -- ver nota sobre LEFT JOIN abaixo.'
AS
-- LEFT JOIN a partir de dim_senador (não de fact_voto_senador): senadores sem nenhum
-- voto registrado (ex.: figuras históricas incluídas em dim_senador que não estavam
-- em exercício nesta legislatura) antes simplesmente sumiam desta view em vez de
-- aparecer com 0/0 -- consistente com o mesmo tipo de correção nas outras marts.
--
-- `IS DISTINCT FROM` em vez de `<>`: na linha vazia do LEFT JOIN, voto_raw é NULL e
-- `NULL <> 'Presidente ...'` seria NULL (cai no ELSE, fora da contagem). Com
-- IS DISTINCT FROM a linha cai no THEN, onde v.codigo_votacao também é NULL e count()
-- a ignora de qualquer forma -- mantendo 0/0 para senador sem registro.
SELECT
    s.codigo_senador,
    count(CASE WHEN v.voto_raw IS DISTINCT FROM 'Presidente (art. 51 RISF)' THEN v.codigo_votacao END) AS total_votacoes,
    count(CASE WHEN v.voto IN ('Sim', 'Não', 'Abstenção', 'Secreto') THEN 1 END) AS votacoes_participadas,
    nvl(try_divide(
        count(CASE WHEN v.voto IN ('Sim', 'Não', 'Abstenção', 'Secreto') THEN 1 END),
        count(CASE WHEN v.voto_raw IS DISTINCT FROM 'Presidente (art. 51 RISF)' THEN v.codigo_votacao END)
    ), 0) AS taxa_participacao
FROM senado_votacoes.gold.dim_senador s
LEFT JOIN senado_votacoes.gold.fact_voto_senador v ON v.codigo_senador = s.codigo_senador
GROUP BY s.codigo_senador
