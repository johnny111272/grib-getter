# Quick Start

## Basic Usage

### Interactive Mode

The simplest way to use grib-getter:

```bash
python fetch_forecast.py fetch
```

You'll be prompted for:

- Query preset (e.g., `sailing_basic`)
- Location (latitude, longitude, area size)

### Non-Interactive Mode

For automation or scripting:

```bash
python fetch_forecast.py fetch \
  -p sailing_basic \
  --lat 45 \
  --lon -93 \
  --height 90 \
  --width 180
```

## Bandwidth-Saving Options

### Check Only

See what's available without downloading:

```bash
python fetch_forecast.py fetch -p sailing_basic --check-only
```

Output:
```
Target file: 20251106_18_000_GFS_sailing_basic.grib
Status: File does not exist locally
```

### New Only

Only download if file doesn't exist (perfect for cron jobs):

```bash
python fetch_forecast.py fetch -p sailing_basic --new-only
```

If file exists:
```
File exists and --new-only specified. Skipping download.
Using existing file: /path/to/20251106_18_000_GFS_sailing_basic.grib
```

### Force Download

Download even if file exists (creates backup first):

```bash
python fetch_forecast.py fetch -p sailing_basic --force
```

Output:
```
Backing up existing file...
  Created backup: 20251106_18_000_GFS_sailing_basic.grib.00.bak
Fetching data...
✓ Success! Downloaded 1,234,567 bytes in 2.3s
```

## File Organization

Downloaded files are organized by run:

```
grib_data/
└── 20251106_18_GFS_sailing_basic/
    └── 20251106_18_000_GFS_sailing_basic.grib
```

Format: `YYYYMMDD_HH_FFF_{model}_{preset}.grib`

- `YYYYMMDD` - Forecast run date
- `HH` - Forecast cycle hour (00, 06, 12, 18 for GFS)
- `FFF` - Forecast hour (000 for analysis file)
- `{model}` - Model name (GFS)
- `{preset}` - Query preset (sailing_basic)

## Available Presets

List all available query presets:

```bash
python fetch_forecast.py list-presets
```

Currently available:

- **sailing_basic** - Essential marine weather variables (wind, pressure, temperature, waves)

## Configuration

Change storage location:

```bash
python fetch_forecast.py configure --storage ~/weather
```

## Common Workflows

### Daily Automated Fetch

For a cron job that downloads once per day:

```bash
0 8 * * * cd /path/to/grib-getter && python fetch_forecast.py fetch -p sailing_basic --new-only
```

### Pre-Departure Check

Before setting sail, check and download latest:

```bash
# Check what's available
python fetch_forecast.py fetch -p sailing_basic --check-only

# Download if needed
python fetch_forecast.py fetch -p sailing_basic
```

### Bandwidth-Constrained Update

When bandwidth is expensive:

```bash
# Check first
python fetch_forecast.py fetch -p sailing_basic --check-only

# Only download if doesn't exist
python fetch_forecast.py fetch -p sailing_basic --new-only
```

## Next Steps

- [Configuration Guide](configuration.md) - Customize settings
- [Architecture](architecture.md) - How it works
- [API Reference](api/cli.md) - Detailed documentation
