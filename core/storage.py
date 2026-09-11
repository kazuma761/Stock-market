import logging
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

SCHEMA_NAME = "market_data"
TABLE_NAME = "stocks"
QUALIFIED_TABLE = f"{SCHEMA_NAME}.{TABLE_NAME}"

# Must be present and non-empty, or the row is rejected. Everything else is
# nullable: a quote missing its high/low is still a usable price record.
REQUIRED_FIELDS = ("name", "trading_day", "price", "volume")

# Column order shared by the INSERT and the parameter tuple, so the two cannot
# drift apart silently.
COLUMNS = (
    "symbol",
    "name",
    "trading_day",
    "price",
    "open_price",
    "high_price",
    "low_price",
    "previous_close",
    "change_amount",
    "change_percent",
    "volume",
    "market_cap",
)

_PLACEHOLDERS = ", ".join(["%s"] * len(COLUMNS))
_UPDATES = ",\n        ".join(
    f"{c} = EXCLUDED.{c}" for c in COLUMNS if c not in ("symbol", "trading_day")
)

# Idempotent write. The conflict target is (symbol, trading_day) -- the session
# the data describes, not the day we happened to run -- so a weekend re-run
# updates Friday's row instead of inventing a second one.
UPSERT_SQL = f"""
    INSERT INTO {QUALIFIED_TABLE} ({", ".join(COLUMNS)})
    VALUES ({_PLACEHOLDERS})
    ON CONFLICT (symbol, trading_day) DO UPDATE SET
        {_UPDATES},
        collected_at = now()
"""


class Storage:
    """Writes stock data into Postgres.

    Attributes:
        logger: The logger used for reporting progress and failures.
        conn: The database connection, open only for the duration of a write.
        cur: The database cursor.
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.conn = None
        self.cur = None

    def _connect(self) -> None:
        try:
            self.conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST"),
                port=os.getenv("POSTGRES_PORT"),
                database=os.getenv("POSTGRES_DB"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
            )
            self.cur = self.conn.cursor()
        except psycopg2.Error as e:
            self.logger.error(f"Error connecting to the database: {e}")
            raise

    def _close(self) -> None:
        try:
            if self.cur:
                self.cur.close()
            if self.conn:
                self.conn.close()
        except psycopg2.Error as e:
            self.logger.error(f"Error closing the database connection: {e}")

    def store_data(self, data: dict[str, dict[str, str]]) -> int:
        """Upsert one row per symbol.

        Rows missing a required field are skipped rather than aborting the
        batch: one incomplete symbol should not cost us the others.

        Args:
            data: Mapping of symbol to its extracted fields.

        Returns:
            The number of rows written.

        Raises:
            psycopg2.Error: If the database itself fails. The transaction is
                rolled back before the error propagates.
        """
        if not data:
            self.logger.warning("No data supplied. Nothing written to the database.")
            return 0

        written = 0
        try:
            self._connect()
            with self.conn, self.cur:
                for symbol, fields in data.items():
                    missing = [f for f in REQUIRED_FIELDS if not fields.get(f)]
                    if missing:
                        self.logger.error(
                            f"Skipping {symbol}: missing required field(s) {missing}"
                        )
                        continue

                    self.cur.execute(
                        UPSERT_SQL,
                        tuple(
                            symbol if c == "symbol" else fields.get(c) for c in COLUMNS
                        ),
                    )
                    written += 1
                    self.logger.info(
                        f"Stored {symbol} for {fields['trading_day']}: "
                        f"price={fields['price']} volume={fields['volume']}"
                    )

            self.logger.info(f"Wrote {written} row(s) to {QUALIFIED_TABLE}.")
            return written

        except psycopg2.Error as error:
            self.logger.error(f"Database error while storing data: {error}")
            if self.conn:
                self.conn.rollback()
            raise
        finally:
            self._close()
