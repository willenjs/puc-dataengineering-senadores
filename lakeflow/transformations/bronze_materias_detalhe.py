from pyspark import pipelines as dp
from pyspark.sql import functions as F

VOLUME_PATH = "/Volumes/senado_votacoes/bronze/raw_landing/materias_detalhe"


@dp.table(
    name="materias_detalhe",
    comment="Payload bruto do detalhe individual de matérias referenciadas por votações mas ausentes da busca por ano (fonte: /materia/{codigo}).",
)
def materias_detalhe():
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
