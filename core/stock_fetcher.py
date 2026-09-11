import logging
import os
import time

import requests
from dotenv import load_dotenv

from utils import read_json

load_dotenv()

BASE_URL = "https://www.alphavantage.co/query"
REQUEST_TIMEOUT_SECONDS = 30

# The free tier allows 1 request/second. Pacing calls is cheaper than handling
# the throttle after the fact.
REQUEST_INTERVAL_SECONDS = 1.5

# Alpha Vantage reports most failures inside an HTTP 200 body rather than via a
# status code, so `raise_for_status()` will not catch any of them and the body
# must be inspected before the payload is indexed.
#
# Both the per-second burst limit and the exhausted daily quota arrive under the
# same key, with only the prose differing -- so the two cannot be told apart
# reliably by inspecting the message. They are distinguished by behaviour
# instead: back off and retry once. A burst limit clears; a spent daily quota
# does not.
RATE_LIMIT_KEYS = ("Note", "Information")
ERROR_KEY = "Error Message"

# Rate-limit backoff. Alpha Vantage's throttle can persist well beyond a couple
# of seconds, so give it several escalating chances before concluding the daily
# quota is actually spent -- a premature conclusion abandons the whole run.
BACKOFF_SCHEDULE_SECONDS = (5, 15, 45)

# Transient transport failures are retried here, in-process. Leaving them to
# Airflow's task retries would not work: fetch() isolates per-symbol errors so
# the other symbols continue, which means a network blip never fails the fetch
# task and Airflow would never re-run it.
NETWORK_RETRY_DELAYS_SECONDS = (2, 5)
TRANSIENT_ERRORS = (requests.exceptions.ConnectionError, requests.exceptions.Timeout)


class RateLimited(Exception):
    """Raised when the API declines a call for rate-limit reasons.

    Covers both the per-second burst limit and the exhausted daily quota, which
    are indistinguishable in the response body.
    """


