# Pinned to the python3.11 variant on purpose. The default `apache/airflow:2.9.0`
# tag ships Python 3.8, where PEP 585 builtin generics (`dict[str, str]` in a
# signature) raise TypeError at import time — the DAG would fail to parse inside
# the container while passing every test on a modern local interpreter.
# This also matches the Python version CI installs.
FROM apache/airflow:2.9.0-python3.11

COPY requirements.txt .

# Install against Airflow's published constraints so added packages cannot
# silently pull in a version that breaks the pinned Airflow release.
RUN pip install --no-cache-dir -r requirements.txt \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.9.0/constraints-3.11.txt"
