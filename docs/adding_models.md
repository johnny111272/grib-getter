# Adding New Models

grib-getter is designed for easy extensibility. Add new forecast models by creating a TOML file - no code changes required!

## Quick Start

To add a new model (e.g., NAM):

1. Create `settings/nam.toml`
2. Copy structure from `settings/gfs.toml`
3. Update with NAM-specific config
4. Done! Auto-discovered and loaded

## Model Configuration Structure

Each model TOML file has four sections:

### 1. `[{model}_data]` - Available Options

Lists all variables and levels the model provides:

```toml
[nam_data]
variables = [
    "TMP",      # Temperature
    "UGRD",     # U-component of wind
    "VGRD",     # V-component of wind
    "PRMSL",    # Pressure reduced to MSL
    # ... full list
]
levels = [
    "surface",
    "2_m_above_ground",
    "10_m_above_ground",
    "1000_mb",
    # ... full list
]
```

### 2. `[{model}_queries]` - Query Presets

Named presets for common use cases:

```toml
[nam_queries.sailing_basic]
variables = "0x204000014400110280"  # Hex bitmask
levels = "0x18000000000000001000000"  # Hex bitmask

[nam_queries.aviation_complete]
variables = "0xFFFFFFFFFFFFFFFFFF"
levels = "0xFFFFFFFFFFFFFFFFFF"
```

**Bitmask Encoding:**
Each bit position corresponds to a variable/level:

```
Position:  0    1    2    3    4    ...
Variable:  TMP  UGRD VGRD PRES HGHT ...
Mask:      1    1    0    1    0    ...
           ↑    ↑    ↑    ↑    ↑
         Include these, skip VGRD and HGHT
```

Convert binary to hex: `0b11010... = 0x1A...`

### 3. `[{model}_products]` - Download Products

Different resolution/processing variants:

```toml
[nam_products.nam_12km]
name = "nam_12km"
filter = "filter_nam_12.pl"
file = "nam.t{cycle_hour_utc}z.awphys{forecast_hour}.tm00.grib2"
dir = "/nam.{date_utc}"

[nam_products.nam_32km]
name = "nam_32km"
filter = "filter_nam_32.pl"
file = "nam.t{cycle_hour_utc}z.awphys{forecast_hour}.tm00.grib2"
dir = "/nam.{date_utc}"
```

### 4. `[{model}_settings]` - Model-Specific Settings (Optional)

Additional model-specific configuration:

```toml
[nam_settings]
forecast_interval_hours = 3  # NAM runs every 3 hours
max_forecast_hours = 84      # NAM provides 84-hour forecasts
```

## Complete Example: Adding NAM

**File:** `settings/nam.toml`

```toml
[nam_products.nam_12km]
name = "nam_12km"
filter = "filter_nam_12.pl"
file = "nam.t{cycle_hour_utc}z.awphys00.tm00.grib2"
dir = "/nam.{date_utc}"

[nam_queries.sailing_basic]
variables = "0x204000014400110280"
levels = "0x18000000000000001000000"

[nam_queries.conus_weather]
variables = "0x3FFFFFFFFFFFFF"
levels = "0x1FFFFFFFFFFFF"

[nam_data]
variables = [
    "TMP",
    "UGRD",
    "VGRD",
    "PRMSL",
    "APCP",
    "TCDC",
    "RH",
    "DPT",
    # ... add all NAM variables
]
levels = [
    "surface",
    "2_m_above_ground",
    "10_m_above_ground",
    "850_mb",
    "700_mb",
    "500_mb",
    # ... add all NAM levels
]

[nam_settings]
forecast_interval_hours = 3
max_forecast_hours = 84
```

## CLI Integration

After creating the TOML file, the model is automatically available but not yet integrated into the CLI menu.

**Future CLI Update** (manual code change required):

```python
# In fetch_forecast.py - when multi-model selection is added
available_models = list(settings.keys())  # Auto-discovers NAM
```

For now, update the CLI to reference the new model explicitly:

```python
# Change hardcoded "GFS" references to support NAM
model_name = settings.defaults.model_name  # Could be NAM
```

## Testing New Model

Test the configuration loads correctly:

```python
from config import settings

# Check NAM data loaded
print(hasattr(settings, 'NAM_DATA'))  # Should be True
print(len(settings.NAM_DATA.variables))

# Check NAM queries loaded
print('sailing_basic' in settings.NAM_QUERIES)

# Check NAM products loaded
print(hasattr(settings.NAM_PRODUCTS, 'nam_12km'))
```

## Finding Model Information

### NOAA Documentation

- [NOMADS Data Access](https://nomads.ncep.noaa.gov/)
- [GRIB Filter Scripts](https://nomads.ncep.noaa.gov/cgi-bin/)
- Model-specific pages (e.g., NAM, HRRR, RAP)

### Inspecting Existing GRIB Filters

Visit NOAA's filter pages to see available variables and levels:

```
https://nomads.ncep.noaa.gov/cgi-bin/filter_nam.pl
```

Check the HTML source for the complete list.

### Testing URLs

Manually construct and test URLs:

```bash
curl "https://nomads.ncep.noaa.gov/cgi-bin/filter_nam.pl?dir=/nam.20251106&file=nam.t12z.awphys00.tm00.grib2&var_TMP=on&lev_surface=on&subregion=&toplat=50&leftlon=-100&rightlon=-80&bottomlat=40"
```

## Common Patterns

### High-Resolution Regional Models

Models like NAM, HRRR, RAP:

- Smaller geographic areas
- Higher resolution
- More frequent updates
- Shorter forecast horizons

```toml
[hrrr_settings]
forecast_interval_hours = 1  # Hourly updates
max_forecast_hours = 18      # 18-hour forecasts
```

### Global Models

Models like GFS, ECMWF:

- Global coverage
- Lower resolution
- Longer forecast horizons
- Less frequent updates

```toml
[gfs_settings]
forecast_interval_hours = 6   # Every 6 hours
max_forecast_hours = 384      # 16-day forecasts
```

## Bitmask Generation

### Manual Method

1. List all variables in order
2. Mark which ones to include (1) or exclude (0)
3. Convert binary string to hex

```python
variables = ["TMP", "UGRD", "VGRD", "PRES", "RH"]
selected = [True, True, False, True, False]
binary = "11010"  # LSB first
hex_mask = hex(int(binary, 2))  # "0x1a"
```

### Using Helper Function

```python
from noaa_query_builder import build_new_mask

all_vars = ["TMP", "UGRD", "VGRD", "PRES", "RH"]
selected_vars = ("TMP", "UGRD", "PRES")
mask = build_new_mask(all_vars, selected_vars)
print(mask)  # "0x1a"
```

## Next Steps

- [Configuration](configuration.md) - Learn about config system
- [Architecture](architecture.md) - Understand how it works
- [API Reference](api/query_builder.md) - Query builder functions
