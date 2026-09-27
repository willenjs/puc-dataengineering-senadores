-- lakeflow/transformations/gold_mart_concordancia_par_senadores.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.mart_concordancia_par_senadores (
    codigo_senador_a STRING NOT NULL COMMENT 'FK para dim_senador -- menor dos dois códigos do par (ordem lexical de string).',
    codigo_senador_b STRING NOT NULL COMMENT 'FK para dim_senador -- o outro senador do par.',
    votacoes_em_comum BIGINT COMMENT 'Quantidade de VOTAÇÕES em que ambos os senadores do par manifestaram posição (Sim/Não/Abstenção). Uma linha por decisão do plenário: os dois turnos de uma PEC contam duas vezes, cada destaque conta por si, e requerimentos contam -- todas são decisões distintas em que os dois ou votaram igual ou não.',
    votacoes_concordantes BIGINT COMMENT 'Dentre votacoes_em_comum, quantidade em que os dois votaram de forma idêntica.',
    taxa_concordancia DOUBLE COMMENT 'votacoes_concordantes dividido por votacoes_em_comum.',
    CONSTRAINT taxa_concordancia_not_null EXPECT (taxa_concordancia IS NOT NULL) ON VIOLATION FAIL UPDATE,
    CONSTRAINT pk_mart_concordancia_par_senadores PRIMARY KEY (codigo_senador_a, codigo_senador_b),
    CONSTRAINT fk_mart_concordancia_senador_a FOREIGN KEY (codigo_senador_a) REFERENCES senado_votacoes.gold.dim_senador(codigo_senador),
    CONSTRAINT fk_mart_concordancia_senador_b FOREIGN KEY (codigo_senador_b) REFERENCES senado_votacoes.gold.dim_senador(codigo_senador)
)
COMMENT 'Taxa de concordância de voto entre cada par de senadores, contada por votação. Nome/partido/UF/foto de cada senador ficam em dim_senador -- consumidores fazem o join.'
AS
-- Self-join em fact_voto_senador, por VOTAÇÃO, exatamente como mart_coesao_bancada_uf:
-- as duas medidas de acordo exibidas na mesma página precisam do mesmo denominador, ou o
-- visitante compara números que não são comparáveis. Até 2026-09-16 esta view lia
-- mart_posicao_senador e contava uma posição por matéria; quando aquela view passou a ser
-- por objeto votado (e a aceitar só texto), continuar lendo de lá teria encolhido a base
-- em 18% por efeito colateral, sem ninguém ter decidido isso.
--
-- Concordância não é o índice: ela não pergunta qual o efeito distributivo da matéria, só
-- se os dois votaram igual. Por isso não depende de nota, de matéria substantiva nem de
-- objeto votado, e conta toda votação nominal -- inclusive requerimentos, que são decisões
-- reais do plenário. A restrição a objetos pontuados vale para o índice, que multiplica o
-- voto por uma nota, e não para uma medida de puro acordo.
SELECT
    va.codigo_senador AS codigo_senador_a,
    vb.codigo_senador AS codigo_senador_b,
    count(*) AS votacoes_em_comum,
    count(CASE WHEN va.voto = vb.voto THEN 1 END) AS votacoes_concordantes,
    nvl(try_divide(count(CASE WHEN va.voto = vb.voto THEN 1 END), count(*)), 0) AS taxa_concordancia
FROM senado_votacoes.gold.fact_voto_senador va
JOIN senado_votacoes.gold.fact_voto_senador vb
    ON va.codigo_votacao = vb.codigo_votacao
    AND va.codigo_senador < vb.codigo_senador
WHERE va.voto IN ('Sim', 'Não', 'Abstenção')
  AND vb.voto IN ('Sim', 'Não', 'Abstenção')
GROUP BY 1, 2
