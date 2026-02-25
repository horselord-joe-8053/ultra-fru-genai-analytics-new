"""
Save Spark analytics results to PostgreSQL batch_analytics table.
Standalone - no backend.* dependencies. Uses os.environ for config.

Note: batch_analytics is shared by both Kube (CronJob) and Nonkube (EventBridge) Spark jobs.
In PROD only one scope is deployed; in DEV both may run. See docs/learned/ANALYTICS_KUBE_NONKUBE_SHARED_DATA.md.
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
