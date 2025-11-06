"""
NOAA GFS GRIB2 Data Fetcher

Fetches Global Forecast System (GFS) weather data from NOAA's NOMADS server.
Implements intelligent retry logic with exponential backoff to find the most
recent available forecast.

Rate Limiting: NOAA requires 10 seconds between requests for the same file.
This implementation respects that limit.
"""

import datetime as dt
import time
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from loguru import logger
from msgspec import Struct

import noaa_query_builder as nqb
from config import settings


# =============================================================================
# EXCEPTIONS
# =============================================================================


class ForecastDataUnavailable(Exception):
    """Raised when no forecast data is available after all retries."""

    pass


class NOAAServerError(Exception):
    """Raised when NOAA server returns 5xx error."""

    pass


# =============================================================================
# DATA STRUCTURES
# =============================================================================


class FetchAttempt(Struct):
    """Record of a single fetch attempt."""

    url: str
    status_code: int | None
    error_type: str | None
    timestamp: datetime


class FetchResult(Struct):
    """Result of fetch operation with metadata."""

    data: bytes | None
    attempts: list[FetchAttempt]
    success: bool
    total_duration_seconds: float


# =============================================================================
# RETRY LOGIC
# =============================================================================


def calculate_exponential_backoff(
    attempt: int,
    initial_delay: float | None = None,
    max_delay: float | None = None,
) -> float:
    """
    Calculate exponential backoff delay with jitter.

    Prevents thundering herd by adding randomness to retry timing.
    """
    import random

    if initial_delay is None:
        initial_delay = settings.retry_settings.initial_delay_seconds
    if max_delay is None:
        max_delay = settings.retry_settings.max_delay_seconds

    delay = min(initial_delay * (2**attempt), max_delay)
    # Add jitter: ±20% of calculated delay
    jitter = delay * 0.2 * (2 * random.random() - 1)
    return delay + jitter


def should_retry_status_code(status_code: int) -> bool:
    """
    Determine if HTTP status code warrants a retry.

    404: Data not available yet (common for recent forecasts) - try older
    5xx: Server error - might be transient, retry
    2xx/3xx: Success - no retry needed
    4xx (except 404): Client error - no retry needed
    """
    if status_code == settings.http_settings.not_found:
        return False  # Try next (older) forecast instead

    return status_code >= settings.http_settings.server_error


# =============================================================================
# HTTP FETCHING
# =============================================================================


def fetch_with_retry(
    url: str,
    attempt_number: int = 0,
) -> tuple[httpx.Response | None, FetchAttempt]:
    """
    Fetch URL with error handling and logging.

    Returns response and attempt record. Response is None on failure.
    """
    attempt = FetchAttempt(
        url=url,
        status_code=None,
        error_type=None,
        timestamp=datetime.now(timezone.utc),
    )

    try:
        logger.info(f"Fetching (attempt {attempt_number + 1}): {url}")

        response = httpx.get(
            url,
            timeout=settings.http_settings.request_timeout_seconds,
            follow_redirects=True,
        )

        attempt.status_code = response.status_code

        if response.status_code == settings.http_settings.success:
            logger.info(f"Success: {len(response.content):,} bytes received")
            return response, attempt

        elif response.status_code == settings.http_settings.not_found:
            logger.warning("Data not found (404) - forecast likely not available yet")
            return None, attempt

        elif response.status_code >= settings.http_settings.server_error:
            logger.error(f"Server error ({response.status_code})")
            attempt.error_type = "server_error"
            return None, attempt

        else:
            logger.warning(f"Unexpected status code: {response.status_code}")
            attempt.error_type = "client_error"
            return None, attempt

    except httpx.TimeoutException:
        logger.error(
            f"Request timeout after {settings.http_settings.request_timeout_seconds}s"
        )
        attempt.error_type = "timeout"
        return None, attempt

    except httpx.NetworkError as e:
        logger.error(f"Network error: {e}")
        attempt.error_type = "network_error"
        return None, attempt

    except Exception as e:
        logger.error(f"Unexpected error: {type(e).__name__}: {e}")
        attempt.error_type = "unknown_error"
        return None, attempt


def fetch_with_exponential_backoff(
    url: str,
    max_attempts: int | None = None,
) -> tuple[httpx.Response | None, list[FetchAttempt]]:
    """
    Fetch URL with exponential backoff retry logic.

    Only retries on transient errors (5xx, timeout, network).
    Does not retry on 404 or other client errors.
    """
    if max_attempts is None:
        max_attempts = settings.retry_settings.max_attempts

    attempts: list[FetchAttempt] = []

    for attempt_num in range(max_attempts):
        response, attempt = fetch_with_retry(url, attempt_num)
        attempts.append(attempt)

        if response is not None:
            return response, attempts

        # Check if we should retry
        if attempt.status_code and not should_retry_status_code(attempt.status_code):
            logger.debug("Status code does not warrant retry")
            break

        # Don't sleep after last attempt
        if attempt_num < max_attempts - 1:
            delay = calculate_exponential_backoff(attempt_num)
            logger.info(f"Retrying in {delay:.1f} seconds...")
            time.sleep(delay)

    return None, attempts


