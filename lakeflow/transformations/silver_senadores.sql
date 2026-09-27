-- lakeflow/transformations/silver_senadores.sql
-- Fonte: /senador/lista/legislatura/57 (todos os titulares e suplentes da legislatura,
-- não só quem ocupa a cadeira hoje) -- ver nota em extract_senadores.py.
CREATE OR REFRESH MATERIALIZED VIEW senado_votacoes.silver.senadores (
    codigo_senador STRING COMMENT 'Identificador único do senador na API do Senado (IdentificacaoParlamentar.CodigoParlamentar).',
    nome_senador STRING COMMENT 'Nome parlamentar do senador.',
    partido STRING COMMENT 'Sigla do partido do senador no momento da extração.',
    uf STRING COMMENT 'Unidade federativa (estado) representada pelo senador.',
    url_foto STRING COMMENT 'URL da foto oficial do senador.',
    -- Mandato = 8 anos = 2 legislaturas (renovação escalonada de 1/3 ou 2/3 do Senado a
    -- cada 4 anos). PrimeiraLegislaturaDoMandato é sempre a legislatura em que o mandato
    -- começou (56ª ou 57ª); SegundaLegislaturaDoMandato é sempre a legislatura em que
    -- termina (57ª ou 58ª) -- confirmado nos 245 registros ao vivo de
    -- /senador/lista/legislatura/57 (só dois anos de término possíveis: 2027 ou 2031).
    mandato_inicio INT COMMENT 'Ano de início do mandato atual do senador (DataInicio da primeira legislatura do mandato).',
    mandato_fim INT COMMENT 'Ano de término do mandato atual do senador (DataFim da segunda legislatura do mandato).',
    CONSTRAINT codigo_senador_not_null EXPECT (codigo_senador IS NOT NULL) ON VIOLATION FAIL UPDATE,
    CONSTRAINT nome_senador_not_null EXPECT (nome_senador IS NOT NULL) ON VIOLATION FAIL UPDATE
)
COMMENT 'Um senador por linha, com os dados de identificação vigentes na extração mais recente (tipo-1, sem histórico de troca de partido).'
AS
WITH ultimo_lote AS (
    -- `_loaded_at` é avaliado por micro-batch, não por linha -- arquivos de datas
    -- diferentes recarregados juntos podem empatar. Ordena primeiro pela data
    -- embutida no caminho (dt=YYYY-MM-DD), só usando `_loaded_at` como desempate.
    SELECT payload
    FROM senado_votacoes.bronze.senadores_lista_atual
    QUALIFY row_number() OVER (
        ORDER BY split_part(_source_endpoint, 'dt=', -1) DESC, _loaded_at DESC
    ) = 1
),

parlamentares AS (
    SELECT value AS parlamentar
    FROM ultimo_lote, LATERAL variant_explode(payload:ListaParlamentarLegislatura.Parlamentares.Parlamentar) AS t
)

SELECT
    parlamentar:IdentificacaoParlamentar.CodigoParlamentar::STRING AS codigo_senador,
    parlamentar:IdentificacaoParlamentar.NomeParlamentar::STRING AS nome_senador,
    parlamentar:IdentificacaoParlamentar.SiglaPartidoParlamentar::STRING AS partido,
    parlamentar:Mandatos.Mandato[0].UfParlamentar::STRING AS uf,
    parlamentar:IdentificacaoParlamentar.UrlFotoParlamentar::STRING AS url_foto,
    year(parlamentar:Mandatos.Mandato[0].PrimeiraLegislaturaDoMandato.DataInicio::DATE) AS mandato_inicio,
    year(parlamentar:Mandatos.Mandato[0].SegundaLegislaturaDoMandato.DataFim::DATE) AS mandato_fim
FROM parlamentares
