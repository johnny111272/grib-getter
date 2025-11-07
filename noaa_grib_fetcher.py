"""
NOAA GFS GRIB2 Data Fetcher

Fetches Global Forecast System (GFS) weather data from NOAA's NOMADS server.

Key features:
- Intelligent retry logic with exponential backoff
- Tries most recent forecast first, falls back to older forecasts if unavailable
- Respects NOAA rate limiting (10 seconds between requests)
- Comprehensive attempt tracking for debugging
"""

import time
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import httpx
from loguru import logger
from pydantic import BaseModel

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


class FetchAttempt(BaseModel):
    """
    Record of a single fetch attempt.

    Tracks URL, status code, error type, and timestamp for debugging.
    """

    url: str
    status_code: int | None
    error_type: str | None
    timestamp: datetime


class FetchResult(BaseModel):
    """
    Result of fetch operation with metadata.

    Includes data bytes (if successful), all attempt records, success flag,
    and total duration for performance tracking.
    """

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
    Jitter helps avoid synchronized retries from multiple clients.
    """
    import random

    if initial_delay is None:  # pyright: ignore[reportUnknownMemberType]
        initial_delay = settings.retry_settings.initial_delay_seconds  # pyright: ignore[reportUnknownMemberType]
    if max_delay is None:  # pyright: ignore[reportUnknownMemberType]
        max_delay = settings.retry_settings.max_delay_seconds  # pyright: ignore[reportUnknownMemberType]

    # Exponential backoff: 2^attempt * initial_delay, capped at max_delay
    delay = min(initial_delay * (2**attempt), max_delay)  # pyright: ignore[reportArgumentType]

    # Add jitter: ±20% of calculated delay to prevent thundering herd
    jitter_percent = 0.2
    jitter = delay * jitter_percent * (2 * random.random() - 1)
    return delay + jitter


def should_retry_status_code(status_code: int) -> bool:
    """
    Determine if HTTP status code warrants a retry.

    Retry strategy:
    - 404: Don't retry same URL, try next (older) forecast instead
    - 5xx: Retry (server error, might be transient)
    - 2xx/3xx: No retry (success)
    - Other 4xx: No retry (client error, won't be fixed by retrying)

    Returns True if we should retry the same URL with backoff.
    """
    if status_code == settings.http_settings.not_found:
        return False  # Move to next (older) forecast instead of retrying

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
    if max_attempts is None:  # pyright: ignore[reportUnknownMemberType]
        max_attempts = settings.retry_settings.max_attempts  # pyright: ignore[reportUnknownMemberType]

    attempts: list[FetchAttempt] = []

    for attempt_num in range(max_attempts):  # pyright: ignore[reportArgumentType]
        response, attempt = fetch_with_retry(url, attempt_num)
        attempts.append(attempt)

        if response is not None:
            return response, attempts

        # Check if we should retry
        if attempt.status_code and not should_retry_status_code(attempt.status_code):
            logger.debug("Status code does not warrant retry")
            break

        # Don't sleep after last attempt
        if attempt_num < max_attempts - 1:  # pyright: ignore[reportOptionalOperand]
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

    Implements intelligent fallback: tries most recent forecast first, then
    progressively older forecasts. Most recent forecasts are often not yet
    available on NOAA servers, so this fallback is critical.

    Features:
    - Exponential backoff on transient errors (5xx, timeout)
    - Rate limiting between different forecast times (NOAA requirement)
    - Comprehensive attempt tracking for debugging

    Returns:
        FetchResult with data (if successful) and all attempt metadata
    """
    start_time = time.time()
    all_attempts: list[FetchAttempt] = []
    first_url = True
    url_count = 0

    for url in query_urls:
        url_count += 1

        # Rate limiting: wait between requests (NOAA requires 10s minimum)
        if not first_url:
            logger.debug(
                f"Rate limit: waiting {settings.noaa_settings.rate_limit_seconds}s..."
            )
            time.sleep(settings.noaa_settings.rate_limit_seconds)
        first_url = False

        # Try this URL with retry logic
        response, attempts = fetch_with_exponential_backoff(url)
        all_attempts.extend(attempts)

        if (
            response is not None
            and response.status_code == settings.http_settings.success
        ):
            # Success! Save and return
            output_path.parent.mkdir(parents=True, exist_ok=True)
            _ = output_path.write_bytes(response.content)

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

    Useful for automated scripts that need predictable failure times
    rather than exhausting all retries (which could take a long time).

    Note: Uses SIGALRM which only works on Unix systems. On Windows,
    falls back to no timeout.
    """
    import signal

    if timeout_minutes is None:  # pyright: ignore[reportUnknownMemberType]
        timeout_minutes = settings.retry_settings.timeout_minutes  # pyright: ignore[reportUnknownMemberType]

    def timeout_handler(signum, frame):  # pyright: ignore[reportUnusedParameter, reportMissingParameterType]
        raise TimeoutError(f"Fetch exceeded {timeout_minutes} minute timeout")

    # Set alarm (Unix/Mac only - gracefully degrades on Windows)
    try:
        _ = signal.signal(signal.SIGALRM, timeout_handler)  # pyright: ignore[reportUnknownArgumentType]
        _ = signal.alarm(int(timeout_minutes * 60))  # pyright: ignore[reportOptionalOperand]

        result = fetch_most_recent_forecast(query_urls, output_path)

        _ = signal.alarm(0)  # Cancel alarm
        return result

    except AttributeError:
        # Windows or signal not available - just run without timeout
        logger.warning("Timeout not supported on this platform, running without")
        return fetch_most_recent_forecast(query_urls, output_path)
