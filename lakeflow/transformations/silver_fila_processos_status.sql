-- lakeflow/transformations/silver_fila_processos_status.sql
-- View de controle da tarefa status_processos_fetch -- ver o cabeçalho de
-- silver_fila_materias_detalhe.sql para o papel do prefixo fila_.
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.silver.fila_processos_status (
    id_processo STRING COMMENT 'Identificador do processo legislativo a consultar em /processo/{id}. Nunca nulo nesta view.'
)
COMMENT 'Fila da tarefa status_processos_fetch: o processo de cada matéria que já gerou votação. Mesmo recorte de custo das outras duas filas -- consulta o processo das matérias votadas, não o das ~18k matérias apresentadas.'
AS
SELECT DISTINCT m.id_processo
FROM senado_votacoes.silver.materias m
JOIN senado_votacoes.silver.votacoes v ON v.codigo_materia = m.codigo_materia
WHERE m.id_processo IS NOT NULL
