# grib-getter

Bandwidth-optimized GRIB weather data fetcher for NOAA GFS forecasts.

Designed for bandwidth-limited environments (like sailboat liveaboards) with intelligent download management and automatic data integrity protection.

## Features

- **Smart Download Management**: Checks for existing files before downloading
- **Bandwidth Optimization**: `--new-only`, `--force`, and `--check-only` modes
- **Automatic Backups**: Creates `.bak` files before overwriting to prevent data loss
- **Interactive CLI**: Built with Typer for excellent user experience
- **Configurable Storage**: Set custom storage paths for GRIB files
- **First-Run Setup**: Automatic configuration on first use

## Installation

```bash
# Clone the repository
git clone https://github.com/johnny111272/weather-model.git
cd weather-model

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

## Quick Start

### First-Time Configuration

On first run, grib-getter will prompt you to configure the storage directory:

```bash
python fetch_forecast.py fetch
```

Or configure manually:

```bash
python fetch_forecast.py configure --storage /path/to/grib_data
```

### Basic Usage

```bash
# Interactive mode (prompts for options)
python fetch_forecast.py fetch

# Non-interactive with all options
python fetch_forecast.py fetch -p sailing_basic --lat 45 --lon -93 --height 90 --width 180

# List available query presets
python fetch_forecast.py list-presets
```

### Bandwidth-Saving Options

```bash
# Only download if file doesn't exist (perfect for automated scripts)
python fetch_forecast.py fetch -p sailing_basic --new-only

# Check what's available without downloading
python fetch_forecast.py fetch -p sailing_basic --check-only

# Force download even if file exists
python fetch_forecast.py fetch -p sailing_basic --force
```

## Configuration

### Storage Path

Configure where GRIB files are stored:

```bash
# Interactive configuration
python fetch_forecast.py configure

# Direct configuration
python fetch_forecast.py configure --storage ~/weather/grib_data
```

To reconfigure, simply delete `output_dir` from `settings.toml` or run `configure` again.

### Location Defaults

Edit `settings.toml` to change default location:

```toml
[default_location]
center_lat = 45.0
center_lon = -93.0
height_degrees = 90.0
width_degrees = 180.0
```

### Query Presets

Query presets are defined in `gfs.toml`. Currently available:
- `sailing_basic`: Essential marine weather variables

## File Naming

Downloaded files follow the pattern: `YYYYMMDD_HH_product.grib`

Examples:
- `20251106_06_gfs_quarter_degree.grib` - GFS 0.25° from 2025-11-06 06Z
- `20251106_12_gfs_quarter_degree.grib` - GFS 0.25° from 2025-11-06 12Z

## Backup Protection

When overwriting existing files, grib-getter automatically creates backups:
- `20251106_12_gfs_quarter_degree.grib.00.bak` (first backup)
- `20251106_12_gfs_quarter_degree.grib.01.bak` (second backup)
- etc.

This prevents data loss from corrupted downloads in unreliable connectivity environments.

## Development

Built with:
- Python 3.13+
- Typer (CLI)
- Rich (terminal formatting)
- Dynaconf (settings management)
- httpx (HTTP client)
- Pydantic & msgspec (data validation)

## Documentation

See `project_preferences.md` for detailed architecture and expansion plans.

## License

MIT

## Author

Johnny (@johnny111272)
