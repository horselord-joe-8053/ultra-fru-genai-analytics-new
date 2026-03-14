"""
Run batch analytics on Delta table and save to PostgreSQL batch_analytics.
Used by bootstrap (one-off), CronJob/EventBridge (scheduled), and local scheduler.
Reads raw data from fru_sales_raw (PostgreSQL) via psycopg2; creates/refreshes Delta from it.
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, sum, avg, min, max, when, lit
import os
import sys

# Path for utils (save_to_db)
_JOBS_DIR = os.path.dirname(os.path.abspath(__file__))
_UTILS_DIR = os.path.join(_JOBS_DIR, "utils")
if _UTILS_DIR not in sys.path:
    sys.path.insert(0, _UTILS_DIR)

try:
    from save_to_db import save_analytics_to_db, verify_saved_total_records
except ImportError:
    save_analytics_to_db = None
    verify_saved_total_records = None

try:
    from spark_s3a_config import get_s3a_numeric_overrides
except ImportError:
    get_s3a_numeric_overrides = None

try:
    from analytics_logger import info as log_info, success as log_success, warning as log_warning, error as log_error, step as log_step
except ImportError:
    def _log(level: str):
        def _f(msg: str):
            print(f"[{level}] {msg}", flush=True)
        return _f
    log_info = _log("INFO")
    log_success = _log("SUCCESS")
    log_warning = _log("WARNING")
    log_error = _log("ERROR")
    log_step = _log("STEP")


def _to_spark_path(path: str) -> str:
    return path.replace("s3://", "s3a://", 1) if path.startswith("s3://") else path


def _read_raw_from_postgres():
    """Read fru_sales_raw from PostgreSQL via psycopg2. Returns list of dicts with uppercase keys.
    Retries connection a few times to tolerate Docker network / postgres startup delay."""
    import time
    import psycopg2
    from psycopg2.extras import RealDictCursor

    host = os.environ.get("PGHOST", "")
    port = int(os.environ.get("PGPORT", "5432"))
    user = os.environ.get("PGUSER", "postgres")
    password = os.environ.get("PGPASSWORD", "")
    dbname = os.environ.get("PGDATABASE", "fru_db")
    last_err = None
    for attempt in range(1, 6):
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                dbname=dbname,
                connect_timeout=30,
            )
            break
        except Exception as e:
            last_err = e
            if attempt < 5:
                log_warning(f"PostgreSQL connection attempt {attempt}/5 failed: {e}. Retrying in 5s...")
                time.sleep(5)
            else:
                raise
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, customer_id, brand, fridge_model, capacity_liters, price, sales_date, "
                "store_name, store_address, customer_feedback, feedback_rating, feedback_sentiment_category "
                "FROM fru_sales_raw"
            )
            rows = cur.fetchall()
        # Map to uppercase keys for Spark (matches legacy CSV column names)
        return [
            {
                "ID": r["id"],
                "CUSTOMER_ID": r.get("customer_id") or "",
                "BRAND": r["brand"] or "Unknown",
                "FRIDGE_MODEL": r["fridge_model"] or "Unknown",
                "CAPACITY_LITERS": r.get("capacity_liters"),
                "PRICE": float(r["price"]) if r["price"] is not None else 0.0,
                "SALES_DATE": r["sales_date"],
                "STORE_NAME": r["store_name"] or "Unknown",
                "STORE_ADDRESS": r.get("store_address") or "",
                "CUSTOMER_FEEDBACK": r.get("customer_feedback") or "",
                "FEEDBACK_RATING": r.get("feedback_rating"),
                "FEEDBACK_SENTIMENT_CATEGORY": r.get("feedback_sentiment_category") or "Neutral",
            }
            for r in rows
        ]
    finally:
        conn.close()


def _ensure_fru_sales_exists(spark: SparkSession, delta_path: str) -> str:
    """Create/refresh fru_sales Delta table from fru_sales_raw (PostgreSQL)."""
    path = _to_spark_path(delta_path)

    # Check if we have DB credentials
    if not os.environ.get("PGHOST") or not os.environ.get("PGPASSWORD"):
        raise RuntimeError(
            "PGHOST and PGPASSWORD required for Spark to read fru_sales_raw. "
            "Ensure these are set in the CronJob/ECS task environment."
        )

    log_info("Reading fru_sales_raw from PostgreSQL...")
    rows = _read_raw_from_postgres()
    if len(rows) < 10:
        raise RuntimeError(
            f"fru_sales_raw has only {len(rows)} rows. "
            "Run database setup (load_raw_from_csv) first to populate fru_sales_raw."
        )

    df = spark.createDataFrame(rows)
    if "ID" in df.columns:
        df = df.withColumnRenamed("ID", "id")
    df.write.format("delta").mode("overwrite").save(path)
    log_success(f"Created fru_sales from fru_sales_raw ({len(rows)} rows) at {path}")
    return path


def main(delta_path: str = None, output_dir: str = None):
    log_step("FRU Batch Analytics START")
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
        # AWS S3: ECS Fargate uses container metadata (no EC2 instance metadata).
        # Apply S3A numeric overrides: Hadoop core-default.xml uses "60s"/"30s" duration strings,
        # but Delta Lake's LogStore expects numeric values → NumberFormatException without overrides.
        # Single source of truth: spark_s3a_config.get_s3a_numeric_overrides(). See WAR_STORIES_AWS.md §12.
        aws_region = os.environ.get("CLOUD_REGION") or "us-east-1"
        builder = builder.config("spark.hadoop.fs.s3a.endpoint.region", aws_region)
        builder = builder.config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "com.amazonaws.auth.ContainerCredentialsProvider,com.amazonaws.auth.DefaultAWSCredentialsProviderChain",
        )
        if get_s3a_numeric_overrides:
            for key, val in get_s3a_numeric_overrides():
                builder = builder.config(key, val)
    spark = builder.getOrCreate()

    path = _ensure_fru_sales_exists(spark, delta_path)
    df = spark.read.format("delta").load(path)

    log_step("FRU Batch Analytics")
    total_records_count = df.count()
    log_info(f"Total records: {total_records_count}")

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

    total_records = total_records_count
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

    log_info("Saving analytics to database...")
    if save_analytics_to_db:
        deploy_scope = os.environ.get("DEPLOY_SCOPE", "")
        ok = save_analytics_to_db(
            sales_by_brand=sales_by_brand_list,
            store_performance=store_performance_list,
            feedback_analysis=feedback_analysis_list,
            top_models=top_models_list,
            price_stats=price_stats_dict,
            total_records=total_records,
            total_revenue=total_revenue,
            deploy_scope=deploy_scope or None,
        )
        # ETL self-check: assert DB save matches computed total (replaces log-based verification)
        if ok and verify_saved_total_records:
            verify_saved_total_records(total_records)
    else:
        log_warning("save_analytics_to_db not available; skipping DB write")

    log_success("fru bootstrap success")
    spark.stop()


if __name__ == "__main__":
    delta_path = sys.argv[1] if len(sys.argv) > 1 else None
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    main(delta_path, output_dir)
