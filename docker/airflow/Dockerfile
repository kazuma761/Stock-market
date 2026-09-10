FROM apache/airflow:2.9.0

COPY requirements.txt .

# Install against Airflow's published constraints so added packages cannot
# silently pull in a version that breaks the pinned Airflow release.
RUN pip install --no-cache-dir -r requirements.txt \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.9.0/constraints-3.8.txt"
