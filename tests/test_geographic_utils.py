"""
Tests for geographic utility functions.

These are pure functions that transform coordinates - perfect for learning testing!
"""

from noaa_query_builder import (
    calculate_latitude_bounds,
    calculate_longitude_bounds,
    clamp_latitude,
    normalize_longitude,
)


# =============================================================================
# LATITUDE TESTS
# =============================================================================


def test_clamp_latitude_within_range():
    """Latitude already in valid range should pass through unchanged."""
    assert clamp_latitude(0.0) == 0.0
    assert clamp_latitude(45.0) == 45.0
    assert clamp_latitude(-45.0) == -45.0


def test_clamp_latitude_at_boundaries():
    """Latitude at exact boundaries should pass through unchanged."""
    assert clamp_latitude(90.0) == 90.0
    assert clamp_latitude(-90.0) == -90.0


def test_clamp_latitude_above_max():
    """Latitude above 90 should be clamped to 90."""
    assert clamp_latitude(100.0) == 90.0
    assert clamp_latitude(91.0) == 90.0


def test_clamp_latitude_below_min():
    """Latitude below -90 should be clamped to -90."""
    assert clamp_latitude(-100.0) == -90.0
    assert clamp_latitude(-91.0) == -90.0


# =============================================================================
# LONGITUDE TESTS
# =============================================================================


def test_normalize_longitude_already_in_range():
    """Longitude already in [0, 360) should pass through unchanged."""
    assert normalize_longitude(0.0) == 0.0
    assert normalize_longitude(180.0) == 180.0
    assert normalize_longitude(359.0) == 359.0


def test_normalize_longitude_negative():
    """Negative longitude should be converted to 0-360 range."""
    assert normalize_longitude(-180.0) == 180.0
    assert normalize_longitude(-1.0) == 359.0
    assert normalize_longitude(-90.0) == 270.0


def test_normalize_longitude_above_360():
    """Longitude above 360 should wrap around."""
    assert normalize_longitude(361.0) == 1.0
    assert normalize_longitude(720.0) == 0.0


# =============================================================================
# BOUNDING BOX CALCULATION TESTS
# =============================================================================


def test_calculate_latitude_bounds_simple():
    """Calculate latitude bounds from center and height."""
    min_lat, max_lat = calculate_latitude_bounds(center_lat=0.0, height_degrees=10.0)
    assert min_lat == -5.0
    assert max_lat == 5.0


def test_calculate_latitude_bounds_clamped_at_poles():
    """Latitude bounds should be clamped at poles."""
    # Near north pole
    min_lat, max_lat = calculate_latitude_bounds(center_lat=85.0, height_degrees=20.0)
    assert min_lat == 75.0
    assert max_lat == 90.0  # Clamped at north pole

    # Near south pole
    min_lat, max_lat = calculate_latitude_bounds(center_lat=-85.0, height_degrees=20.0)
    assert min_lat == -90.0  # Clamped at south pole
    assert max_lat == -75.0


def test_calculate_longitude_bounds_simple():
    """Calculate longitude bounds from center and width."""
    min_lon, max_lon = calculate_longitude_bounds(center_lon=0.0, width_degrees=10.0)
    assert min_lon == 355.0  # 0 - 5 = -5, normalized to 355
    assert max_lon == 5.0


def test_calculate_longitude_bounds_wraps_at_antimeridian():
    """Longitude bounds should wrap at 0/360 boundary."""
    min_lon, max_lon = calculate_longitude_bounds(center_lon=350.0, width_degrees=20.0)
    assert min_lon == 340.0
    assert max_lon == 0.0  # 350 + 10 = 360, normalized to 0
