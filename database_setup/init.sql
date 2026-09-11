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

    -- Identity -------------------------------------------------------------
    symbol          VARCHAR(20)  NOT NULL,
    name            VARCHAR(100) NOT NULL,

    -- The trading session this row describes, from the API's "latest trading
    -- day". NOT the day we happened to run: a weekend run reports Friday's
    -- session, and keying on the run date would store that same session twice
    -- under two different dates.
    trading_day     DATE NOT NULL,

    -- Price action ---------------------------------------------------------
    -- 4 decimal places because that is what the API returns; rounding to 2
    -- would discard precision we were given for free.
    price           DECIMAL(12,4) NOT NULL,
    open_price      DECIMAL(12,4),
    high_price      DECIMAL(12,4),
    low_price       DECIMAL(12,4),
    previous_close  DECIMAL(12,4),
    change_amount   DECIMAL(12,4),
    change_percent  DECIMAL(10,4),

    -- Volume / size --------------------------------------------------------
    -- BIGINT, not INT: heavily traded tickers exceed INT's ~2.1B ceiling.
    volume          BIGINT NOT NULL,
    market_cap      DECIMAL(20,2),

    -- Audit ----------------------------------------------------------------
    -- When WE fetched it, as opposed to which session it describes. Keeping
    -- both means a late or re-run backfill stays traceable.
    collected_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- One row per symbol per trading session. This is what makes the pipeline
    -- idempotent: re-running any number of times updates in place.
    CONSTRAINT stocks_symbol_trading_day_key UNIQUE (symbol, trading_day)
);

-- Supports the common query shape: latest data, or one symbol's history.
CREATE INDEX IF NOT EXISTS stocks_trading_day_idx
    ON market_data.stocks (trading_day DESC);
CREATE INDEX IF NOT EXISTS stocks_symbol_idx
    ON market_data.stocks (symbol);
