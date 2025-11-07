# GRIB Fetcher Reference

HTTP fetching with retry logic and rate limiting for NOAA GRIB data.

## Exceptions

::: noaa_grib_fetcher.ForecastDataUnavailable
    options:
      show_root_heading: true
      show_source: true

::: noaa_grib_fetcher.NOAAServerError
    options:
      show_root_heading: true
      show_source: true

## Data Models

::: noaa_grib_fetcher.FetchAttempt
    options:
      show_root_heading: true
      show_source: true

::: noaa_grib_fetcher.FetchResult
    options:
      show_root_heading: true
      show_source: true

## Main Functions

::: noaa_grib_fetcher.fetch_most_recent_forecast
    options:
      show_root_heading: true
      show_source: true

::: noaa_grib_fetcher.fetch_with_retry
    options:
      show_root_heading: true
      show_source: true

::: noaa_grib_fetcher.fetch_with_exponential_backoff
    options:
      show_root_heading: true
      show_source: true

::: noaa_grib_fetcher.fetch_with_timeout
    options:
      show_root_heading: true
      show_source: true

## Helper Functions

::: noaa_grib_fetcher.calculate_exponential_backoff
    options:
      show_root_heading: true
      show_source: true

::: noaa_grib_fetcher.should_retry_status_code
    options:
      show_root_heading: true
      show_source: true
