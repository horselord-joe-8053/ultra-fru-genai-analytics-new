
FROM spark:4.0.1-scala2.13-java21-python3-ubuntu
# Content-based build skip: hash of build context, passed as --build-arg by build_and_push_images.py.
ARG BUILD_CONTEXT_HASH
LABEL build_context_hash=${BUILD_CONTEXT_HASH}
USER root
RUN pip install --no-cache-dir psycopg2-binary
# Add delta libraries via spark packages at runtime; keep image minimal here.
COPY analytics/jobs /opt/fru/jobs
# GCS connector (shaded jar avoids Guava conflicts with Spark 3.5)
RUN mkdir -p /opt/fru/jars && curl -sL -o /opt/fru/jars/gcs-connector-hadoop3-2.2.7-shaded.jar \
    https://repo1.maven.org/maven2/com/google/cloud/bigdataoss/gcs-connector/hadoop3-2.2.7/gcs-connector-hadoop3-2.2.7-shaded.jar \
    && chmod 644 /opt/fru/jars/gcs-connector-hadoop3-2.2.7-shaded.jar
# Set HOME to /tmp to avoid Ivy/Maven cache permission issues (Spark uses ~/.ivy2)
# Also set Spark-specific Ivy home and user.home property
ENV HOME=/tmp
ENV IVY_HOME=/tmp/.ivy2

# Create a user in /etc/passwd so Spark/Hadoop can resolve the name
# This prevents "javax.security.auth.login.LoginException: java.lang.NullPointerException: invalid null input: name"
RUN echo "fru:x:1001:1001:fru:/tmp:/sbin/nologin" >> /etc/passwd

# Use a numeric user that matches typical Spark environments or just stick to 1001 but ensure write access
USER 1001
