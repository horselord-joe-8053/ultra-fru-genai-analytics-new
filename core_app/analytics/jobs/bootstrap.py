from pyspark.sql import SparkSession
import sys
import os

# Bootstrap runs from /opt/fru/jobs; utils is sibling
_JOBS_DIR = os.path.dirname(os.path.abspath(__file__))
_UTILS_DIR = os.path.join(_JOBS_DIR, "utils")
if _UTILS_DIR not in sys.path:
    sys.path.insert(0, _UTILS_DIR)

try:
    from tools.cloud_shared.logging import logger
except ImportError:
    try:
        from analytics_logger import info, success, step
        logger = type("logger", (), {"info": staticmethod(lambda m: info(m)), "success": staticmethod(lambda m: success(m)), "step": staticmethod(lambda m: step(m))})()
    except ImportError:
        class logger:
            @staticmethod
            def info(m): print(f"[INFO] {m}", flush=True)
            @staticmethod
            def success(m): print(f"[SUCCESS] {m}", flush=True)
            @staticmethod
            def step(m): print(f"\n[STEP] {m}", flush=True)

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
