
FROM apache/spark:3.5.1
# Content-based build skip: hash of build context, passed as --build-arg by build_and_push_images.py.
ARG BUILD_CONTEXT_HASH
LABEL build_context_hash=${BUILD_CONTEXT_HASH}
USER root
RUN pip install --no-cache-dir psycopg2-binary
# Add delta libraries via spark packages at runtime; keep image minimal here.
COPY analytics/jobs /opt/fru/jobs
COPY data/raw/fridge_sales_with_rating.csv /opt/fru/data/fridge_sales_with_rating.csv
RUN chmod 644 /opt/fru/data/fridge_sales_with_rating.csv
# Set HOME to /tmp to avoid Ivy/Maven cache permission issues (Spark uses ~/.ivy2)
# Also set Spark-specific Ivy home and user.home property
ENV HOME=/tmp
ENV IVY_HOME=/tmp/.ivy2

# Create a user in /etc/passwd so Spark/Hadoop can resolve the name
# This prevents "javax.security.auth.login.LoginException: java.lang.NullPointerException: invalid null input: name"
RUN echo "fru:x:1001:1001:fru:/tmp:/sbin/nologin" >> /etc/passwd

# Use a numeric user that matches typical Spark environments or just stick to 1001 but ensure write access
USER 1001
