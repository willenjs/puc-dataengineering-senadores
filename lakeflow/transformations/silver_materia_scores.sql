-- lakeflow/transformations/silver_materia_scores.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.silver.materia_scores (
    codigo_materia STRING COMMENT 'Matéria a que esta nota se refere.',
    prompt_version STRING COMMENT 'Versão do prompt da nota vigente: v3-com-empurrao (texto integral, mediana de 9 amostras) quando a matéria tem as 9, senão v2, senão v1.',
    n_amostras INT COMMENT 'Quantas amostras formam a nota. 9 na v3, que publica a mediana e nunca publica com menos de 9 (decisão de 2026-09-17); 1 na v1 e na v2, que publicam a menor amostra.',
    nota_classe_baixa DOUBLE COMMENT 'Nota de -1 (prejudicial) a 1 (benéfico) do impacto da matéria para o brasileiro de classe baixa. Na v3, a mediana das 9 amostras.',
    justificativa_classe_baixa STRING COMMENT 'Justificativa da amostra cuja nota de classe baixa é a mediana (menor índice em caso de empate): texto que o modelo escreveu para exatamente a nota publicada ao lado.',
    amostra_justificativa_classe_baixa INT COMMENT 'De qual amostra veio justificativa_classe_baixa, para a auditoria fechar contra silver.materia_scores_amostras e a resposta crua no Volume.',
    nota_classe_alta DOUBLE COMMENT 'Nota de -1 a 1 do impacto da matéria para o brasileiro de classe alta. Na v3, a mediana das 9 amostras.',
    justificativa_classe_alta STRING COMMENT 'Justificativa da amostra cuja nota de classe alta é a mediana (menor índice em caso de empate).',
    amostra_justificativa_classe_alta INT COMMENT 'De qual amostra veio justificativa_classe_alta.',
    fonte_texto STRING COMMENT 'Documento pontuado (v3; NULL na v1/v2, que pontuavam a ementa). Ver silver.materia_scores_amostras.',
    ids_documento STRING COMMENT 'Ids dos PDFs pontuados (v3), separados por vírgula.',
    CONSTRAINT codigo_materia_not_null EXPECT (codigo_materia IS NOT NULL) ON VIOLATION FAIL UPDATE,
    CONSTRAINT nota_classe_baixa_range EXPECT (nota_classe_baixa BETWEEN -1 AND 1) ON VIOLATION FAIL UPDATE,
    CONSTRAINT nota_classe_alta_range EXPECT (nota_classe_alta BETWEEN -1 AND 1) ON VIOLATION FAIL UPDATE,
    -- A mediana de um número ímpar de amostras é sempre a nota de uma delas; se a amostra da
    -- justificativa não for achada, a mediana não é o que se pensa, e a atualização falha.
    CONSTRAINT justificativa_baixa_encontrada EXPECT (amostra_justificativa_classe_baixa IS NOT NULL) ON VIOLATION FAIL UPDATE,
    CONSTRAINT justificativa_alta_encontrada EXPECT (amostra_justificativa_classe_alta IS NOT NULL) ON VIOLATION FAIL UPDATE,
    CONSTRAINT v3_so_com_9_amostras EXPECT (prompt_version <> 'v3-com-empurrao' OR n_amostras = 9) ON VIOLATION FAIL UPDATE
)
COMMENT 'Nota de alinhamento socioeconômico por matéria, gerada por LLM, uma linha por matéria. Versão vigente por prioridade explícita: v3-com-empurrao, a mediana de 9 amostras sobre o texto integral votado, quando a matéria tem as 9; senão v2 (ementa, sigla, número, ano e tipo); senão v1 (só a ementa). A v3-sem-empurrao, que perdeu o teste A/B do empurrão fiscal pelo critério declarado antes, fica em silver.materia_scores_amostras e não é publicada. O autor nunca entra no prompt, e na v3 a identidade de quem propôs, relatou ou assinou é retirada do texto.'
AS
-- Allowlist das versões PUBLICADAS, com a prioridade de cada uma. Até 2026-09-17 a versão
-- vigente era a do arquivo mais recente; com a v3 gravando duas variantes do teste A/B, "a mais
-- recente" seria a última variante coletada, então a prioridade passa a ser declarada.
-- v3-com-empurrao venceu o A/B em 2026-09-18: 20 matérias com viés exatamente 0 sem o empurrão
-- contra 16 com ele, e a regra declarada antes manda manter o empurrão quando sem ele há mais
-- zeros (spec da v3, seção 7).
WITH publicadas AS (
    SELECT
        *,
        CASE prompt_version WHEN 'v3-com-empurrao' THEN 3 WHEN 'v2' THEN 2 WHEN 'v1' THEN 1 END AS prioridade,
        prompt_version = 'v3-com-empurrao' AS multiamostra
    FROM senado_votacoes.silver.materia_scores_amostras
    WHERE prompt_version IN ('v1', 'v2', 'v3-com-empurrao')
),
-- A v3 só vale com as amostras 1 a 9 todas presentes: a mediana de 7 não é a mediana de 9, e a
-- estabilidade do rótulo foi calculada para 9. Matéria incompleta segue na versão anterior.
v3_completas AS (
    SELECT codigo_materia
    FROM publicadas
    WHERE multiamostra AND amostra BETWEEN 1 AND 9
    GROUP BY codigo_materia
    HAVING count(DISTINCT amostra) = 9
),
candidatas AS (
    SELECT p.*
    FROM publicadas p
    LEFT JOIN v3_completas c ON c.codigo_materia = p.codigo_materia
    WHERE NOT p.multiamostra OR (c.codigo_materia IS NOT NULL AND p.amostra BETWEEN 1 AND 9)
),
versao_vigente AS (
    SELECT codigo_materia, prompt_version
    FROM (SELECT DISTINCT codigo_materia, prompt_version, prioridade FROM candidatas)
    QUALIFY row_number() OVER (PARTITION BY codigo_materia ORDER BY prioridade DESC) = 1
),
-- As amostras que formam a nota: as 9 na v3; na v1 e na v2, só a menor, como sempre foi (a
-- rodada de repetibilidade gravou uma segunda amostra v2 que não pode mover o Gold).
conjunto AS (
    SELECT c.*
    FROM candidatas c
    JOIN versao_vigente v ON v.codigo_materia = c.codigo_materia AND v.prompt_version = c.prompt_version
    QUALIFY c.multiamostra OR row_number() OVER (PARTITION BY c.codigo_materia ORDER BY c.amostra) = 1
),
medianas AS (
    SELECT
        codigo_materia,
        prompt_version,
        CAST(count(*) AS INT) AS n_amostras,
        median(nota_classe_baixa) AS nota_classe_baixa,
        median(nota_classe_alta) AS nota_classe_alta
    FROM conjunto
    GROUP BY codigo_materia, prompt_version
)
-- A justificativa não tem mediana: vem da amostra cuja nota daquela classe É a mediana, com
-- desempate pelo menor índice, por classe (decisão de 2026-09-17).
SELECT
    m.codigo_materia,
    m.prompt_version,
    m.n_amostras,
    m.nota_classe_baixa,
    min_by(c.justificativa_classe_baixa, c.amostra) FILTER (WHERE c.nota_classe_baixa = m.nota_classe_baixa) AS justificativa_classe_baixa,
    min(c.amostra) FILTER (WHERE c.nota_classe_baixa = m.nota_classe_baixa) AS amostra_justificativa_classe_baixa,
    m.nota_classe_alta,
    min_by(c.justificativa_classe_alta, c.amostra) FILTER (WHERE c.nota_classe_alta = m.nota_classe_alta) AS justificativa_classe_alta,
    min(c.amostra) FILTER (WHERE c.nota_classe_alta = m.nota_classe_alta) AS amostra_justificativa_classe_alta,
    max(c.fonte_texto) AS fonte_texto,
    max(c.ids_documento) AS ids_documento
FROM medianas m
JOIN conjunto c ON c.codigo_materia = m.codigo_materia AND c.prompt_version = m.prompt_version
GROUP BY m.codigo_materia, m.prompt_version, m.n_amostras, m.nota_classe_baixa, m.nota_classe_alta
