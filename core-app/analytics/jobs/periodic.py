
from pyspark.sql import SparkSession

def main():
    spark = SparkSession.builder.appName("fru-periodic").getOrCreate()
    delta_root = spark.conf.get("spark.fru.delta_root", "s3a://example/delta")
    path = f"{delta_root}/gold/bootstrap_metrics"
    df = spark.read.format("delta").load(path)
    df.groupBy().count().show()
    spark.stop()

if __name__ == "__main__":
    main()
