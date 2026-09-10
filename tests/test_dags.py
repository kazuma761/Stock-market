import logging
import unittest
from unittest.mock import MagicMock, patch

from airflow.exceptions import AirflowException

logging.getLogger("airflow").setLevel(logging.ERROR)


class TestDagIntegrity(unittest.TestCase):
    """The DAG must import cleanly and expose the expected shape."""

    @classmethod
    def setUpClass(cls):
        from airflow.models import DagBag

        cls.dagbag = DagBag(dag_folder="dags", include_examples=False)

    def test_no_import_errors(self):
        self.assertEqual(self.dagbag.import_errors, {})

    def test_dag_is_registered(self):
        self.assertIn("stock_data_pipeline", self.dagbag.dags)

    def test_has_fetch_then_store(self):
        dag = self.dagbag.dags["stock_data_pipeline"]

        self.assertEqual(
            sorted(t.task_id for t in dag.tasks),
            ["fetch_stock_data", "store_stock_data"],
        )
        fetch = dag.get_task("fetch_stock_data")
        self.assertEqual(list(fetch.downstream_task_ids), ["store_stock_data"])

    def test_catchup_disabled_and_start_date_is_static(self):
        dag = self.dagbag.dags["stock_data_pipeline"]

        self.assertFalse(dag.catchup)
        # A dynamic start_date would move on every parse.
        self.assertEqual(dag.default_args["start_date"].year, 2024)

    def test_retries_configured(self):
        dag = self.dagbag.dags["stock_data_pipeline"]

        self.assertGreaterEqual(dag.default_args["retries"], 1)


class TestStoreTaskFailureSignal(unittest.TestCase):
    """Partial failures must be surfaced, but only after the good rows land."""

    @patch("dags.stock_data_dag.Storage")
    def test_raises_when_a_symbol_failed(self, mock_storage):
        from dags.stock_data_dag import store_stock_data

        mock_storage.return_value.store_data.return_value = 2

        with self.assertRaises(AirflowException) as ctx:
            store_stock_data({"data": {"AAPL": {}}, "failures": ["GOOG: quota"]})

        self.assertIn("GOOG", str(ctx.exception))

    @patch("dags.stock_data_dag.Storage")
    def test_stores_before_raising(self, mock_storage):
        from dags.stock_data_dag import store_stock_data

        store = mock_storage.return_value.store_data
        store.return_value = 1

        with self.assertRaises(AirflowException):
            store_stock_data({"data": {"AAPL": {}}, "failures": ["GOOG: quota"]})

        # Raising before the write would discard the data we did collect.
        store.assert_called_once()

    @patch("dags.stock_data_dag.Storage")
    def test_silent_when_everything_succeeded(self, mock_storage):
        from dags.stock_data_dag import store_stock_data

        mock_storage.return_value.store_data.return_value = 3

        store_stock_data({"data": {"AAPL": {}}, "failures": []})


if __name__ == "__main__":
    unittest.main()
