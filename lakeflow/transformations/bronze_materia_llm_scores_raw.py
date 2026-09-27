from pyspark import pipelines as dp
from pyspark.sql import functions as F

VOLUME_PATH = "/Volumes/senado_votacoes/bronze/raw_landing/materia_llm_scores_raw"


@dp.table(
    name="materia_llm_scores_raw",
    comment="Nota do LLM já interpretada, um arquivo por amostra: cada amostra de cada matéria e de cada emenda destacada pontuada (payload com as notas e justificativas do contrato congelado, prompt_version, amostra e status; as de emenda trazem também objeto_votado e numero_objeto). Escrita pelos scripts de pontuação. A resposta crua completa do modelo não entra aqui: fica no Volume, em materia_llm_scores_resposta_bruta/.",
)
def materia_llm_scores_raw():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.allowOverwrites", "true")
        .option("singleVariantColumn", "payload")
        .load(VOLUME_PATH)
        .select("payload", "_metadata.file_path")
        .withColumnRenamed("file_path", "_source_endpoint")
        .withColumn("_loaded_at", F.current_timestamp())
    )
