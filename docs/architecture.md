# Architecture

## Overview

grib-getter is designed around three core principles:

1. **Bandwidth Optimization** - Minimize downloads in limited connectivity
2. **Data Integrity** - Protect against corrupted downloads
3. **Extensibility** - Easy to add new models via configuration

## Data Flow

```
User Input (CLI)
    ↓
Configuration Loading (dynaconf)
    ↓
Query URL Generation (noaa_query_builder.py)
    ↓
HTTP Fetching with Retry (noaa_grib_fetcher.py)
    ↓
GRIB2 File (grib_data/YYYYMMDD_HH_model_preset/)
```

## Component Architecture

### CLI Layer (`fetch_forecast.py`)

**Responsibilities:**
- User interaction (Typer + Rich)
- First-run configuration
- Bandwidth control flags (`--new-only`, `--force`, `--check-only`)
- Backup file management

**Key Features:**
- Interactive prompts with sensible defaults
- Non-interactive mode for automation
- Logging with rich handler (loguru + rich)

### Query Builder (`noaa_query_builder.py`)

**Responsibilities:**
- Convert user input to NOAA API URLs
- Forecast time calculations (with lookback)
- Geographic bounding box calculations
- Variable/level selection via hexadecimal bitmasks

**Key Concepts:**

**Bitmask Selection:**
Variables and levels are selected using hexadecimal bitmasks for efficient encoding:

```python
# All available variables
variables = ["TMP", "UGRD", "VGRD", "PRMSL", ...]

# Hex mask: which ones to include?
hex_mask = "0x204000014400110280"

# Decoded to binary, selects specific variables
# Bit 1 = include, Bit 0 = exclude
```

**Forecast Time Lookback:**
Most recent forecasts aren't immediately available on NOAA servers (processing delay). The query builder generates multiple candidate times:

```python
# Try: 18Z, 12Z, 06Z (today)
# Looking back up to max_lookback_hours
```

### Fetcher (`noaa_grib_fetcher.py`)

**Responsibilities:**
- HTTP requests with retry logic
- Exponential backoff on failures
- NOAA rate limiting (10s between requests)
- Comprehensive attempt tracking

**Retry Strategy:**

```
For each forecast time (newest to oldest):
    For each attempt (up to max_attempts):
        Try to fetch
        If 404: Try next (older) forecast time
        If 5xx: Retry same URL with backoff
        If success: Done!
```

**Rate Limiting:**
NOAA requires 10 seconds between requests. The fetcher automatically handles this:

```python
if not first_url:
    time.sleep(settings.noaa_settings.rate_limit_seconds)
```

### Configuration (`config.py`)

**Responsibilities:**
- Load and merge configuration files
- Auto-discover model configs in `settings/`
- Provide type-safe access to settings

**Configuration Merging:**

```python
settings = Dynaconf(
    settings_files=[
        "settings.toml",      # Defaults
        "user.toml",          # User overrides
        ".secrets.toml",      # Secrets
        "settings/*.toml",    # Auto-discovered models
    ],
    merge_enabled=True,  # Merge [core_settings] across files
)
```

## File Organization

### Run-Specific Folders

Files are organized by forecast run:

```
grib_data/
└── 20251106_18_GFS_sailing_basic/
    ├── 20251106_18_000_GFS_sailing_basic.grib  (analysis)
    ├── 20251106_18_001_GFS_sailing_basic.grib  (1-hour forecast)
    ├── 20251106_18_006_GFS_sailing_basic.grib  (6-hour forecast)
    └── ...
```

**Benefits:**
- Easy to identify complete vs partial downloads
- Natural sorting by forecast hour
- Supports future batch downloading
- Atomic operations (all files from same run)

### Backup Protection

When overwriting existing files:

```
20251106_18_000_GFS_sailing_basic.grib      (current)
20251106_18_000_GFS_sailing_basic.grib.00.bak
20251106_18_000_GFS_sailing_basic.grib.01.bak
...
```

**Why:** In unreliable connectivity, a corrupted download shouldn't destroy good data from earlier successful downloads.

## Configuration System

### Layered Configuration

```
settings.toml          (shipped defaults)
    ↓ merged with
user.toml              (user preferences)
    ↓ merged with
.secrets.toml          (API keys)
    ↓ merged with
settings/gfs.toml      (GFS model config)
    ↓ merged with
settings/nam.toml      (NAM model config - auto-discovered)
    ↓
Final Settings Object
```

### Auto-Discovery

Glob pattern `settings/*.toml` enables zero-code-change extensibility:

```bash
# Add NAM model
$ cp settings/gfs.toml settings/nam.toml
# Edit nam.toml with NAM-specific config
# That's it! Automatically loaded
```

## Data Validation

All configuration and data structures use Pydantic for validation:

```python
class CoreSettings(pydantic.BaseModel, frozen=True):
    grib_url: str
    output_dir: pathlib.Path
    forecast_interval_hours: int
    max_lookback_hours: int
```

**Benefits:**
- Type safety throughout
- Early error detection
- Self-documenting via type hints
- Auto-generated from docstrings (this documentation!)

## Future Extensions

### Async Batch Downloading (Planned)

Current structure supports future async batch downloads:

1. Download analysis file (000) to confirm run exists
2. Launch async downloads for all forecast hours
3. All saved to same run-specific folder

File naming already supports this:
- `YYYYMMDD_HH_000_model_preset.grib` (analysis)
- `YYYYMMDD_HH_FFF_model_preset.grib` (forecasts)

## Design Patterns

### Functional Core, Imperative Shell

- **Core:** Pure functions for calculations (geographic, time, masking)
- **Shell:** I/O operations (HTTP, file writes, user interaction)

### Configuration-Driven

- New models: add TOML file
- New query presets: edit model TOML
- No code changes required for common extensions

### Type-Safe Throughout

- Pydantic models for validation
- Extensive type annotations
- basedpyright for static checking

## Next Steps

- [Adding Models](adding_models.md) - Add new forecast models
- [API Reference](api/cli.md) - Detailed API documentation
