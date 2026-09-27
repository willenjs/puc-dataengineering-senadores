-- sql/databricks_bootstrap.sql
-- Setup único do Unity Catalog para o projeto.
-- Storage 100% gerenciado pelo Databricks Free Edition: sem IAM Role, Storage
-- Credential ou External Location.

CREATE CATALOG IF NOT EXISTS senado_votacoes;

CREATE SCHEMA IF NOT EXISTS senado_votacoes.bronze;
CREATE SCHEMA IF NOT EXISTS senado_votacoes.silver;
CREATE SCHEMA IF NOT EXISTS senado_votacoes.gold;

-- Volume managed: sem EXTERNAL, sem LOCATION -- o Unity Catalog provisiona e
-- gerencia o storage por baixo. Aparece montado como /Volumes/senado_votacoes/bronze/raw_landing.
CREATE VOLUME IF NOT EXISTS senado_votacoes.bronze.raw_landing;

-- ===========================================================================
-- Setup de credenciais (uma vez, via CLI, fora deste SQL -- rode no seu terminal):
--
--   databricks secrets create-scope senado-votacoes
--   databricks tokens create --comment "senado-votacoes-job" --lifetime-seconds 7776000 -o json
--   -- (copie o token_value do JSON retornado, depois:)
--   databricks secrets put-secret --json '{"scope": "senado-votacoes", "key": "databricks-token", "string_value": "<token>"}'
--   databricks secrets put-secret --json '{"scope": "senado-votacoes", "key": "anthropic-api-key", "string_value": "<sua-chave>"}'
--   -- opcional, só se sua chave Anthropic for do tipo "identity-linked":
--   databricks secrets put-secret --json '{"scope": "senado-votacoes", "key": "anthropic-workspace-id", "string_value": "<workspace-id>"}'
--
-- Os 3 scripts Python do Job (gap-fill, scoring, dicionário de dados) leem essas
-- credenciais via `senado_pipeline.databricks_auth.obter_secret()`.
-- ===========================================================================
