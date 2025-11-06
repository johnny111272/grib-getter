# Weather Model Project Documentation

## About This Document
**PURPOSE**: Documents project-specific behaviors, architecture decisions, and expansion patterns for the weather data fetcher.

**SCOPE**: This is project-specific documentation. General programming preferences are in `programmer_preferences.md`.

---

## Architecture Overview

This project fetches weather forecast data from various numerical weather prediction models (currently NOAA). The architecture is designed for extensibility as new models and products are added.

## Configuration Structure

### Model Configuration Pattern

Each forecast model has its own TOML configuration file (e.g., `gfs.toml`). This pattern will be followed for all future models.

#### Configuration Sections

**`[{model}_data]`** - Contains all selectable download options
- Lists all available variables (e.g., temperature, wind, precipitation)
- Lists all available vertical levels (e.g., surface, 10m above ground, pressure levels)
- These are the complete set of options the model provides

**`[{model}_queries]`** - Query presets/recipes
- Named presets for common use cases (e.g., `sailing_basic`, `aviation_complete`)
- Each preset contains bitmasks (hex strings) that select subsets from `{model}_data`
- Bitmasks are run against the data lists to efficiently encode selections
- Allows users to quickly select common variable/level combinations

**`[{model}_products]`** - Available download products
- Different resolution/processing variants of the same model
- Example: GFS offers 0.25°, 0.5°, 1° grid spacing products
- Each product has its own URL pattern, file naming convention, and directory structure

**`[{model}_settings]`** - (Future) Model-specific settings
- Reserved for other model-specific configuration that doesn't fit above categories
- Not currently used but available for future expansion

### Current Implementation: GFS Model

**Configuration File**: `gfs.toml`

**Available Products**:
- `gfs_quarter_degree` - 0.25° resolution (currently the only option)

**Query Presets**:
- `sailing_basic` - Essential marine weather variables (wind, pressure, temperature, etc.)

## File Naming Convention

Downloaded files follow this pattern:
```
YYYYMMDD_HH_product_name.grib
```

Examples:
- `20251106_06_gfs_quarter_degree.grib` - GFS 0.25° from 2025-11-06 06Z
- `20251106_12_gfs_half_degree.grib` - (future) GFS 0.5° from 2025-11-06 12Z

**Components**:
- `YYYYMMDD` - Forecast run date (UTC)
- `HH` - Forecast cycle hour (00, 06, 12, 18 for GFS) - emphasized with separate underscore
- `product_name` - Product identifier from settings
- `.grib` - GRIB2 format extension

**Storage Location**: `_mutable/` directory

## Location Input Formats

Two supported formats for specifying geographic area:

### 1. Location and Expanse (DEFAULT)
```
center_lat: float      # Center latitude (-90 to 90)
center_lon: float      # Center longitude (-180 to 180 or 0 to 360)
height_degrees: float  # Height in degrees
width_degrees: float   # Width in degrees
```

### 2. Bounding Box
```
lat_max: float    # Top latitude
lat_min: float    # Bottom latitude
lon_max: float    # Right longitude
lon_min: float    # Left longitude
```

Both formats are converted internally to bounding boxes for the NOAA API.

## CLI Design Principles

### Progressive Disclosure
The CLI will eventually support the hierarchy:
1. **Forecast Model** (e.g., GFS, NAM, HRRR)
2. **Forecast Product** (e.g., gfs_quarter_degree, gfs_half_degree)
3. **Query Preset** (e.g., sailing_basic, aviation_complete)

### Smart Defaults
- When only one option exists at any level, auto-select it (no prompt)
- Use current defaults from `settings.toml` as suggested values
- Default to "location and expanse" input format (more intuitive than bounding box)

### Current Behavior
Since only GFS model and `gfs_quarter_degree` product exist:
- Skip model selection (auto-select GFS)
- Skip product selection (auto-select gfs_quarter_degree)
- Prompt for query preset (show available options from `[gfs_queries]`)
- Prompt for location with smart defaults

### Bandwidth Optimization Features

**Critical for bandwidth-limited environments (sailboat liveaboard)**

The CLI includes intelligent file management to avoid unnecessary downloads:

**File Existence Checking**:
- Before downloading, checks if target forecast file already exists locally
- Shows file size and forecast time for existing files
- Prompts user for action if file exists (download, skip, cancel)

**Download Control Flags**:

1. **`--force` / `-f`**: Force download even if file exists
   - Use when you want to ensure latest data regardless of local cache
   - Example: `fetch -p sailing_basic --force`

2. **`--new-only`**: Only download if file doesn't exist locally
   - Bandwidth-saving mode: never re-download existing forecasts
   - Perfect for automated scripts that should download once
   - Example: `fetch -p sailing_basic --new-only`

3. **`--check-only`**: Check forecast availability without downloading
   - Shows what forecast time would be downloaded
   - Checks if file exists locally
   - No network bandwidth used for download
   - Example: `fetch -p sailing_basic --check-only`

**Interactive Behavior**:
- If file exists and no flags specified: prompts user
- Default choice is "skip" to avoid accidental re-downloads
- Clear status messages show file size and existence

**Use Cases**:
- Daily automated fetch: `--new-only` (only gets new forecasts)
- Pre-departure check: `--check-only` (verify without downloading)
- Force refresh: `--force` (get latest even if cached)
- Bandwidth monitoring: Check file size before deciding to download

## Future Expansions

### Adding New Models
1. Create new config file: `{model_name}.toml`
2. Define `[{model}_data]`, `[{model}_queries]`, `[{model}_products]` sections
3. Add model to CLI selection menu
4. No code changes required - configuration driven

### Adding New Products
1. Add product definition to `[{model}_products.{product_name}]`
2. Specify URL patterns, file naming, directory structure
3. Product automatically appears in CLI options

### Adding New Query Presets
1. Define new preset in `[{model}_queries.{preset_name}]`
2. Create bitmasks for desired variables and levels
3. Preset automatically appears in CLI options

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
GRIB2 File (_mutable/YYYYMMDDHH_product.grib)
```

---

**Last Updated**: 2025-11-06
