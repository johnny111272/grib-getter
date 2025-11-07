# Installation

## Requirements

- Python 3.13 or higher
- Internet connection for downloading forecasts

## Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/johnny111272/grib-getter.git
cd grib-getter

# Install with uv
uv sync
```

## Using pip

```bash
# Clone the repository
git clone https://github.com/johnny111272/grib-getter.git
cd grib-getter

# Install with pip
pip install -e .
```

## First-Time Configuration

On first run, grib-getter will prompt you to configure the storage directory:

```bash
python fetch_forecast.py fetch
```

You'll be asked:

1. **Storage directory** - Where to save GRIB files (default: `./grib_data`)
2. Directory creation (if it doesn't exist)

This creates a `user.toml` file with your preferences.

## Manual Configuration

You can also configure storage directly:

```bash
python fetch_forecast.py configure --storage ~/weather/grib_data
```

Or edit `user.toml` manually:

```toml
[core_settings]
output_dir = "/path/to/your/grib_data"
```

## Verifying Installation

Check that everything works:

```bash
python fetch_forecast.py list-presets
```

You should see:

```
Available Query Presets:

  • sailing_basic
```

## Next Steps

- [Quick Start Guide](quickstart.md) - Learn basic usage
- [Configuration](configuration.md) - Customize settings
