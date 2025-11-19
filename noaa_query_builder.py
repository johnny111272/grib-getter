"""
NOAA Query Builder

Constructs query URLs for NOAA's NOMADS GRIB filter service.

Key features:
- Geographic bounding box calculations
- Forecast time selection with lookback
- Variable/level selection via hexadecimal bitmasks
- URL-encoded query string generation
"""

import pathlib
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import pydantic


class ModelData(pydantic.BaseModel, frozen=True):
    """
    Available variables and levels for a model.

    Defines the complete set of options that can be selected via masks.
    """

    variables: list[str]
    levels: list[str]


class QueryModel(pydantic.BaseModel, frozen=True):
    """
    Product-specific query configuration.

    Defines NOAA URL patterns and file naming for a specific product
    (e.g., gfs_quarter_degree).
    """

    name: str
    filter: str
    file: str
    dir: str


class QueryMask(pydantic.BaseModel, frozen=True):
    """
    Hexadecimal bitmasks for selecting variables and levels.

    Efficient encoding of which items to include in the query.
    """

    variables: str
    levels: str


class QueryTime(pydantic.BaseModel, frozen=True):
    """Forecast run timestamp for NOAA GFS data."""

    date_utc: str  # Format: YYYYMMDD
    cycle_hour_utc: str  # Format: HH (00, 06, 12, 18)


class SelectedKeys(pydantic.BaseModel, frozen=True):
    """
    Selected keys decoded from hexadecimal mask.

    Contains all available keys, the hex mask, and URL prefix for encoding.
    """

    all_keys: list[str]
    hex_mask: str
    prefix: str


class BoundingBox(pydantic.BaseModel, frozen=True):
    """
    Geographic bounding box for data request.

    Coordinates in degrees, following NOAA API conventions.
    """

    toplat: float
    leftlon: float
    rightlon: float
    bottomlat: float


class CoreSettings(pydantic.BaseModel, frozen=True):
    """
    Core application settings from configuration.

    Loaded from settings.toml via dynaconf.
    """

    grib_url: str
    output_dir: pathlib.Path
    forecast_interval_hours: int
    max_lookback_hours: int


class LocationSettings(pydantic.BaseModel, frozen=True):
    """
    Location specified as center point + expanse.

    More intuitive than bounding box for user input.
    Converted to BoundingBox internally.
    """

    center_lat: float
    center_lon: float
    height_degrees: float
    width_degrees: float


class QueryStructure(pydantic.BaseModel, frozen=True):
    """
    Complete query configuration for NOAA API.

    Combines all parameters needed to generate query URLs.
    """

    bounding_box: BoundingBox
    query_model: QueryModel
    variables: SelectedKeys
    levels: SelectedKeys
    current_time: datetime
    settings: CoreSettings


# =============================================================================
# GEOGRAPHIC UTILITIES
# =============================================================================


def clamp_latitude(latitude: float) -> float:
    """Constrain latitude to valid range [-90, 90]."""

    return max(-90.0, min(90.0, latitude))


def normalize_longitude(longitude: float) -> float:
    """
    Normalize longitude to [0, 360) range.

    NOAA API expects 0-360 format, not -180 to 180.
    """
    normalized = longitude % 360
    return normalized if normalized >= 0 else normalized + 360


def calculate_latitude_bounds(
    center_lat: float,
    height_degrees: float,
) -> tuple[float, float]:
    """Calculate min/max latitude from center point and height."""

    half_height = height_degrees / 2
    min_lat = clamp_latitude(center_lat - half_height)
    max_lat = clamp_latitude(center_lat + half_height)
    return min_lat, max_lat


def calculate_longitude_bounds(
    center_lon: float,
    width_degrees: float,
) -> tuple[float, float]:
    """Calculate min/max longitude from center point and width."""

    normalized_longitude = normalize_longitude(center_lon)
    half_width = width_degrees / 2
    min_lon = normalize_longitude(normalized_longitude - half_width)
    max_lon = normalize_longitude(normalized_longitude + half_width)
    return min_lon, max_lon


def create_bounding_box(ls: LocationSettings) -> BoundingBox:
    """Create geographic bounding box centered on given coordinates."""

    lat_min, lat_max = calculate_latitude_bounds(ls.center_lat, ls.height_degrees)
    lon_min, lon_max = calculate_longitude_bounds(ls.center_lon, ls.width_degrees)

    return BoundingBox(
        toplat=lat_max,
        leftlon=lon_min,
        rightlon=lon_max,
        bottomlat=lat_min,
    )


# =============================================================================
# TIME UTILITIES
# =============================================================================


def format_date_utc(dt_object: datetime) -> str:
    """Format datetime as YYYYMMDD for NOAA query."""

    return dt_object.strftime("%Y%m%d")


def crop_to_hour(dt_object: datetime) -> datetime:
    """
    Round down to nearest hour.

    Removes minutes, seconds, microseconds for forecast time calculations.
    """
    return dt_object.replace(
        minute=0,
        second=0,
        microsecond=0,
    )


