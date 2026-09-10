-- Initialises the market data database.
--
-- NOTE: Postgres runs this script ONLY when the data volume is first created.
-- To re-apply changes made here, tear the volume down: `docker compose down -v`.

-- Airflow keeps its metadata in a separate database on this same instance,
-- so the pipeline's data and the orchestrator's bookkeeping never mix.
CREATE DATABASE airflow;

CREATE SCHEMA IF NOT EXISTS market_data;

CREATE TABLE IF NOT EXISTS market_data.stocks (
    id              SERIAL PRIMARY KEY,
    date_collected  DATE NOT NULL DEFAULT CURRENT_DATE,
    symbol          VARCHAR(20) NOT NULL,
    name            VARCHAR(100) NOT NULL,
    market_cap      DECIMAL(20,2) NOT NULL,
    -- BIGINT, not INT: heavily traded tickers exceed INT's ~2.1B ceiling.
    volume          BIGINT NOT NULL,
    price           DECIMAL(10,2) NOT NULL,
    change_percent  DECIMAL(15,8) NOT NULL,

    -- One row per symbol per day. This constraint is what makes the pipeline
    -- idempotent: re-running a day updates in place instead of duplicating.
    CONSTRAINT stocks_symbol_date_key UNIQUE (symbol, date_collected)
);
