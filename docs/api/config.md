# Configuration Reference

Configuration management with Dynaconf.

## Settings Object

The `settings` object provides access to all configuration values loaded from:

- `settings.toml` - Application defaults (version controlled)
- `user.toml` - User-specific config (gitignored)
- `.secrets.toml` - Secrets (gitignored)
- `settings/*.toml` - Model configs (auto-discovered)

## Usage

```python
from config import settings

# Access core settings
output_dir = settings.core_settings.output_dir
grib_url = settings.core_settings.grib_url

# Access GFS model data
variables = settings.GFS_DATA.variables
levels = settings.GFS_DATA.levels

# Access GFS queries
sailing_vars = settings.GFS_QUERIES.sailing_basic.variables
sailing_levels = settings.GFS_QUERIES.sailing_basic.levels

# Access GFS products
product_info = settings.GFS_PRODUCTS.gfs_quarter_degree
```

## Configuration Sections

### Core Settings

::: config
    options:
      show_root_heading: false
      members:
        - settings

## Configuration Files

### settings.toml

Application defaults (version controlled):

```toml
[core_settings]
grib_url = "https://nomads.ncep.noaa.gov/cgi-bin/{filter}"
forecast_interval_hours = 6
max_lookback_hours = 18

[http_settings]
success = 200
not_found = 404
server_error = 500
request_timeout_seconds = 30

[noaa_settings]
rate_limit_seconds = 10

[retry_settings]
max_attempts = 3
initial_delay_seconds = 5
max_delay_seconds = 300
timeout_minutes = 30

[default_location]
center_lat = 45.0
center_lon = -93.0
height_degrees = 90.0
width_degrees = 180.0

[defaults]
grib_dir = "grib_data"
model_name = "GFS"
product_name = "gfs_quarter_degree"

[backup]
max_count = 100
extension = ".bak"

[query]
var_prefix = "var_"
lev_prefix = "lev_"
```

### user.toml

User-specific configuration (gitignored, auto-created):

```toml
[core_settings]
output_dir = "/path/to/grib_data"
```

### settings/gfs.toml

GFS model configuration (auto-discovered):

See [Adding Models](../adding_models.md) for structure and examples.

## Environment Variables

Override any setting with environment variables using `DYNACONF_` prefix:

```bash
export DYNACONF_CORE_SETTINGS__OUTPUT_DIR=/tmp/grib_data
export DYNACONF_RETRY_SETTINGS__MAX_ATTEMPTS=5
```

## Configuration Merging

Dynaconf merges nested dictionaries from all configuration files. Later files override earlier ones:

1. `settings.toml` (defaults)
2. `user.toml` (overrides)
3. `.secrets.toml` (overrides)
4. `settings/*.toml` (model-specific, merged)
5. Environment variables (highest priority)
