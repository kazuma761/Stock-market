# ST-09 · Reconcile dependency pins with the built image

**Phase:** phase-2-runtime
**Source:** architecture.md "What's actually there today" + "Stack & libraries"

## Description
`requirements.txt` pins `apache-airflow==2.8.0` while the Dockerfile builds `apache/airflow:2.9.0`, and
`requests==2.26.0` (2021) will fight Airflow 2.9's constraints. This is exactly the class of detail the
code-quality criterion catches.

## Acceptance criteria
- [ ] The `apache-airflow` pin removed from `requirements.txt` (the image supplies it)
- [ ] `requests` moved to a current release compatible with Airflow 2.9 constraints
- [ ] `psycopg2-binary` pinned and present
- [ ] Deleted-module dependencies (`pysertive`, FMP/crypto SDKs if any) removed
- [ ] Image builds clean with no pip resolver conflicts in the build log
