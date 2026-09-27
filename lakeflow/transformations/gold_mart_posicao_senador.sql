-- lakeflow/transformations/gold_mart_posicao_senador.sql
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.gold.mart_posicao_senador (
    codigo_senador STRING NOT NULL COMMENT 'FK para dim_senador.',
    codigo_materia STRING NOT NULL COMMENT 'FK para dim_materia.',
    objeto_votado STRING NOT NULL COMMENT 'Objeto sobre o qual esta posição se manifesta (fact_votacao.objeto_votado): "texto" (o texto da matéria) ou "emenda" (emenda destacada), os dois objetos que têm nota. Artigos destacados e requerimentos ficam fora.',
    numero_objeto STRING NOT NULL COMMENT 'Número do objeto votado: "texto" para o texto da matéria, o número da emenda destacada ("157") para a emenda. Entra na chave porque uma matéria pode ter três emendas destacadas, cada uma com a sua votação e a sua nota.',
    codigo_votacao STRING NOT NULL COMMENT 'FK para fact_votacao -- a votação que determinou esta posição (a mais recente entre as que decidiram este objeto).',
    voto STRING NOT NULL COMMENT 'Posição definitiva do senador sobre este objeto (Sim/Não/Abstenção/Secreto/Ausente). Secreto = votação secreta: o senador votou mas o sentido não é público, então essa posição não tem direção e as marts que usam o sentido do voto a descartam.',
    CONSTRAINT pk_mart_posicao_senador PRIMARY KEY (codigo_senador, codigo_materia, objeto_votado, numero_objeto),
    CONSTRAINT fk_mart_posicao_senador FOREIGN KEY (codigo_senador) REFERENCES senado_votacoes.gold.dim_senador(codigo_senador),
    CONSTRAINT fk_mart_posicao_materia FOREIGN KEY (codigo_materia) REFERENCES senado_votacoes.gold.dim_materia(codigo_materia),
    CONSTRAINT fk_mart_posicao_votacao FOREIGN KEY (codigo_votacao) REFERENCES senado_votacoes.gold.fact_votacao(codigo_votacao)
)
COMMENT 'Posição definitiva de cada senador sobre cada OBJETO votado, não sobre a matéria como um todo. Até 2026-09-16 a posição era a votação mais recente da matéria, qualquer que fosse o objeto: em 29 das 111 matérias isso era um destaque, e o índice multiplicava a nota da matéria inteira pelo sinal de um voto sobre outro objeto (na PLP 210/2024, um "Não" à Emenda 20 destacada, que suprimia parte do ajuste fiscal, era lido como voto contra o pacote). Entram as votações do texto e das emendas destacadas, os dois objetos com nota própria; cada emenda é um objeto separado, identificado por numero_objeto. Artigos destacados ficam fora, sem nota, e emendas sem número ou sem nota também. Requerimentos (adiamento, preferência, urgência) ficam fora em definitivo -- decidir quando votar não tem conteúdo distributivo. Só inclui matérias com dim_processo.materia_concluida = true: sem essa garantia, a "mais recente de hoje" pode não ser a última. 1º e 2º turno de PEC são o mesmo objeto, então continuam contando uma vez. Base das marts de alinhamento e destaque.'
AS
WITH candidatas AS (
    SELECT
        v.codigo_senador,
        fv.codigo_materia,
        fv.objeto_votado,
        fv.numero_objeto,
        v.codigo_votacao,
        v.voto,
        fv.data_votacao,
        fv.sequencial_sessao
    FROM senado_votacoes.gold.fact_voto_senador v
    JOIN senado_votacoes.gold.fact_votacao fv ON fv.codigo_votacao = v.codigo_votacao
    JOIN senado_votacoes.gold.dim_materia m ON m.codigo_materia = fv.codigo_materia
    JOIN senado_votacoes.gold.dim_processo p ON p.id_processo = m.id_processo
    -- Declara o que aceita, não o que exclui: um objeto novo (ou não classificado)
    -- fica de fora por padrão, mesma regra de allowlist de materia_substantiva.
    WHERE p.materia_concluida = true
      -- Texto e emenda destacada: os dois objetos que têm nota própria hoje. O artigo
      -- destacado continua fora, sem nota. `numero_objeto` NULL é destaque que a descrição não
      -- numera (a subemenda da PLP 175/2024), e fica fora pela mesma regra de allowlist.
      AND fv.objeto_votado IN ('texto', 'emenda')
      AND fv.numero_objeto IS NOT NULL
)
SELECT codigo_senador, codigo_materia, objeto_votado, numero_objeto, codigo_votacao, voto
FROM candidatas
QUALIFY row_number() OVER (
    PARTITION BY codigo_senador, codigo_materia, objeto_votado, numero_objeto
    ORDER BY data_votacao DESC, sequencial_sessao DESC NULLS LAST
) = 1
