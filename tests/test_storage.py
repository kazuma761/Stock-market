import logging
import unittest
from unittest.mock import MagicMock, patch

import psycopg2

from core.storage import QUALIFIED_TABLE, Storage

DB_ENV = {
    "POSTGRES_USER": "user",
    "POSTGRES_PASSWORD": "password",
    "POSTGRES_DB": "market_data",
    "POSTGRES_PORT": "5432",
    "POSTGRES_HOST": "postgres",
}

ROW = {
    "name": "Apple Inc",
    "market_cap": "3000000000000",
    "volume": "50000000",
    "price": "150.00",
    "change_percent": "1.23",
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
        # The unique constraint plus ON CONFLICT is what makes a re-run
        # idempotent rather than duplicating the day's row.
        self.assertIn("ON CONFLICT (symbol, date_collected) DO UPDATE", sql)
        self.assertIn(QUALIFIED_TABLE, sql)
        self.assertEqual(params[0], "AAPL")

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

        self.assertEqual(cursor.execute.call_args[0][1][3], "5000000000")

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
