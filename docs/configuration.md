# Configuration

grib-getter uses a layered configuration system powered by [Dynaconf](https://www.dynaconf.com/).

## Configuration Files

### `settings.toml` (Application Defaults)

Version-controlled defaults that ship with the application:

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

### `user.toml` (User Preferences)

User-specific configuration (gitignored, auto-created):

```toml
[core_settings]
output_dir = "/Users/johnny/weather/grib_data"
```

### `settings/*.toml` (Model Configs)

Model-specific configurations are auto-discovered from the `settings/` directory.

**Current models:**
- `settings/gfs.toml` - Global Forecast System

**Future models:**
Add a new file and it's automatically loaded!
- `settings/nam.toml` - North American Mesoscale
- `settings/hrrr.toml` - High-Resolution Rapid Refresh

## Configuration Priority

Settings are loaded in order (later files override earlier):

1. `settings.toml` - Application defaults
2. `user.toml` - User overrides
3. `.secrets.toml` - Secrets (if present)
4. `settings/*.toml` - Model configs (auto-discovered)
5. Environment variables - `DYNACONF_*` prefix

Example:
```bash
# Override output_dir via environment variable
export DYNACONF_CORE_SETTINGS__OUTPUT_DIR=/tmp/grib_data
python fetch_forecast.py fetch -p sailing_basic
```

## Storage Configuration

### Via CLI

```bash
# Interactive
python fetch_forecast.py configure

# Direct
python fetch_forecast.py configure --storage /path/to/grib_data
```

### Via File

Edit `user.toml`:

```toml
[core_settings]
output_dir = "/path/to/grib_data"
```

### Via Environment

```bash
export DYNACONF_CORE_SETTINGS__OUTPUT_DIR=/path/to/grib_data
```

## Location Defaults

Change default location in `user.toml`:

```toml
[default_location]
center_lat = 37.7749  # San Francisco
center_lon = -122.4194
height_degrees = 60.0
width_degrees = 120.0
```

## Retry Settings

Adjust retry behavior in `user.toml`:

```toml
[retry_settings]
max_attempts = 5  # More retries for unreliable connections
initial_delay_seconds = 10
max_delay_seconds = 600
timeout_minutes = 60
```

## HTTP Settings

Customize timeouts:

```toml
[http_settings]
request_timeout_seconds = 60  # Longer timeout for slow connections
```

## Backup Settings

Control backup behavior:

```toml
[backup]
max_count = 50  # Fewer backups to save space
extension = ".backup"  # Different extension
```

## Model Configuration

See [Adding Models](adding_models.md) for details on adding new forecast models.

## Configuration Validation

Settings are validated using Pydantic models, ensuring type safety and catching errors early.

If you have an invalid configuration:

```
ValidationError: 1 validation error for CoreSettings
forecast_interval_hours
  Input should be a valid integer [type=int_type, input_value='six', input_type=str]
```

## Next Steps

- [Architecture](architecture.md) - How configuration system works
- [Adding Models](adding_models.md) - Extend with new models
