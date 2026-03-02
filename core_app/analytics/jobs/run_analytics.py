"""
Run batch analytics on Delta table and save to PostgreSQL batch_analytics.
Used by both bootstrap (one-off) and periodic (scheduled) jobs.
Creates fru_sales Delta table from CSV if missing; fails if no CSV source is available (legacy-consistent).
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, sum, avg, min, max, when, date_format, lit
import os
import sys

# Path for utils (save_to_db)
_JOBS_DIR = os.path.dirname(os.path.abspath(__file__))
_UTILS_DIR = os.path.join(_JOBS_DIR, "utils")
if _UTILS_DIR not in sys.path:
    sys.path.insert(0, _UTILS_DIR)

try:
    from save_to_db import save_analytics_to_db
except ImportError:
    save_analytics_to_db = None


def _to_spark_path(path: str) -> str:
    return path.replace("s3://", "s3a://", 1) if path.startswith("s3://") else path


def _s3_csv_path_from_delta(delta_path: str) -> str:
    """Derive S3 raw CSV path from Delta path (legacy: s3a://bucket/raw/fridge_sales_with_rating.csv)."""
    # s3a://bucket/delta/fru_sales -> s3a://bucket/raw/fridge_sales_with_rating.csv
    p = _to_spark_path(delta_path)
    if "/delta/" in p or "/delta" in p:
        base = p.split("/delta")[0]
        return f"{base}/raw/fridge_sales_with_rating.csv"
    return ""

def _ensure_fru_sales_exists(spark: SparkSession, delta_path: str) -> str:
    """Create fru_sales Delta table if missing. Loads from bundled CSV or S3 CSV. Fails if no CSV source available."""
    path = _to_spark_path(delta_path)
    existing_count = 0
    try:
        df = spark.read.format("delta").load(path)
        existing_count = df.count()
        if existing_count > 10:  # Full dataset already loaded
            print(f"✓ Delta table exists at {path} ({existing_count} rows)")
            return path
        # Few rows = incomplete; try to upgrade from CSV
        print(f"Delta exists with {existing_count} rows; attempting upgrade from CSV...")
    except Exception:
        print("No Delta table found; will create from CSV")

    # Try CSV sources: bundled first (no S3 creds needed), then S3, then local dev paths
    # Bundled in container: /opt/fru/data/fridge_sales_with_rating.csv (Dockerfile COPY)
    _jobs_dir = os.path.dirname(os.path.abspath(__file__))
    csv_paths = [
        "/opt/fru/data/fridge_sales_with_rating.csv",  # Bundled in Spark image - always works in ECS
        os.path.join(_jobs_dir, "..", "..", "data", "raw", "fridge_sales_with_rating.csv"),
        os.path.join(_jobs_dir, "..", "..", "data", "fridge_sales_with_rating.csv"),
    ]
    s3_csv = _s3_csv_path_from_delta(delta_path)
    if s3_csv:
        csv_paths.insert(1, s3_csv)  # S3 as fallback (deploy uploads; needs ContainerCredentialsProvider)
    bundled = "/opt/fru/data/fridge_sales_with_rating.csv"
    print(f"Bundled CSV exists: {os.path.exists(bundled)}, size={os.path.getsize(bundled) if os.path.exists(bundled) else 0}")
    print(f"Trying CSV sources in order: {csv_paths}")
    for csv_path in csv_paths:
        can_read = False
        spark_path = csv_path
        if csv_path.startswith("s3") or csv_path.startswith("s3a"):
            can_read = True  # Try Spark read (will fail if missing)
        elif os.path.exists(csv_path):
            can_read = True
            # Use file:// for local paths so Spark reads from container filesystem (ECS/Fargate)
            if not csv_path.startswith("file://"):
                spark_path = "file://" + csv_path
        if can_read:
            try:
                print(f"Creating fru_sales from CSV at {spark_path}...")
                df = (
                    spark.read.option("header", "true")
                    .option("inferSchema", "true")
                    .csv(spark_path)
                )
                row_count = df.count()
                if row_count < 10:
                    continue  # Skip tiny files, try next source
                # Normalize column names (legacy ingest_delta: ID -> id)
                if "ID" in df.columns:
                    df = df.withColumnRenamed("ID", "id")
                df.write.format("delta").mode("overwrite").save(path)
                print(f"✓ Created fru_sales from CSV ({row_count} rows) at {path}")
                return path
            except Exception as ex:
                import traceback
                print(f"  CSV read failed for {csv_path}: {ex}")
                traceback.print_exc()
                continue

    raise RuntimeError(
        "No CSV source available to create fru_sales Delta table. "
        "Ensure CSV exists at bundled path /opt/fru/data/fridge_sales_with_rating.csv, "
        "S3 raw/ path, or run deploy to upload CSV before bootstrap."
    )


def main(delta_path: str = None, output_dir: str = None):
    delta_path = delta_path or os.environ.get("DELTA_TABLE_PATH", "")
    if not delta_path:
        extra = os.environ.get("SPARK_EXTRA_CONF", "")
        if "spark.fru.delta_root=" in extra:
            delta_root = extra.split("spark.fru.delta_root=")[-1].split()[0].rstrip(",")
        else:
            delta_root = "s3a://example/delta"
        delta_path = f"{delta_root.rstrip('/')}/fru_sales"

    spark_compute_limit = int(os.environ.get("NUM_FOR_BATCH_ANALYTICS_TOP_SPARK_COMPUTE", "20"))

    builder = (
        SparkSession.builder.appName("fru-batch-analytics")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    )
    cloud_provider = os.environ.get("CLOUD_PROVIDER", "").lower()
    if cloud_provider == "gcp":
        # GCS connector: use Application Default Credentials (Cloud Run workload identity)
        builder = builder.config("spark.hadoop.fs.gs.impl", "com.google.cloud.hadoop.fs.gcs.GoogleHadoopFileSystem")
        builder = builder.config("spark.hadoop.fs.AbstractFileSystem.gs.impl", "com.google.cloud.hadoop.fs.gcs.GoogleHadoopFS")
    else:
        # S3 access: ECS Fargate uses container metadata (no EC2 instance metadata)
        aws_region = os.environ.get("CLOUD_REGION") or "us-east-1"
        builder = builder.config("spark.hadoop.fs.s3a.endpoint.region", aws_region)
        builder = builder.config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "com.amazonaws.auth.ContainerCredentialsProvider,com.amazonaws.auth.DefaultAWSCredentialsProviderChain",
        )
    spark = builder.getOrCreate()

    path = _ensure_fru_sales_exists(spark, delta_path)
    df = spark.read.format("delta").load(path)

    print("=" * 80)
    print("FRU Batch Analytics Report")
    print("=" * 80)
    print(f"\nTotal records: {df.count()}")

    # Handle missing columns gracefully
    cols = [c.upper() for c in df.columns]
    has_brand = "BRAND" in cols
    has_price = "PRICE" in cols
    has_store = "STORE_NAME" in cols
    has_feedback = "FEEDBACK_SENTIMENT_CATEGORY" in cols
    has_model = "FRIDGE_MODEL" in cols
    has_date = "SALES_DATE" in cols

    if not has_brand:
        df = df.withColumn("BRAND", lit("Unknown"))
    if not has_price:
        df = df.withColumn("PRICE", lit(0.0))
    if not has_store:
        df = df.withColumn("STORE_NAME", lit("Unknown"))
    if not has_feedback:
        df = df.withColumn("FEEDBACK_SENTIMENT_CATEGORY", lit("Neutral"))
    if not has_model:
        df = df.withColumn("FRIDGE_MODEL", lit("Unknown"))

    sales_by_brand = (
        df.groupBy("BRAND")
        .agg(
            count("*").alias("total_sales"),
            sum("PRICE").alias("total_revenue"),
            avg("PRICE").alias("avg_price"),
            min("PRICE").alias("min_price"),
            max("PRICE").alias("max_price")
        )
        .orderBy(col("total_sales").desc())
        .limit(spark_compute_limit)
    )

    store_performance = (
        df.groupBy("STORE_NAME")
        .agg(
            count("*").alias("total_sales"),
            sum("PRICE").alias("total_revenue"),
            avg("PRICE").alias("avg_sale_price"),
            count(when(col("FEEDBACK_SENTIMENT_CATEGORY") == "Negative", 1)).alias("negative_feedback_count"),
            count(when(col("FEEDBACK_SENTIMENT_CATEGORY") == "Positive", 1)).alias("positive_feedback_count")
        )
        .withColumn("negative_feedback_rate", (col("negative_feedback_count") / col("total_sales") * 100).cast("decimal(5,2)"))
        .orderBy(col("total_revenue").desc())
        .limit(spark_compute_limit)
    )

    feedback_by_brand = (
        df.groupBy("BRAND", "FEEDBACK_SENTIMENT_CATEGORY")
        .agg(count("*").alias("count"))
        .orderBy("BRAND", col("count").desc())
    )

    top_models = (
        df.groupBy("BRAND", "FRIDGE_MODEL")
        .agg(
            count("*").alias("sales_count"),
            sum("PRICE").alias("total_revenue"),
            avg("PRICE").alias("avg_price")
        )
        .orderBy(col("sales_count").desc())
        .limit(spark_compute_limit)
    )

    price_stats_row = df.agg(
        avg("PRICE").alias("mean_price"),
        min("PRICE").alias("min_price"),
        max("PRICE").alias("max_price")
    ).collect()[0]

    total_records = df.count()
    total_revenue = float(df.agg(sum("PRICE").alias("total")).collect()[0]["total"] or 0.0)

    sales_by_brand_list = [
        {
            "brand": row["BRAND"],
            "total_sales": int(row["total_sales"]),
            "total_revenue": float(row["total_revenue"]) if row["total_revenue"] else 0.0,
            "avg_price": float(row["avg_price"]) if row["avg_price"] else 0.0,
            "min_price": float(row["min_price"]) if row["min_price"] else 0.0,
            "max_price": float(row["max_price"]) if row["max_price"] else 0.0,
        }
        for row in sales_by_brand.collect()
    ]

    store_performance_list = [
        {
            "store_name": row["STORE_NAME"],
            "total_sales": int(row["total_sales"]),
            "total_revenue": float(row["total_revenue"]) if row["total_revenue"] else 0.0,
            "avg_sale_price": float(row["avg_sale_price"]) if row["avg_sale_price"] else 0.0,
            "negative_feedback_count": int(row["negative_feedback_count"]),
            "positive_feedback_count": int(row["positive_feedback_count"]),
            "negative_feedback_rate": float(row["negative_feedback_rate"]) if row["negative_feedback_rate"] else 0.0,
        }
        for row in store_performance.collect()
    ]

    feedback_analysis_list = [
        {"brand": row["BRAND"], "feedback_sentiment_category": row["FEEDBACK_SENTIMENT_CATEGORY"], "count": int(row["count"])}
        for row in feedback_by_brand.collect()
    ]

    top_models_list = [
        {
            "brand": row["BRAND"],
            "fridge_model": row["FRIDGE_MODEL"],
            "sales_count": int(row["sales_count"]),
            "total_revenue": float(row["total_revenue"]) if row["total_revenue"] else 0.0,
            "avg_price": float(row["avg_price"]) if row["avg_price"] else 0.0,
        }
        for row in top_models.collect()
    ]

    price_stats_dict = {
        "mean_price": float(price_stats_row["mean_price"]) if price_stats_row["mean_price"] else 0.0,
        "min_price": float(price_stats_row["min_price"]) if price_stats_row["min_price"] else 0.0,
        "max_price": float(price_stats_row["max_price"]) if price_stats_row["max_price"] else 0.0,
    }

    if save_analytics_to_db:
        save_analytics_to_db(
            sales_by_brand=sales_by_brand_list,
            store_performance=store_performance_list,
            feedback_analysis=feedback_analysis_list,
            top_models=top_models_list,
            price_stats=price_stats_dict,
            total_records=total_records,
            total_revenue=total_revenue,
        )
    else:
        print("Warning: save_analytics_to_db not available")

    print("fru bootstrap success")
    spark.stop()


if __name__ == "__main__":
    delta_path = sys.argv[1] if len(sys.argv) > 1 else None
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    main(delta_path, output_dir)
