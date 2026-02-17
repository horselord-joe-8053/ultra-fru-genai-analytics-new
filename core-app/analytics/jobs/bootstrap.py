from pyspark.sql import SparkSession

# Note: tools.common.logging is in /app/tools/ inside the container
try:
    from tools.common.logging import logger
except ImportError:
    # Fallback if not in container or structured differently
    class logger:
        @staticmethod
        def info(m): print(f"[INFO] {m}")
        @staticmethod
        def success(m): print(f"[SUCCESS] {m}")
        @staticmethod
        def step(m): print(f"\n[STEP] {m}")

def main():
    logger.step("FRU BOOTSTRAP START")
    spark = SparkSession.builder.appName("fru-bootstrap").getOrCreate()
    logger.info(f"Spark version: {spark.version}")
    
    df = spark.range(0, 100).withColumnRenamed("id", "x")
    # The storage URI is injected via env var at runtime (S3 or GCS).
    delta_root = spark.conf.get("spark.fru.delta_root", "s3a://example/delta")
    logger.info(f"Writing bootstrap data to: {delta_root}")
    
    out = f"{delta_root}/gold/bootstrap_metrics"
    df.write.format("delta").mode("overwrite").save(out)
    
    logger.success("FRU BOOTSTRAP SUCCESS")
    spark.stop()

if __name__ == "__main__":
    main()