# =============================================================================
# MAIN FETCH LOGIC
# =============================================================================


def fetch_most_recent_forecast(
    query_urls: Iterator[str],
    output_path: Path,
) -> FetchResult:
    """
    Try each query URL until one succeeds, with retry logic.

    Implements:
    - Exponential backoff on transient errors (5xx, timeout)
    - Rate limiting between different forecast times
    - Comprehensive attempt tracking

    Returns FetchResult with data and all attempt metadata.
    """
    start_time = time.time()
    all_attempts: list[FetchAttempt] = []
    first_url = True
    url_count = 0

    for url in query_urls:
        url_count += 1

        # Rate limiting: wait between requests (except first)
        if not first_url:
            logger.debug(
                f"Rate limit: waiting {settings.noaa_settings.rate_limit_seconds}s..."
            )
            time.sleep(settings.noaa_settings.rate_limit_seconds)
        first_url = False

        # Try this URL with retry logic
        response, attempts = fetch_with_exponential_backoff(url)
        all_attempts.extend(attempts)

        if response is not None and response.status_code == settings.http_settings.success:
            # Success! Save and return
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.content)

            duration = time.time() - start_time
            logger.info(f"Successfully downloaded to {output_path}")

            return FetchResult(
                data=response.content,
                attempts=all_attempts,
                success=True,
                total_duration_seconds=duration,
            )

    # All URLs failed
    duration = time.time() - start_time
    logger.error(
        f"Failed to fetch forecast after {len(all_attempts)} attempts "
        f"across {url_count} forecast times"
    )

    return FetchResult(
        data=None,
        attempts=all_attempts,
        success=False,
        total_duration_seconds=duration,
    )


def fetch_with_timeout(
    query_urls: Iterator[str],
    output_path: Path,
    timeout_minutes: float | None = None,
) -> FetchResult:
    """
    Fetch with overall timeout across all retries.

    Useful for critical data where you want to fail after a fixed period
    rather than exhausting all possible retries.
    """
    import signal

    if timeout_minutes is None:
        timeout_minutes = settings.retry_settings.timeout_minutes

    def timeout_handler(signum, frame):
        raise TimeoutError(f"Fetch exceeded {timeout_minutes} minute timeout")

    # Set alarm (Unix only - won't work on Windows)
    try:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(timeout_minutes * 60))

        result = fetch_most_recent_forecast(query_urls, output_path)

        signal.alarm(0)  # Cancel alarm
        return result

    except AttributeError:
        # Windows or signal not available - just run without timeout
        logger.warning("Timeout not supported on this platform, running without")
        return fetch_most_recent_forecast(query_urls, output_path)


# =============================================================================
# MAIN EXECUTION
# =============================================================================


def main() -> None:
    """Fetch most recent NOAA GFS forecast data."""
    # setup_logging()

    logger.info("Starting NOAA GFS forecast fetch")

    model_data = nqb.ModelData.model_validate(settings.GFS_DATA)
    query_mask = nqb.QueryMask.model_validate(settings.GFS_QUERIES.sailing_basic)

    qs = nqb.QueryStructure(
        bounding_box=nqb.create_bounding_box(
            ls=nqb.LocationSettings.model_validate(settings.DEFAULT_LOCATION)
        ),
        query_model=nqb.QueryModel.model_validate(
            settings.GFS_PRODUCTS.gfs_quarter_degree,
        ),
        variables=nqb.SelectedKeys(
            all_keys=model_data.variables,
            hex_mask=query_mask.variables,
            prefix="var_",
        ),
        levels=nqb.SelectedKeys(
            all_keys=model_data.levels,
            hex_mask=query_mask.levels,
            prefix="lev_",
        ),
        current_time=dt.datetime.now(tz=dt.timezone.utc),
        settings=nqb.CoreSettings.model_validate(settings.core_settings),
    )

    query_urls = nqb.generate_query_urls(
        qt_batch=nqb.generate_qt_batch(reference_time=qs.current_time, qs=qs),
        qs=qs,
    )

    # Fetch data with timeout
    output_path = Path(settings.core_settings.output_dir) / "test.anl"
    result = fetch_with_timeout(
        query_urls=query_urls,
        output_path=output_path,
    )

    # Report results
    if result.success and result.data:
        logger.info(
            f"✓ Success after {len(result.attempts)} attempts "
            f"in {result.total_duration_seconds:.1f}s"
        )
        logger.info(f"Downloaded {len(result.data):,} bytes to {output_path}")
    else:
        logger.error(
            f"✗ Failed after {len(result.attempts)} attempts "
            f"in {result.total_duration_seconds:.1f}s"
        )

        # Log attempt summary
        if result.attempts:
            status_counts: dict[str, int] = {}
            for attempt in result.attempts:
                key = (
                    str(attempt.status_code)
                    if attempt.status_code
                    else attempt.error_type or "unknown"
                )
                status_counts[key] = status_counts.get(key, 0) + 1

            logger.error(f"Attempt summary: {status_counts}")
        else:
            logger.error("No attempts were made - check query URL generation!")

        raise ForecastDataUnavailable(
            f"Could not fetch forecast data after {len(result.attempts)} attempts"
        )


if __name__ == "__main__":
    main()
