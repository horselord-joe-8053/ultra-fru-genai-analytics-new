
FROM apache/spark:3.5.1
USER root
# Add delta libraries via spark packages at runtime; keep image minimal here.
COPY jobs /opt/fru/jobs
# Set HOME to /tmp to avoid Ivy/Maven cache permission issues (Spark uses ~/.ivy2)
# Also set Spark-specific Ivy home and user.home property
ENV HOME=/tmp
ENV IVY_HOME=/tmp/.ivy2

# Create a user in /etc/passwd so Spark/Hadoop can resolve the name
# This prevents "javax.security.auth.login.LoginException: java.lang.NullPointerException: invalid null input: name"
RUN echo "fru:x:1001:1001:fru:/tmp:/sbin/nologin" >> /etc/passwd

# Use a numeric user that matches typical Spark environments or just stick to 1001 but ensure write access
USER 1001
