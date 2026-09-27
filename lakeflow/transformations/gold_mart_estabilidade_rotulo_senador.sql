-- lakeflow/transformations/gold_mart_estabilidade_rotulo_senador.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.mart_estabilidade_rotulo_senador (
    codigo_senador STRING NOT NULL PRIMARY KEY COMMENT 'FK para dim_senador. Só senadores elegíveis à classificação (20 ou mais posições não unânimes).',
    n_replicas INT COMMENT 'Reamostragens feitas: 4000. Eram 1000 até 2026-09-23, quando a entrada das emendas mudou a semente do sorteio e um senador a 0,959 de estabilidade trocou de lado: com 1000 reamostragens o erro do próprio sorteio é de cerca de 0,7%, da ordem da distância ao corte de 0,95. Com 4000 ele cai à metade.',
    frac_pro_classe_baixa DOUBLE COMMENT 'Fração das reamostragens em que o senador caiu no tercil superior do índice (pro_classe_baixa).',
    frac_equilibrado DOUBLE COMMENT 'Fração das reamostragens em que caiu no tercil médio (equilibrado).',
    frac_pro_classe_alta DOUBLE COMMENT 'Fração das reamostragens em que caiu no tercil inferior (pro_classe_alta).',
    rotulo_mais_frequente STRING COMMENT 'O rótulo que mais saiu nas reamostragens.',
    estabilidade DOUBLE COMMENT 'Fração do rótulo mais frequente. O rótulo só é publicado com 0,95 ou mais (mart_alinhamento_senador.classificacao_popular); abaixo disso o senador fica na fronteira.',
    segundo_rotulo STRING COMMENT 'O segundo rótulo mais frequente: com o mais frequente, forma a fronteira em que o senador está quando a estabilidade fica abaixo de 0,95.',
    CONSTRAINT fracoes_somam_um EXPECT (abs(frac_pro_classe_baixa + frac_equilibrado + frac_pro_classe_alta - 1) < 1e-9) ON VIOLATION FAIL UPDATE,
    CONSTRAINT fk_estabilidade_senador FOREIGN KEY (codigo_senador) REFERENCES senado_votacoes.gold.dim_senador(codigo_senador)
)
COMMENT 'Estabilidade do rótulo de cada senador sob o ruído do avaliador (spec da v3, seção 5). As 9 amostras de cada objeto votado (o texto de uma matéria ou uma emenda destacada dela) são reamostradas com reposição 4000 vezes; em cada reamostragem a nota da matéria é a mediana das sorteadas, o índice centrado e os tercis são recalculados com as mesmas regras de mart_contribuicao_senador_materia e mart_alinhamento_senador, e conta-se em que tercil cada senador caiu. O sorteio é determinístico (hash com semente fixa), então o resultado só muda se as notas ou as posições mudarem. Objeto com nota de amostra única (v1/v2) entra com a própria nota em todas as reamostragens: o ruído dela não foi medido, então não entra na conta -- em 2026-09-18 todas as matérias com posição têm as 9 amostras da v3, e a checagem 13b da verificação acusa se isso deixar de valer.'
AS
WITH
-- Posições que entram no índice centrado: não unânimes (mart_alinhamento_senador). A
-- contribuição centrada de mart_contribuicao_senador_materia é sinal * viés menos a média
-- do plenário de sinal * viés; como o viés é o mesmo para todos na matéria, isso é
-- viés * (sinal - sinal médio do plenário), e o sinal médio é (Sim - Não) / (Sim + Não).
posicoes AS (
    SELECT
        codigo_senador,
        codigo_materia,
        objeto_votado,
        numero_objeto,
        CASE WHEN voto = 'Sim' THEN 1.0 ELSE -1.0 END
            - (n_sim_plenario - n_nao_plenario) / (n_sim_plenario + n_nao_plenario) AS peso
    FROM senado_votacoes.gold.mart_contribuicao_senador_materia
    WHERE least(n_sim_plenario, n_nao_plenario) > 0
),
-- Mesmo corte de elegibilidade de mart_alinhamento_senador: 20 ou mais posições não unânimes.
elegiveis AS (
    SELECT codigo_senador FROM posicoes GROUP BY codigo_senador HAVING count(*) >= 20
),
-- Um objeto pontuado é o texto de uma matéria ou uma emenda destacada dela; os dois entram na
-- reamostragem do mesmo jeito, cada um com as suas amostras.
objetos AS (
    SELECT DISTINCT p.codigo_materia, p.objeto_votado, p.numero_objeto, s.prompt_version,
           s.n_amostras, s.nota_classe_baixa - s.nota_classe_alta AS vies_publicado
    FROM posicoes p
    JOIN senado_votacoes.gold.fact_materia_scored s ON s.codigo_materia = p.codigo_materia
    WHERE p.objeto_votado = 'texto'
    UNION ALL
    SELECT DISTINCT p.codigo_materia, p.objeto_votado, p.numero_objeto, e.prompt_version,
           e.n_amostras, e.nota_classe_baixa - e.nota_classe_alta AS vies_publicado
    FROM posicoes p
    JOIN senado_votacoes.gold.fact_emenda_scored e
        ON e.codigo_materia = p.codigo_materia AND e.numero_objeto = p.numero_objeto
    WHERE p.objeto_votado = 'emenda'
),
-- As amostras dos dois objetos, na mesma forma, para o sorteio não precisar saber de qual tabela
-- cada nota veio.
amostras AS (
    SELECT codigo_materia, 'texto' AS objeto_votado, 'texto' AS numero_objeto, prompt_version,
           amostra, nota_classe_baixa, nota_classe_alta
    FROM senado_votacoes.gold.fact_materia_score_amostra
    UNION ALL
    SELECT codigo_materia, 'emenda' AS objeto_votado, numero_objeto, prompt_version,
           amostra, nota_classe_baixa, nota_classe_alta
    FROM senado_votacoes.gold.fact_emenda_score_amostra
),
replicas AS (
    SELECT explode(sequence(1, 4000)) AS replica
),
-- Para cada reamostragem e matéria multiamostra, n_amostras sorteios com reposição. O hash
-- dá o mesmo sorteio em todo refresh; a semente é o texto fixo.
sorteios AS (
    SELECT r.replica, m.codigo_materia, m.objeto_votado, m.numero_objeto, m.prompt_version,
           1 + pmod(xxhash64('estabilidade-rotulo-v3', r.replica, m.codigo_materia, m.numero_objeto, k.k),
                    m.n_amostras) AS amostra
    FROM replicas r
    CROSS JOIN objetos m
    LATERAL VIEW explode(sequence(1, m.n_amostras)) k AS k
    WHERE m.n_amostras > 1
),
vies_por_replica AS (
    SELECT s.replica, s.codigo_materia, s.objeto_votado, s.numero_objeto,
           median(a.nota_classe_baixa) - median(a.nota_classe_alta) AS vies
    FROM sorteios s
    JOIN amostras a
        ON a.codigo_materia = s.codigo_materia AND a.objeto_votado = s.objeto_votado
       AND a.numero_objeto = s.numero_objeto AND a.prompt_version = s.prompt_version
       AND a.amostra = s.amostra
    GROUP BY s.replica, s.codigo_materia, s.objeto_votado, s.numero_objeto
    UNION ALL
    SELECT r.replica, m.codigo_materia, m.objeto_votado, m.numero_objeto, m.vies_publicado
    FROM replicas r CROSS JOIN objetos m
    WHERE m.n_amostras = 1
),
indices AS (
    SELECT v.replica, p.codigo_senador, avg(v.vies * p.peso) AS indice
    FROM posicoes p
    JOIN elegiveis e ON e.codigo_senador = p.codigo_senador
    JOIN vies_por_replica v ON v.codigo_materia = p.codigo_materia
                           AND v.objeto_votado = p.objeto_votado
                           AND v.numero_objeto = p.numero_objeto
    GROUP BY v.replica, p.codigo_senador
),
-- Desempate pelo código do senador: ntile sobre valores iguais precisa de ordem total para que
-- o resultado não dependa do plano de execução.
tercis AS (
    SELECT replica, codigo_senador,
           ntile(3) OVER (PARTITION BY replica ORDER BY indice DESC, codigo_senador) AS tercil
    FROM indices
),
fracoes AS (
    SELECT codigo_senador,
           CAST(count(*) AS INT) AS n_replicas,
           avg(CASE WHEN tercil = 1 THEN 1.0D ELSE 0.0D END) AS frac_pro_classe_baixa,
           avg(CASE WHEN tercil = 2 THEN 1.0D ELSE 0.0D END) AS frac_equilibrado,
           avg(CASE WHEN tercil = 3 THEN 1.0D ELSE 0.0D END) AS frac_pro_classe_alta
    FROM tercis
    GROUP BY codigo_senador
),
ordenados AS (
    SELECT f.*,
           sort_array(array(
               named_struct('frac', frac_pro_classe_baixa, 'ordem', 1, 'rotulo', 'pro_classe_baixa'),
               named_struct('frac', frac_equilibrado, 'ordem', 2, 'rotulo', 'equilibrado'),
               named_struct('frac', frac_pro_classe_alta, 'ordem', 3, 'rotulo', 'pro_classe_alta')
           ), false) AS ranking
    FROM fracoes f
)
SELECT
    codigo_senador,
    n_replicas,
    frac_pro_classe_baixa,
    frac_equilibrado,
    frac_pro_classe_alta,
    ranking[0].rotulo AS rotulo_mais_frequente,
    ranking[0].frac AS estabilidade,
    ranking[1].rotulo AS segundo_rotulo
FROM ordenados
