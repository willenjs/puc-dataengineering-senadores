-- lakeflow/transformations/silver_fila_materias_detalhe.sql
-- View de controle: não descreve uma entidade do mundo real, e sim o trabalho que a
-- tarefa gap_fill_materias do Job ainda tem pela frente. O prefixo fila_ existe para
-- que ninguém a confunda com uma entidade da Silver, do mesmo jeito que mart_ separa
-- resposta pré-agregada de fato join-ready no Gold.
--
-- A tarefa lê ESTA view e não o Gold: o que atravessa a fronteira é uma lista de
-- identificadores (controle), nunca um dado derivado, e o que a tarefa grava na Bronze
-- é o payload cru de /materia/{codigo}, numa partição dt= nova. A dependência fica
-- declarada no catálogo em vez de escondida num join dentro do Python.
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.silver.fila_materias_detalhe (
    codigo_materia STRING COMMENT 'Código da matéria que precisa ser buscada individualmente em /materia/{codigo}. Herda a restrição de not null de silver.votacoes.'
)
COMMENT 'Fila da tarefa gap_fill_materias: matérias referenciadas por alguma votação mas ausentes de silver.materias, porque a busca por ano (/materia/pesquisa/lista?ano=) não devolve toda matéria que depois é votada -- um projeto apresentado antes de 2023 e votado em 2024, por exemplo. Fica vazia quando não há nada a buscar, e é assim que a tarefa decide não chamar a API.'
AS
SELECT DISTINCT v.codigo_materia
FROM senado_votacoes.silver.votacoes v
LEFT JOIN senado_votacoes.silver.materias m ON m.codigo_materia = v.codigo_materia
WHERE m.codigo_materia IS NULL
