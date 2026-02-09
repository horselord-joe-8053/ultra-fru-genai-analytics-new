
from pyspark.sql import SparkSession

def main():
    spark = SparkSession.builder.appName("fru-bootstrap").getOrCreate()
    df = spark.range(0, 100).withColumnRenamed("id", "x")
    # The storage URI is injected via env var at runtime (S3 or GCS).
    delta_root = spark.conf.get("spark.fru.delta_root", "s3a://example/delta")
    out = f"{delta_root}/gold/bootstrap_metrics"
    df.write.format("delta").mode("overwrite").save(out)
    spark.stop()

if __name__ == "__main__":
    main()
