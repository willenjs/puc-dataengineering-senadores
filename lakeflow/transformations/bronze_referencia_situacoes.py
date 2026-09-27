from pyspark import pipelines as dp
from pyspark.sql import functions as F

VOLUME_PATH = "/Volumes/senado_votacoes/bronze/raw_landing/referencia_situacoes"


@dp.table(
    name="referencia_situacoes",
    comment="Payload bruto da lista de referência de situações de tramitação (fonte: /processo/tipos-situacao) -- domínio controlado, buscado por inteiro a cada execução.",
)
def referencia_situacoes():
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
