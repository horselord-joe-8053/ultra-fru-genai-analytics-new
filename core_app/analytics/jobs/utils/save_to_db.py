"""
Save Spark analytics results to PostgreSQL batch_analytics table.
Standalone - no backend.* dependencies. Uses os.environ for config.

Note: batch_analytics is shared by both Kube (CronJob) and Nonkube (EventBridge) Spark jobs.
In PROD only one scope is deployed; in DEV both may run. See docs/learned/cloud_shared/ANALYTICS_AND_DATA.md.
"""
import os
import json
from typing import Dict, Any, Optional


def save_analytics_to_db(
    sales_by_brand: list,
    store_performance: list,
    feedback_analysis: list,
    top_models: list,
    price_stats: Dict[str, Any],
    total_records: int,
    total_revenue: float,
    db_config: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Save analytics results to PostgreSQL batch_analytics table.
    All data is stored as JSONB.
    """
    if db_config is None:
        db_config = {
            "host": os.environ.get("PGHOST", ""),
            "port": int(os.environ.get("PGPORT", "5432")),
            "user": os.environ.get("PGUSER", "postgres"),
            "password": os.environ.get("PGPASSWORD", ""),
            "dbname": os.environ.get("PGDATABASE", "fru_db"),
        }
    if not db_config.get("host") or not db_config.get("password"):
        print("✗ PGHOST and PGPASSWORD required for save_analytics_to_db; skipping")
        return False

    try:
        import psycopg2
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO batch_analytics
            (sales_by_brand, store_performance, feedback_analysis, top_models,
             price_stats, total_records, total_revenue)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                json.dumps(sales_by_brand),
                json.dumps(store_performance),
                json.dumps(feedback_analysis),
                json.dumps(top_models),
                json.dumps(price_stats),
                total_records,
                total_revenue,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
        print("✓ Analytics saved to database")
        return True
    except Exception as e:
        print(f"✗ Error saving analytics to database: {e}")
        return False


def verify_saved_total_records(expected: int, db_config: Optional[Dict[str, Any]] = None) -> None:
    """
    ETL self-check: verify latest batch_analytics row has total_records == expected.
    Raises RuntimeError on mismatch. Replaces CloudWatch/Cloud Logging log scraping.
    """
    if db_config is None:
        db_config = {
            "host": os.environ.get("PGHOST", ""),
            "port": int(os.environ.get("PGPORT", "5432")),
            "user": os.environ.get("PGUSER", "postgres"),
            "password": os.environ.get("PGPASSWORD", ""),
            "dbname": os.environ.get("PGDATABASE", "fru_db"),
        }
    if not db_config.get("host") or not db_config.get("password"):
        raise RuntimeError("PGHOST and PGPASSWORD required for verify_saved_total_records")

    import psycopg2
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    cur.execute(
        "SELECT total_records FROM batch_analytics ORDER BY created_at DESC LIMIT 1"
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row is None:
        raise RuntimeError("No batch_analytics row found after save")
    db_total = int(row[0])
    if db_total != expected:
        raise RuntimeError(
            f"ETL self-check failed: saved total_records={db_total} != expected={expected}"
        )
