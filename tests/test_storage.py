import logging
import unittest
from unittest.mock import MagicMock, patch

import psycopg2

from core.storage import COLUMNS, QUALIFIED_TABLE, Storage

DB_ENV = {
    "POSTGRES_USER": "user",
    "POSTGRES_PASSWORD": "password",
    "POSTGRES_DB": "market_data",
    "POSTGRES_PORT": "5432",
    "POSTGRES_HOST": "postgres",
}

ROW = {
    "name": "Apple Inc.",
    "trading_day": "2026-09-10",
    "price": "326.5700",
    "open_price": "316.6700",
    "high_price": "326.7400",
    "low_price": "316.5100",
    "previous_close": "315.3400",
    "change_amount": "11.2300",
    "change_percent": "3.5612",
    "volume": "70011913",
    "market_cap": "4602128761000",
}


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.logger = MagicMock(spec=logging.Logger)
        self.storage = Storage(logger=self.logger)

    @patch.dict("core.storage.os.environ", DB_ENV, clear=True)
    @patch("core.storage.psycopg2.connect")
    def test_connect_uses_environment_variables(self, mock_connect):
        self.storage._connect()

        mock_connect.assert_called_once_with(
            host="postgres",
            port="5432",
            database="market_data",
            user="user",
            password="password",
        )

    @patch.dict("core.storage.os.environ", DB_ENV, clear=True)
    @patch("core.storage.psycopg2.connect")
    def test_connection_failure_is_logged_and_raised(self, mock_connect):
        mock_connect.side_effect = psycopg2.OperationalError("no route to host")

        with self.assertRaises(psycopg2.Error):
            self.storage._connect()
        self.logger.error.assert_called()

    @patch.dict("core.storage.os.environ", DB_ENV, clear=True)
    @patch("core.storage.psycopg2.connect")
    def test_store_data_upserts_on_conflict(self, mock_connect):
        cursor = mock_connect.return_value.cursor.return_value

        written = self.storage.store_data({"AAPL": ROW})

        self.assertEqual(written, 1)
        sql, params = cursor.execute.call_args[0]
        # Keyed on the trading session, not the run date: a weekend re-run must
        # update Friday's row, not create a second one for the same session.
        self.assertIn("ON CONFLICT (symbol, trading_day) DO UPDATE", sql)
        self.assertIn(QUALIFIED_TABLE, sql)
        self.assertEqual(params[0], "AAPL")
        self.assertEqual(len(params), len(COLUMNS))

    @patch.dict("core.storage.os.environ", DB_ENV, clear=True)
    @patch("core.storage.psycopg2.connect")
    def test_all_quote_fields_are_persisted(self, mock_connect):
        cursor = mock_connect.return_value.cursor.return_value

        self.storage.store_data({"AAPL": ROW})

        sql, params = cursor.execute.call_args[0]
        stored = dict(zip(COLUMNS, params))
        # Every field the API handed us should land -- they cost no extra call.
        self.assertEqual(stored["open_price"], "316.6700")
        self.assertEqual(stored["high_price"], "326.7400")
        self.assertEqual(stored["low_price"], "316.5100")
        self.assertEqual(stored["previous_close"], "315.3400")
        self.assertEqual(stored["change_amount"], "11.2300")
        self.assertEqual(stored["trading_day"], "2026-09-10")

    @patch.dict("core.storage.os.environ", DB_ENV, clear=True)
    @patch("core.storage.psycopg2.connect")
    def test_nullable_fields_pass_through_as_none(self, mock_connect):
        cursor = mock_connect.return_value.cursor.return_value
        sparse = dict(ROW, high_price=None, market_cap=None)

        written = self.storage.store_data({"AAPL": sparse})

        self.assertEqual(written, 1)
        stored = dict(zip(COLUMNS, cursor.execute.call_args[0][1]))
        self.assertIsNone(stored["high_price"])
        self.assertIsNone(stored["market_cap"])

    @patch.dict("core.storage.os.environ", DB_ENV, clear=True)
    @patch("core.storage.psycopg2.connect")
    def test_repeat_store_issues_upsert_not_insert(self, mock_connect):
        cursor = mock_connect.return_value.cursor.return_value

        self.storage.store_data({"AAPL": ROW})
        self.storage.store_data({"AAPL": ROW})

        self.assertEqual(cursor.execute.call_count, 2)
        for call in cursor.execute.call_args_list:
            self.assertIn("ON CONFLICT", call[0][0])

    @patch.dict("core.storage.os.environ", DB_ENV, clear=True)
    @patch("core.storage.psycopg2.connect")
    def test_row_missing_required_field_is_skipped_not_fatal(self, mock_connect):
        cursor = mock_connect.return_value.cursor.return_value
        incomplete = {k: v for k, v in ROW.items() if k != "name"}

        written = self.storage.store_data({"BAD": incomplete, "AAPL": ROW})

        # The good symbol still lands; only the incomplete one is dropped.
        self.assertEqual(written, 1)
        self.assertEqual(cursor.execute.call_count, 1)
        self.logger.error.assert_called()

    @patch.dict("core.storage.os.environ", DB_ENV, clear=True)
    @patch("core.storage.psycopg2.connect")
    def test_high_volume_value_is_passed_through(self, mock_connect):
        # Regression guard for the INT -> BIGINT widening: this exceeds INT's
        # ~2.1B ceiling.
        cursor = mock_connect.return_value.cursor.return_value
        row = dict(ROW, volume="5000000000")

        self.storage.store_data({"AAPL": row})

        stored = dict(zip(COLUMNS, cursor.execute.call_args[0][1]))
        self.assertEqual(stored["volume"], "5000000000")

    @patch("core.storage.psycopg2.connect")
    def test_empty_data_writes_nothing(self, mock_connect):
        written = self.storage.store_data({})

        self.assertEqual(written, 0)
        mock_connect.assert_not_called()
        self.logger.warning.assert_called()

    @patch.dict("core.storage.os.environ", DB_ENV, clear=True)
    @patch("core.storage.psycopg2.connect")
    def test_database_error_rolls_back(self, mock_connect):
        conn = mock_connect.return_value
        conn.cursor.return_value.execute.side_effect = psycopg2.DatabaseError("boom")

        with self.assertRaises(psycopg2.Error):
            self.storage.store_data({"AAPL": ROW})
        conn.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
