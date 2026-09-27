from pyspark import pipelines as dp
from pyspark.sql import functions as F

VOLUME_PATH = "/Volumes/senado_votacoes/bronze/raw_landing/votacoes"


@dp.table(
    name="votacoes_lista_anual",
    comment="Payload bruto do arquivo anual de votações, já com os votos individuais aninhados (fonte: /arquivos/ListaVotacoes{ano}.json).",
)
def votacoes_lista_anual():
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
