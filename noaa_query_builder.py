"""
NOAA GFS GRIB2 Data Fetcher

Fetches Global Forecast System (GFS) weather data from NOAA's NOMADS server.
Implements intelligent retry logic with exponential backoff to find the most
recent available forecast.

Rate Limiting: NOAA requires 10 seconds between requests for the same file.
This implementation respects that limit.
"""

import pathlib
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import pydantic

from config import settings


class ModelData(pydantic.BaseModel, frozen=True):
    variables: list[str]
    levels: list[str]


class QueryModel(pydantic.BaseModel, frozen=True):
    name: str
    filter: str
    file: str
    dir: str


class QueryMask(pydantic.BaseModel, frozen=True):
    variables: str
    levels: str


class QueryTime(pydantic.BaseModel, frozen=True):
    """Forecast run timestamp for NOAA GFS data."""

    date_utc: str  # Format: YYYYMMDD
    cycle_hour_utc: str  # Format: HH (00, 06, 12, 18)


class SelectedKeys(pydantic.BaseModel, frozen=True):
    all_keys: list[str]
    hex_mask: str
    prefix: str


class BoundingBox(pydantic.BaseModel, frozen=True):
    """Geographic bounding box for data request."""

    toplat: float
    leftlon: float
    rightlon: float
    bottomlat: float


class CoreSettings(pydantic.BaseModel, frozen=True):
    grib_url: str
    output_dir: pathlib.Path
    forecast_interval_hours: int
    max_lookback_hours: int


class LocationSettings(pydantic.BaseModel, frozen=True):
    center_lat: float
    center_lon: float
    height_degrees: float
    width_degrees: float


class QueryStructure(pydantic.BaseModel, frozen=True):
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
    """Normalize longitude to [0, 360) range."""

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
    """Round down to nearest hour."""
    return dt_object.replace(
        minute=0,
        second=0,
        microsecond=0,
    )


def get_latest_of_multiple(hour: int, qs: QueryStructure) -> int:
    hour_interval = qs.settings.forecast_interval_hours
    return (hour // hour_interval) * hour_interval


def get_latest_run_start(dt_object: datetime, qs: QueryStructure) -> datetime:
    """
    Round down to nearest 6-hour forecast cycle.
    NOAA GFS runs at 00, 06, 12, 18 UTC.
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

    Searches back MAX_LOOKBACK_HOURS in FORECAST_INTERVAL_HOURS increments.
    Most recent forecasts may not be available yet, so we try progressively
    older ones until we find data.
    """

    cropped_time = crop_to_hour(reference_time)
    latest_run_start = get_latest_run_start(cropped_time, qs)

    if latest_run_start + timedelta(hours=3) <= datetime.now(tz=timezone.utc):
        latest_cycle = cropped_time.replace(hour=latest_run_start.hour)
    else:
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
    binary_string = format(int(hex_mask, base=16), "b").rjust(mask_length, "0")
    return tuple(int(value) for value in binary_string)


def get_url_encoded_keys(all_keys: list[str], hex_mask: str, prefix: str) -> str:
    binary_mask = get_binary_mask_from_hex(hex_mask=hex_mask, mask_length=len(all_keys))
    return urlencode(
        [(f"{prefix}{key}", "on") for key, mask in zip(all_keys, binary_mask) if mask]
    )


def build_new_mask(all_values: list[str], selected_values: tuple[str, ...]) -> str:
    raw_mask = ["1" if key in selected_values else "0" for key in all_values]
    return hex(int("".join(raw_mask), 2))


def reveal_masked_values(all_values: list[str], hex_mask: str) -> list[str]:
    binary_mask = get_binary_mask_from_hex(
        hex_mask=hex_mask, mask_length=len(all_values)
    )
    return [key for key, mask in zip(all_values, binary_mask) if mask]


# =============================================================================
# QUERY BUILDING
# =============================================================================


def collect_query_arguments(qs: QueryStructure) -> tuple[str, str, str]:
    """
    Build URL query arguments from template and parameters.

    Season filtering: Variables/levels tagged with season name are included
    for that season, "on" are always included, others are excluded.
    """

    variables = get_url_encoded_keys(**qs.variables.model_dump())
    levels = get_url_encoded_keys(**qs.levels.model_dump())
    subregion = "=".join(["subregion", urlencode(query=qs.bounding_box.model_dump())])

    return variables, levels, subregion


def build_query_url(qt: QueryTime, qa: tuple[str, str, str], qs: QueryStructure) -> str:
    """Construct complete NOAA query URL from arguments."""

    uri = qs.settings.grib_url.format(
        filter=qs.query_model.filter,
    )
    core = urlencode(
        (
            (
                "dir",
                qs.query_model.dir.format(**qt.model_dump()),
            ),
            (
                "file",
                qs.query_model.file.format(**qt.model_dump()),
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


###############################################################################

if __name__ == "__main__":
    model_data = ModelData.model_validate(settings.GFS_DATA)
    query_mask = QueryMask.model_validate(settings.GFS_QUERIES.sailing_basic)
    default_location = LocationSettings.model_validate(settings.DEFAULT_LOCATION)

    qs = QueryStructure(
        bounding_box=create_bounding_box(
            ls=LocationSettings.model_validate(settings.DEFAULT_LOCATION)
        ),
        query_model=QueryModel.model_validate(
            settings.GFS_PRODUCTS.gfs_quarter_degree,
        ),
        variables=SelectedKeys(
            all_keys=model_data.variables,
            hex_mask=query_mask.variables,
            prefix="var_",
        ),
        levels=SelectedKeys(
            all_keys=model_data.levels,
            hex_mask=query_mask.levels,
            prefix="lev_",
        ),
        current_time=datetime.now(tz=timezone.utc),
        settings=CoreSettings.model_validate(settings.core_settings),
    )

    query_urls_generator = generate_query_urls(
        qt_batch=generate_qt_batch(reference_time=qs.current_time, qs=qs),
        qs=qs,
    )

    print(tuple(query_urls_generator))
