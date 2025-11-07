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
git clone https://github.com/johnny111272/grib-getter.git
cd grib-getter

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

To reconfigure, simply delete `output_dir` from `user.toml` or run `configure` again.

### Location Defaults

Edit `user.toml` to change default location:

```toml
[default_location]
center_lat = 45.0
center_lon = -93.0
height_degrees = 90.0
width_degrees = 180.0
```

See the [Configuration Guide](https://johnny111272.github.io/grib-getter/configuration/) for all available settings.

### Query Presets

Query presets are defined in `settings/gfs.toml`. Currently available:
- `sailing_basic`: Essential marine weather variables

See [Adding Models](https://johnny111272.github.io/grib-getter/adding_models/) to learn how to add new models and presets.

## File Organization

Downloaded files are organized in run-specific folders:

```
grib_data/
└── 20251106_18_GFS_sailing_basic/
    └── 20251106_18_000_GFS_sailing_basic.grib
```

Pattern: `YYYYMMDD_HH_{model}_{preset}/YYYYMMDD_HH_FFF_{model}_{preset}.grib`

Where:
- `YYYYMMDD` - Forecast run date
- `HH` - Forecast cycle hour (00, 06, 12, 18 for GFS)
- `FFF` - Forecast hour (000 for analysis file, 001, 006, etc.)
- `{model}` - Model name (GFS)
- `{preset}` - Query preset (sailing_basic)

## Backup Protection

When overwriting existing files, grib-getter automatically creates backups:
- `20251106_18_000_GFS_sailing_basic.grib.00.bak` (first backup)
- `20251106_18_000_GFS_sailing_basic.grib.01.bak` (second backup)
- etc.

This prevents data loss from corrupted downloads in unreliable connectivity environments.

## Documentation

Comprehensive documentation is available at: https://johnny111272.github.io/grib-getter/

Or build and serve locally:

```bash
# Install documentation dependencies
uv sync --extra docs

# Serve documentation locally (with live reload)
uv run mkdocs serve

# Build static documentation
uv run mkdocs build
```

Documentation includes:
- [Installation Guide](https://johnny111272.github.io/grib-getter/installation/)
- [Quick Start](https://johnny111272.github.io/grib-getter/quickstart/)
- [Configuration Reference](https://johnny111272.github.io/grib-getter/configuration/)
- [Architecture Overview](https://johnny111272.github.io/grib-getter/architecture/)
- [Adding New Models](https://johnny111272.github.io/grib-getter/adding_models/)
- [API Reference](https://johnny111272.github.io/grib-getter/api/cli/)

## Development

Built with:
- Python 3.13+
- Typer (CLI)
- Rich (terminal formatting)
- Loguru (logging)
- Dynaconf (configuration management)
- httpx (HTTP client)
- Pydantic (data validation)

## License

MIT

## Author

Johnny (@johnny111272)