def get_latest_of_multiple(hour: int, qs: QueryStructure) -> int:
    """
    Round hour down to nearest forecast interval.

    E.g., if forecast_interval_hours is 6: 14 -> 12, 23 -> 18
    """
    hour_interval = qs.settings.forecast_interval_hours
    return (hour // hour_interval) * hour_interval


def get_latest_run_start(dt_object: datetime, qs: QueryStructure) -> datetime:
    """
    Round down to nearest forecast cycle.

    For GFS: runs at 00, 06, 12, 18 UTC (every 6 hours).
    Interval configured in settings.forecast_interval_hours.
    """
    process_start_hour = get_latest_of_multiple(hour=dt_object.hour, qs=qs)
    return crop_to_hour(dt_object).replace(hour=process_start_hour)


def build_qt(dt_object: datetime, qs: QueryStructure) -> QueryTime:
    """Convert datetime to NOAA query time format."""
    return QueryTime(
        date_utc=format_date_utc(dt_object=dt_object),
        cycle_hour_utc=f"{get_latest_run_start(dt_object=dt_object, qs=qs).hour:02}",
    )


def generate_qt_batch(
    reference_time: datetime,
    qs: QueryStructure,
) -> tuple[QueryTime, ...]:
    """
    Generate batch of query times to try, from most to least recent.

    Most recent forecasts are often not yet available on NOAA servers
    (processing delay). This generates fallback times going back
    max_lookback_hours in forecast_interval_hours increments.

    Special logic: if latest run started less than 3 hours ago, skip it
    since NOAA processing typically takes 3+ hours.
    """
    cropped_time = crop_to_hour(reference_time)
    latest_run_start = get_latest_run_start(cropped_time, qs)

    # Skip very recent run if it started less than 3 hours ago
    if latest_run_start + timedelta(hours=3) <= datetime.now(tz=timezone.utc):
        latest_cycle = cropped_time.replace(hour=latest_run_start.hour)
    else:
        # Too recent, try previous cycle
        latest_cycle = cropped_time.replace(
            hour=(latest_run_start - timedelta(hours=6)).hour,
        )

    return tuple(
        build_qt(dt_object=latest_cycle - timedelta(hours=offset), qs=qs)
        for offset in range(
            0,
            qs.settings.max_lookback_hours + 1,
            qs.settings.forecast_interval_hours,
        )
    )


# =============================================================================
# MASKING UTILITIES
# =============================================================================


def get_binary_mask_from_hex(hex_mask: str, mask_length: int) -> tuple[int, ...]:
    """
    Convert hexadecimal mask string to tuple of binary integers.

    E.g., "0xF" with length 4 -> (1, 1, 1, 1)
    """
    binary_string = format(int(hex_mask, base=16), "b").rjust(mask_length, "0")
    return tuple(int(value) for value in binary_string)


def get_url_encoded_keys(all_keys: list[str], hex_mask: str, prefix: str) -> str:
    """
    Convert hexadecimal mask to URL-encoded query string.

    Only includes keys where mask bit is 1. Adds prefix to each key.
    E.g., ["TMP", "UGRD"] with mask 0x3 and prefix "var_" ->
    "var_TMP=on&var_UGRD=on"
    """
    binary_mask = get_binary_mask_from_hex(hex_mask=hex_mask, mask_length=len(all_keys))
    return urlencode(
        [(f"{prefix}{key}", "on") for key, mask in zip(all_keys, binary_mask) if mask]
    )


def build_new_mask(all_values: list[str], selected_values: tuple[str, ...]) -> str:
    """
    Build hexadecimal mask from selected values.

    Inverse of reveal_masked_values. Creates mask where bit is 1
    if value is selected.
    """
    raw_mask = ["1" if key in selected_values else "0" for key in all_values]
    return hex(int("".join(raw_mask), 2))


def reveal_masked_values(all_values: list[str], hex_mask: str) -> list[str]:
    """
    Decode hexadecimal mask to list of selected values.

    Returns only values where mask bit is 1.
    """
    binary_mask = get_binary_mask_from_hex(
        hex_mask=hex_mask, mask_length=len(all_values)
    )
    return [key for key, mask in zip(all_values, binary_mask) if mask]


# =============================================================================
# QUERY BUILDING
# =============================================================================


def collect_query_arguments(qs: QueryStructure) -> tuple[str, str, str]:
    """
    Build URL query arguments from query structure.

    Returns tuple of: (variables_string, levels_string, subregion_string)
    All encoded for URL inclusion.
    """
    variables = get_url_encoded_keys(**qs.variables.model_dump())  # pyright: ignore[reportAny]
    levels = get_url_encoded_keys(**qs.levels.model_dump())  # pyright: ignore[reportAny]
    subregion = "=".join(["subregion", urlencode(query=qs.bounding_box.model_dump())])

    return variables, levels, subregion


def build_query_url(qt: QueryTime, qa: tuple[str, str, str], qs: QueryStructure) -> str:
    """
    Construct complete NOAA query URL from components.

    Combines base URI, file/dir parameters, and query arguments
    (variables, levels, subregion).
    """
    uri = qs.settings.grib_url.format(
        filter=qs.query_model.filter,
    )
    core = urlencode(
        (
            (
                "dir",
                qs.query_model.dir.format(**qt.model_dump()),  # pyright: ignore[reportAny]
            ),
            (
                "file",
                qs.query_model.file.format(**qt.model_dump()),  # pyright: ignore[reportAny]
            ),
        )
    )
    query_string = "&".join([core, *qa])
    return f"{uri}?{query_string}"


def generate_query_urls(
    qt_batch: tuple[QueryTime, ...],
    qs: QueryStructure,
) -> Generator[str, None, None]:
    """Generate query URLs in order from most to least recent."""

    for qt in qt_batch:
        qa = collect_query_arguments(qs=qs)
        yield build_query_url(qt=qt, qa=qa, qs=qs)
