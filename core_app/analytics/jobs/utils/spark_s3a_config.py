"""
S3A numeric config overrides for Spark/Hadoop when using Delta Lake on AWS S3.

Background
----------
Hadoop's core-default.xml defines fs.s3a.* timeout values as duration strings:
  - fs.s3a.connection.establish.timeout = "30s"
  - fs.s3a.threads.keepalivetime = "60s"

Delta Lake's LogStore (and some Hadoop code paths) parse these via Configuration.getLong()
or Integer.parseInt(), which expect numeric strings (e.g. "60000"), not "60s".
Result: NumberFormatException when Spark initializes S3A for Delta _delta_log access.

This is an ecosystem inconsistency: Hadoop evolved to support duration strings, but
not all consumers (Delta Lake, older S3A paths) were updated to use getDuration().

Scope
-----
- AWS S3A only. GCP uses fs.gs.impl (GoogleHadoopFileSystem) and does not load
  fs.s3a.* config, so GCP is unaffected.
- See docs/war_stories/WAR_STORIES_AWS.md §12 for full discussion.

Usage
-----
Call get_s3a_numeric_overrides() and apply each (key, value) to the SparkSession
builder before getOrCreate(). Values must remain numeric (milliseconds or seconds
as integers) — never use "60s" or "30s" strings.
"""

from typing import Iterator

# Establish connection timeout (ms). Hadoop default "30s" causes NumberFormatException.
S3A_CONNECTION_ESTABLISH_TIMEOUT_MS = "5000"

# Socket/connection timeout (ms). 60s = 60000ms.
S3A_CONNECTION_TIMEOUT_MS = "60000"

# Thread pool keepalive (seconds, integer). Hadoop default "60s" causes NumberFormatException.
S3A_THREADS_KEEPALIVETIME_SEC = "60"

# Multipart purge age (seconds). Hadoop default "24h" causes NumberFormatException.
S3A_MULTIPART_PURGE_AGE_SEC = "86400"

# Multipart uploads expiration (seconds). May be duration string in some Hadoop versions.
S3A_MULTIPART_UPLOADS_EXPIRATION_SEC = "86400"

# Connection pool and retry (legacy parity; avoids any duration-string defaults).
S3A_CONNECTION_MAXIMUM = "15"
S3A_ATTEMPTS_MAXIMUM = "3"
S3A_RETRY_INTERVAL_MS = "1000"
S3A_THREADS_MAX = "10"
S3A_THREADS_CORE = "5"
S3A_FAST_UPLOAD = "true"
S3A_BLOCK_SIZE = "134217728"


def get_s3a_numeric_overrides() -> Iterator[tuple[str, str]]:
    """
    Yield (spark.hadoop.fs.s3a.*, value) pairs to override Hadoop's duration-string defaults.

    Apply these to SparkSession.builder before getOrCreate() when using S3A (AWS).
    All values are numeric strings; Hadoop/Delta parsers expect numbers, not "60s".
    """
    yield ("spark.hadoop.fs.s3a.connection.establish.timeout", S3A_CONNECTION_ESTABLISH_TIMEOUT_MS)
    yield ("spark.hadoop.fs.s3a.connection.timeout", S3A_CONNECTION_TIMEOUT_MS)
    yield ("spark.hadoop.fs.s3a.threads.keepalivetime", S3A_THREADS_KEEPALIVETIME_SEC)
    yield ("spark.hadoop.fs.s3a.multipart.purge.age", S3A_MULTIPART_PURGE_AGE_SEC)
    yield ("spark.hadoop.fs.s3a.multipart.uploads.expiration", S3A_MULTIPART_UPLOADS_EXPIRATION_SEC)
    yield ("spark.hadoop.fs.s3a.connection.maximum", S3A_CONNECTION_MAXIMUM)
    yield ("spark.hadoop.fs.s3a.attempts.maximum", S3A_ATTEMPTS_MAXIMUM)
    yield ("spark.hadoop.fs.s3a.retry.interval", S3A_RETRY_INTERVAL_MS)
    yield ("spark.hadoop.fs.s3a.threads.max", S3A_THREADS_MAX)
    yield ("spark.hadoop.fs.s3a.threads.core", S3A_THREADS_CORE)
    yield ("spark.hadoop.fs.s3a.fast.upload", S3A_FAST_UPLOAD)
    yield ("spark.hadoop.fs.s3a.block.size", S3A_BLOCK_SIZE)
