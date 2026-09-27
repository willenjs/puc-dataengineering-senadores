-- lakeflow/transformations/gold_mart_destaque_senador.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.mart_destaque_senador (
    codigo_senador STRING NOT NULL COMMENT 'FK para dim_senador.',
    quadrante STRING NOT NULL COMMENT '"pro_classe_baixa": a posição do senador, entre as matérias contestadas, com maior contribuicao_centrada, e só quando essa contribuição é positiva. "pro_classe_alta": a de menor contribuicao_centrada, e só quando é negativa. O rótulo é verdadeiro por construção: a linha existe apenas quando é de fato desvio naquela direção.',
    codigo_materia STRING NOT NULL COMMENT 'FK para dim_materia -- matéria que define este quadrante para o senador. Sigla/número/ano/ementa ficam em dim_materia; consumidores fazem o join.',
    voto STRING NOT NULL COMMENT 'Sim ou Não -- como o senador votou nessa matéria. Permite à UI escrever "votou Não em ..." em vez de só "matéria de maior nota".',
    nota_classe_baixa DOUBLE COMMENT 'Nota da matéria para a classe baixa.',
    nota_classe_alta DOUBLE COMMENT 'Nota da matéria para a classe alta.',
    vies_distributivo DOUBLE COMMENT 'nota_classe_baixa - nota_classe_alta da matéria.',
    contribuicao_centrada DOUBLE COMMENT 'Contribuição centrada desta posição (ver mart_contribuicao_senador_materia) -- o critério de escolha do quadrante. Estritamente positiva nas linhas pro_classe_baixa e estritamente negativa nas pro_classe_alta.',
    n_sim_plenario BIGINT COMMENT 'Quantos senadores votaram Sim nesta matéria -- contexto para a UI ("contra 48 votos Sim").',
    n_nao_plenario BIGINT COMMENT 'Quantos senadores votaram Não nesta matéria. Sempre 5 ou mais aqui: só matérias contestadas são candidatas.',
    justificativa_classe_baixa STRING COMMENT 'Justificativa do LLM para nota_classe_baixa.',
    justificativa_classe_alta STRING COMMENT 'Justificativa do LLM para nota_classe_alta.',
    CONSTRAINT quadrante_valido EXPECT (quadrante IN ('pro_classe_baixa', 'pro_classe_alta')) ON VIOLATION FAIL UPDATE,
    CONSTRAINT contribuicao_com_sinal_do_quadrante EXPECT (
        (quadrante = 'pro_classe_baixa' AND contribuicao_centrada > 0)
        OR (quadrante = 'pro_classe_alta' AND contribuicao_centrada < 0)
    ) ON VIOLATION FAIL UPDATE,
    CONSTRAINT pk_mart_destaque_senador PRIMARY KEY (codigo_senador, quadrante),
    CONSTRAINT fk_mart_destaque_senador FOREIGN KEY (codigo_senador) REFERENCES senado_votacoes.gold.dim_senador(codigo_senador),
    CONSTRAINT fk_mart_destaque_materia FOREIGN KEY (codigo_materia) REFERENCES senado_votacoes.gold.dim_materia(codigo_materia)
)
COMMENT 'Para cada senador, as duas pontas do eixo distributivo entre suas posições em matérias contestadas (5 ou mais votos Não no plenário): a de maior e a de menor contribuição centrada. Esta tabela existe para ser PROVA -- a afirmação que ela sustenta é "este senador desviou do plenário nesta direção, e foi neste voto" -- então uma ponta só vira linha quando o sinal confirma a direção do rótulo. Zero é ausência de desvio, não desvio, por isso o predicado é estrito. Um senador sem desvio numa direção simplesmente não tem linha naquele quadrante, e isso é informação verdadeira ("não há evidência"): a UI trata a ausência. Substitui os 4 quadrantes classe x sentido usados até 2026-09-14 -- com o eixo único, "Sim em matéria pró-classe-baixa" e "Não em matéria pró-classe-alta" são a mesma evidência. Restringir a contestadas evita que uma matéria unânime seja o destaque de 60 senadores ao mesmo tempo. NÃO há mínimo de posições aqui, de propósito: o índice exige 20 porque afirma um padrão, o destaque afirma um voto específico, verdadeiro mesmo com uma posição só.'
AS
WITH candidatas AS (
    SELECT c.*, ms.justificativa_classe_baixa, ms.justificativa_classe_alta
    FROM senado_votacoes.gold.mart_contribuicao_senador_materia c
    JOIN senado_votacoes.gold.fact_materia_scored ms ON ms.codigo_materia = c.codigo_materia
    WHERE c.n_nao_plenario >= 5
),
-- codigo_materia como desempate no ORDER BY: sem ele, duas posições com exatamente a
-- mesma contribuicao_centrada dariam um destaque não-determinístico entre refreshes.
-- O filtro de sinal vai no WHERE, antes do row_number: sem ele, o "melhor" candidato de
-- um senador que nunca desviou naquela direção seria emitido como se fosse evidência.
pro_baixa AS (
    SELECT 'pro_classe_baixa' AS quadrante, *
    FROM candidatas
    WHERE contribuicao_centrada > 0
    QUALIFY row_number() OVER (PARTITION BY codigo_senador ORDER BY contribuicao_centrada DESC, codigo_materia) = 1
),
pro_alta AS (
    SELECT 'pro_classe_alta' AS quadrante, *
    FROM candidatas
    WHERE contribuicao_centrada < 0
    QUALIFY row_number() OVER (PARTITION BY codigo_senador ORDER BY contribuicao_centrada ASC, codigo_materia) = 1
)
SELECT codigo_senador, quadrante, codigo_materia, voto, nota_classe_baixa, nota_classe_alta,
       vies_distributivo, contribuicao_centrada, n_sim_plenario, n_nao_plenario,
       justificativa_classe_baixa, justificativa_classe_alta
FROM pro_baixa
UNION ALL
SELECT codigo_senador, quadrante, codigo_materia, voto, nota_classe_baixa, nota_classe_alta,
       vies_distributivo, contribuicao_centrada, n_sim_plenario, n_nao_plenario,
       justificativa_classe_baixa, justificativa_classe_alta
FROM pro_alta
