# Plataforma (Etapa 3)

O pipeline roda no Databricks. A experiência prévia era com Snowflake, que poderia ter sido o caminho, e de fato a primeira versão do projeto usava Snowflake, dbt e S3. A troca foi feita porque o projeto era uma boa oportunidade de aprender Databricks e porque simplificava a arquitetura.

Hoje tudo fica em um só lugar. O Unity Catalog guarda o catálogo `senado_votacoes` com as camadas Bronze, Silver e Gold, e um Volume gerenciado recebe os JSONs extraídos da API do Senado. O Auto Loader ingere esses arquivos, o Lakeflow declara as transformações como materialized views (`CREATE OR REFRESH MATERIALIZED VIEW`), e um único Job, definido por um Databricks Asset Bundle ([`databricks.yml`](../databricks.yml) e [`resources/jobs.yml`](../resources/jobs.yml)), orquestra as etapas de extração, pontuação e atualização. Com isso saíram o bucket S3, o dbt e o orquestrador separado.