class QuotaExhausted(Exception):
    """Raised when the request budget is judged to be spent for the day.

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
        self._last_request_at = 0.0

        if not self.api_key:
            raise ValueError(
                "ALPHA_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        if not self.symbols:
            raise ValueError("No symbols configured. Add at least one to config.json.")

    def _throttle(self) -> None:
        """Space requests out to stay inside the free tier's 1/second limit."""
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < REQUEST_INTERVAL_SECONDS:
            time.sleep(REQUEST_INTERVAL_SECONDS - elapsed)
        self._last_request_at = time.monotonic()

    def _redact(self, message: object) -> str:
        """Strip the API key from text headed for logs, XCom, or exceptions.

        Alpha Vantage echoes the key back inside its rate-limit notice, and
        requests puts the full URL -- `apikey=` included -- in HTTP errors.
        """
        return str(message).replace(self.api_key, "***")

    def _call(self, function: str, symbol: str) -> dict:
        """Make one paced API call and return its parsed body.

        Raises:
            RateLimited: If the body carries a rate-limit notice.
            ValueError: If the body carries an API-level error message.
            requests.exceptions.RequestException: On transport or HTTP failure.
        """
        self._throttle()
        response = requests.get(
            BASE_URL,
            params={"function": function, "symbol": symbol, "apikey": self.api_key},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()

        for key in RATE_LIMIT_KEYS:
            if key in payload:
                raise RateLimited(self._redact(payload[key]))

        if ERROR_KEY in payload:
            raise ValueError(self._redact(payload[ERROR_KEY]))

        return payload

    def _call_with_network_retry(self, function: str, symbol: str) -> dict:
        """`_call`, retrying dropped connections and timeouts.

        Raises:
            The same as `_call`, once the network retries are used up.
        """
        for delay in NETWORK_RETRY_DELAYS_SECONDS:
            try:
                return self._call(function, symbol)
            except TRANSIENT_ERRORS as e:
                self.logger.warning(
                    f"Network error on {function} for {symbol}: {self._redact(e)}. "
                    f"Retrying in {delay}s."
                )
                time.sleep(delay)

        return self._call(function, symbol)

    def _request(self, function: str, symbol: str) -> dict:
        """Call an endpoint, retrying with escalating backoff if rate-limited.

        A rate-limit response is ambiguous: it means either a transient throttle
        or the spent daily quota, and the body does not distinguish them. They
        are told apart by persistence -- a throttle clears, the daily quota does
        not -- so the call is retried on an escalating schedule before the quota
        is declared spent. Concluding too early abandons the entire run over a
        condition that would have cleared on its own.

        Raises:
            QuotaExhausted: If the limit survives every retry.
            ValueError: If the response carries an API-level error message.
            requests.exceptions.RequestException: On transport or HTTP failure.
        """
        last: Exception | None = None

        for attempt, backoff in enumerate(BACKOFF_SCHEDULE_SECONDS, start=1):
            try:
                return self._call_with_network_retry(function, symbol)
            except RateLimited as e:
                last = e
                self.logger.warning(
                    f"Rate-limited on {function} for {symbol} "
                    f"(attempt {attempt}/{len(BACKOFF_SCHEDULE_SECONDS) + 1}). "
                    f"Backing off {backoff}s."
                )
                time.sleep(backoff)

        try:
            return self._call_with_network_retry(function, symbol)
        except RateLimited as final:
            raise QuotaExhausted(final) from final

    @staticmethod
    def _optional(quote: dict, key: str) -> str | None:
        """Read a non-essential quote field, tolerating its absence.

        Missing optional fields are stored as NULL rather than failing the
        symbol: a quote without a high/low is still a usable price record.
        """
        value = quote.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else None

    def _fetch_symbol(self, symbol: str) -> dict[str, str | None]:
        """Fetch and parse both endpoints for a single symbol.

        Every data point the API returns is captured, not just the headline
        price -- the fields arrive in the same response either way, so
        discarding them buys nothing.

        Raises:
            QuotaExhausted: Propagated so the caller can stop the run.
            ValueError: If a REQUIRED field is missing or the payload is empty.
            requests.exceptions.RequestException: On transport failure.
        """
        quote = self._request("GLOBAL_QUOTE", symbol).get("Global Quote")
        if not quote:
            raise ValueError(f"No quote data returned for {symbol}")

        # Required: without these the row is meaningless or violates NOT NULL.
        try:
            price = quote["05. price"]
            volume = quote["06. volume"]
            trading_day = quote["07. latest trading day"]
        except KeyError as e:
            raise ValueError(f"Quote for {symbol} is missing {e}") from e

        if not all([price, volume, trading_day]):
            raise ValueError(f"Quote for {symbol} has empty required fields")

        overview = self._request("OVERVIEW", symbol)
        name = overview.get("Name")
        if not name:
            raise ValueError(f"No company overview returned for {symbol}")

        change_percent = self._optional(quote, "10. change percent")

        return {
            "name": name,
            "trading_day": trading_day,
            "price": price,
            "open_price": self._optional(quote, "02. open"),
            "high_price": self._optional(quote, "03. high"),
            "low_price": self._optional(quote, "04. low"),
            "previous_close": self._optional(quote, "08. previous close"),
            "change_amount": self._optional(quote, "09. change"),
            # Stored as a number, so the API's trailing "%" has to go.
            "change_percent": change_percent.rstrip("%") if change_percent else None,
            "volume": volume,
            "market_cap": self._optional(overview, "MarketCapitalization"),
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
                fields = self._fetch_symbol(symbol)
                data[symbol] = fields
                # Log the values, not just the fact of success: the task log is
                # the first place anyone looks to confirm what was collected.
                self.logger.info(
                    f"Fetched {symbol} ({fields['name']}) "
                    f"for {fields['trading_day']}: "
                    f"price={fields['price']} "
                    f"open={fields['open_price']} "
                    f"high={fields['high_price']} "
                    f"low={fields['low_price']} "
                    f"prev_close={fields['previous_close']} "
                    f"change={fields['change_amount']} "
                    f"({fields['change_percent']}%) "
                    f"volume={fields['volume']} "
                    f"market_cap={fields['market_cap']}"
                )

            except QuotaExhausted as e:
                remaining = self.symbols[self.symbols.index(symbol) :]
                self.logger.error(
                    f"API quota exhausted at {symbol}: {e}. "
                    f"Abandoning {len(remaining)} remaining symbol(s): {remaining}"
                )
                failures.extend(f"{s}: quota exhausted" for s in remaining)
                break

            except requests.exceptions.RequestException as e:
                reason = self._redact(e)
                self.logger.error(f"Request failed for {symbol}: {reason}")
                failures.append(f"{symbol}: request failed ({reason})")

            except (ValueError, KeyError, TypeError) as e:
                self.logger.error(f"Could not parse data for {symbol}: {e}")
                failures.append(f"{symbol}: {e}")

        self.logger.info(
            f"Fetch complete: {len(data)} succeeded, {len(failures)} failed."
        )
        return data, failures
