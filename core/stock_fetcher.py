import logging
import os

import requests
from dotenv import load_dotenv

from utils import read_json

load_dotenv()

BASE_URL = "https://www.alphavantage.co/query"
REQUEST_TIMEOUT_SECONDS = 30

# Alpha Vantage reports most failures inside an HTTP 200 body rather than via a
# status code, using one of these keys. `raise_for_status()` will not catch any
# of them, so the body must be inspected before the payload is indexed.
#   "Note" / "Information" -> rate limit or daily quota exhausted
#   "Error Message"        -> invalid symbol, endpoint, or API key
RATE_LIMIT_KEYS = ("Note", "Information")
ERROR_KEY = "Error Message"


class QuotaExhausted(Exception):
    """Raised when the API's request budget is spent.

    Distinct from an ordinary failure because it is not worth retrying and not
    worth attempting the remaining symbols: the budget is account-wide.
    """


class StockFetcher:
    """Fetches quote and company data for a configured list of symbols.

    Each symbol costs two requests: GLOBAL_QUOTE for the price fields and
    OVERVIEW for the company name and market capitalisation.

    Attributes:
        logger: The logger used for reporting progress and failures.
        symbols: The ticker symbols to fetch.
        api_key: The Alpha Vantage API key, read from the environment.
    """

    def __init__(self, logger: logging.Logger, config_path: str = "config.json"):
        self.logger = logger
        self.symbols = read_json(config_path)["symbols"]
        self.api_key = os.getenv("ALPHA_API_KEY")

        if not self.api_key:
            raise ValueError(
                "ALPHA_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        if not self.symbols:
            raise ValueError("No symbols configured. Add at least one to config.json.")

    def _request(self, function: str, symbol: str) -> dict:
        """Call one Alpha Vantage endpoint and return its parsed body.

        Args:
            function: The API function name, e.g. "GLOBAL_QUOTE".
            symbol: The ticker to request.

        Returns:
            The decoded JSON body.

        Raises:
            QuotaExhausted: If the response signals a rate limit or spent quota.
            ValueError: If the response carries an API-level error message.
            requests.exceptions.RequestException: On transport or HTTP failure.
        """
        response = requests.get(
            BASE_URL,
            params={"function": function, "symbol": symbol, "apikey": self.api_key},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()

        for key in RATE_LIMIT_KEYS:
            if key in payload:
                raise QuotaExhausted(payload[key])

        if ERROR_KEY in payload:
            raise ValueError(payload[ERROR_KEY])

        return payload

    def _fetch_symbol(self, symbol: str) -> dict[str, str]:
        """Fetch and parse both endpoints for a single symbol.

        Raises:
            QuotaExhausted: Propagated so the caller can stop the run.
            ValueError: If either endpoint returns an error or empty payload.
            requests.exceptions.RequestException: On transport failure.
        """
        quote = self._request("GLOBAL_QUOTE", symbol).get("Global Quote")
        if not quote:
            raise ValueError(f"No quote data returned for {symbol}")

        overview = self._request("OVERVIEW", symbol)
        name = overview.get("Name")
        market_cap = overview.get("MarketCapitalization")
        if not name or not market_cap:
            raise ValueError(f"No company overview returned for {symbol}")

        return {
            "price": quote["05. price"],
            "volume": quote["06. volume"],
            "change_percent": quote["10. change percent"].rstrip("%"),
            "name": name,
            "market_cap": market_cap,
        }

    def fetch(self) -> tuple[dict[str, dict[str, str]], list[str]]:
        """Fetch every configured symbol.

        A failing symbol does not block its peers: the successes are still
        returned. Quota exhaustion is the exception — the remaining symbols are
        abandoned, since the budget is account-wide and further calls would only
        produce identical errors.

        Returns:
            A tuple of (data keyed by symbol, list of "symbol: reason" failures).
        """
        data: dict[str, dict[str, str]] = {}
        failures: list[str] = []

        for symbol in self.symbols:
            try:
                data[symbol] = self._fetch_symbol(symbol)
                self.logger.info(f"Fetched {symbol}.")

            except QuotaExhausted as e:
                remaining = self.symbols[self.symbols.index(symbol) :]
                self.logger.error(
                    f"API quota exhausted at {symbol}: {e}. "
                    f"Abandoning {len(remaining)} remaining symbol(s): {remaining}"
                )
                failures.extend(f"{s}: quota exhausted" for s in remaining)
                break

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request failed for {symbol}: {e}")
                failures.append(f"{symbol}: request failed ({e})")

            except (ValueError, KeyError, TypeError) as e:
                self.logger.error(f"Could not parse data for {symbol}: {e}")
                failures.append(f"{symbol}: {e}")

        self.logger.info(
            f"Fetch complete: {len(data)} succeeded, {len(failures)} failed."
        )
        return data, failures
