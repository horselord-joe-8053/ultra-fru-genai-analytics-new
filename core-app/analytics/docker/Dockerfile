
FROM bitnami/spark:3.5
USER root
# Add delta libraries via spark packages at runtime; keep image minimal here.
COPY jobs /opt/fru/jobs
USER 1001
