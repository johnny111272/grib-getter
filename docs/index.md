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
- **Extensible**: Add new forecast models by dropping TOML files in `settings/`

## Use Case

Perfect for sailors, cruisers, and off-grid users who need:

- Reliable weather data with minimal bandwidth usage
- Protection against corrupted downloads in unreliable connectivity
- Easy-to-use command-line interface
- Flexible configuration for different use cases

## Quick Links

- [Installation](installation.md) - Get started in minutes
- [Quick Start](quickstart.md) - Basic usage examples
- [Configuration](configuration.md) - Customize for your needs
- [Architecture](architecture.md) - How it works
- [API Reference](api/cli.md) - Detailed documentation

## Technology Stack

Built with modern Python tools:

- **Python 3.13+** - Latest Python features
- **Typer** - Beautiful CLI with Rich integration
- **Pydantic** - Data validation with type hints
- **Dynaconf** - Flexible settings management
- **httpx** - Modern HTTP client
- **loguru** - Simple, powerful logging

## License

MIT License - See LICENSE file for details.

## Author

Johnny (@johnny111272)
