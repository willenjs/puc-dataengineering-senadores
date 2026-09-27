from pyspark import pipelines as dp
from pyspark.sql import functions as F

VOLUME_PATH = "/Volumes/senado_votacoes/bronze/raw_landing/status_processos"


@dp.table(
    name="status_processos",
    comment="Payload bruto do status de tramitação de processos legislativos referenciados por votações (fonte: /processo/{id}), escopado às matérias efetivamente votadas.",
)
def status_processos():
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
