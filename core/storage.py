import logging
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

SCHEMA_NAME = "market_data"
TABLE_NAME = "stocks"
QUALIFIED_TABLE = f"{SCHEMA_NAME}.{TABLE_NAME}"

REQUIRED_FIELDS = ("name", "market_cap", "volume", "price", "change_percent")

# Idempotent write: the (symbol, date_collected) unique constraint turns a
# repeat run into an update rather than a duplicate row.
UPSERT_SQL = f"""
    INSERT INTO {QUALIFIED_TABLE}
        (symbol, name, market_cap, volume, price, change_percent)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (symbol, date_collected) DO UPDATE SET
        name           = EXCLUDED.name,
        market_cap     = EXCLUDED.market_cap,
        volume         = EXCLUDED.volume,
        price          = EXCLUDED.price,
        change_percent = EXCLUDED.change_percent
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
                        (
                            symbol,
                            fields["name"],
                            fields["market_cap"],
                            fields["volume"],
                            fields["price"],
                            fields["change_percent"],
                        ),
                    )
                    written += 1
                    self.logger.info(f"Stored data for {symbol}.")

            self.logger.info(f"Wrote {written} row(s) to {QUALIFIED_TABLE}.")
            return written

        except psycopg2.Error as error:
            self.logger.error(f"Database error while storing data: {error}")
            if self.conn:
                self.conn.rollback()
            raise
        finally:
            self._close()
