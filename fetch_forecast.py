#!/usr/bin/env python3
"""
NOAA Weather Forecast Fetcher CLI

Fetch weather forecast data from NOAA's NOMADS server with an interactive
command-line interface.
"""

import datetime as dt
import tomli_w
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.prompt import Prompt, Confirm
from typing_extensions import Annotated

import noaa_grib_fetcher as ngf
import noaa_query_builder as nqb
from config import settings

app = typer.Typer(
    help="Fetch NOAA weather forecast data",
    add_completion=False,
)
console = Console()


# Configuration file path
SETTINGS_FILE = Path("settings.toml")


def get_storage_path() -> Path | None:
    """Get configured storage path, or None if not configured."""
    try:
        return Path(settings.core_settings.output_dir)
    except (AttributeError, KeyError):
        return None


def save_storage_path(storage_path: Path) -> None:
    """Save storage path to settings.toml file."""
    import tomli

    # Read current settings
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, "rb") as f:
            config = tomli.load(f)
    else:
        config = {}

    # Ensure core_settings section exists
    if "core_settings" not in config:
        config["core_settings"] = {}

    # Update output_dir
    config["core_settings"]["output_dir"] = str(storage_path)

    # Write back to file
    with open(SETTINGS_FILE, "wb") as f:
        tomli_w.dump(config, f)

    console.print(f"[green]✓[/green] Storage path configured: [cyan]{storage_path}[/cyan]")


def ensure_storage_configured() -> Path:
    """
    Ensure storage path is configured. Prompts user if not set.
    Returns the configured storage path.
    """
    storage_path = get_storage_path()

    if storage_path is None:
        console.print("\n[bold yellow]First-time setup required[/bold yellow]")
        console.print("Please configure where GRIB files should be stored.\n")

        default_path = Path.cwd() / "grib_data"
        path_input = Prompt.ask(
            "Storage directory for GRIB files",
            default=str(default_path),
        )

        storage_path = Path(path_input).expanduser().resolve()

        # Create directory if it doesn't exist
        if not storage_path.exists():
            if Confirm.ask(f"Directory doesn't exist. Create {storage_path}?", default=True):
                storage_path.mkdir(parents=True, exist_ok=True)
                console.print(f"[green]✓[/green] Created directory: {storage_path}")
            else:
                console.print("[red]Setup cancelled[/red]")
                raise typer.Exit(code=1)

        save_storage_path(storage_path)

        # Reload settings
        from dynaconf import Dynaconf
        global settings
        settings = Dynaconf(
            envvar_prefix="DYNACONF",
            settings_files=["settings.toml", ".secrets.toml", "gfs.toml"],
        )

    return storage_path


def get_available_query_presets() -> list[str]:
    """Get list of available query preset names from GFS settings."""
    return list(settings.GFS_QUERIES.keys())


def prompt_for_query_preset() -> str:
    """Interactively prompt user to select a query preset."""
    presets = get_available_query_presets()

    if len(presets) == 1:
        console.print(f"[dim]Auto-selecting query preset: {presets[0]}[/dim]")
        return presets[0]

    console.print("\n[bold]Available Query Presets:[/bold]")
    for i, preset in enumerate(presets, 1):
        console.print(f"  {i}. {preset}")

    while True:
        choice = Prompt.ask(
            "\nSelect preset",
            choices=[str(i) for i in range(1, len(presets) + 1)],
            default="1",
        )
        return presets[int(choice) - 1]


def prompt_for_location() -> nqb.LocationSettings:
    """Interactively prompt user for location parameters."""
    console.print("\n[bold]Location Configuration[/bold]")
    console.print("[dim]Using center point + expanse format[/dim]")

    # Get defaults from settings
    defaults = settings.DEFAULT_LOCATION

    center_lat = float(
        Prompt.ask(
            "Center latitude (-90 to 90)",
            default=str(defaults.center_lat),
        )
    )
    center_lon = float(
        Prompt.ask(
            "Center longitude (-180 to 180)",
            default=str(defaults.center_lon),
        )
    )
    height_degrees = float(
        Prompt.ask(
            "Height in degrees",
            default=str(defaults.height_degrees),
        )
    )
    width_degrees = float(
        Prompt.ask(
            "Width in degrees",
            default=str(defaults.width_degrees),
        )
    )

    return nqb.LocationSettings(
        center_lat=center_lat,
        center_lon=center_lon,
        height_degrees=height_degrees,
        width_degrees=width_degrees,
    )


def generate_output_filename(
    product_name: str,
    forecast_time: dt.datetime,
    storage_path: Path,
) -> Path:
    """
    Generate output filename following convention: YYYYMMDD_HH_product_name.grib

    Args:
        product_name: Product identifier (e.g., 'gfs_quarter_degree')
        forecast_time: Forecast run datetime
        storage_path: Directory where GRIB files are stored

    Returns:
        Path to output file in storage directory
    """
    date_part = forecast_time.strftime("%Y%m%d")
    hour_part = forecast_time.strftime("%H")
    filename = f"{date_part}_{hour_part}_{product_name}.grib"
    return storage_path / filename


def create_backup_file(original_path: Path) -> Path:
    """
    Create a backup of an existing file before overwriting.

    Critical for bandwidth-limited environments where corrupted downloads
    could lose good data from earlier successful downloads.

    Backup naming: {original_name}.{00-99}.bak
    Finds next available number if multiple backups exist.

    Args:
        original_path: Path to file that will be backed up

    Returns:
        Path to created backup file
    """
    # Find next available backup number
    backup_num = 0
    while backup_num < 100:
        backup_path = Path(f"{original_path}.{backup_num:02d}.bak")
        if not backup_path.exists():
            break
        backup_num += 1
    else:
        # If we've hit 100 backups, overwrite .99.bak
        backup_path = Path(f"{original_path}.99.bak")

    # Create backup by renaming original
    original_path.rename(backup_path)
    console.print(f"  [dim]Created backup: {backup_path.name}[/dim]")

    return backup_path


@app.command()
def fetch(
    preset: Annotated[
        str | None,
        typer.Option(
            "--preset",
            "-p",
            help="Query preset name (e.g., 'sailing_basic'). If not provided, will prompt interactively.",
        ),
    ] = None,
    lat: Annotated[
        float | None,
        typer.Option("--lat", help="Center latitude (-90 to 90)"),
    ] = None,
    lon: Annotated[
        float | None,
        typer.Option("--lon", help="Center longitude (-180 to 180)"),
    ] = None,
    height: Annotated[
        float | None,
        typer.Option("--height", help="Height in degrees"),
    ] = None,
    width: Annotated[
        float | None,
        typer.Option("--width", help="Width in degrees"),
    ] = None,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive/--no-interactive",
            "-i/-I",
            help="Force interactive mode even if all options provided",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force download even if file already exists locally",
        ),
    ] = False,
    new_only: Annotated[
        bool,
        typer.Option(
            "--new-only",
            help="Only download if file doesn't exist locally",
        ),
    ] = False,
    check_only: Annotated[
        bool,
        typer.Option(
            "--check-only",
            help="Check what forecast is available on server without downloading",
        ),
    ] = False,
) -> None:
    """
    Fetch NOAA GFS weather forecast data.

    Can be used interactively (prompts for all options) or with command-line arguments
    for automation.

    Examples:
        # Interactive mode (default)
        python fetch_forecast.py fetch

        # Non-interactive with all options
        python fetch_forecast.py fetch -p sailing_basic --lat 45 --lon -93 --height 90 --width 180

        # Force download even if file exists
        python fetch_forecast.py fetch -p sailing_basic --force

        # Only download if file doesn't exist (bandwidth-saving)
        python fetch_forecast.py fetch -p sailing_basic --new-only

        # Check what's available without downloading
        python fetch_forecast.py fetch -p sailing_basic --check-only
    """
    console.print("[bold blue]grib-getter: NOAA Weather Forecast Fetcher[/bold blue]\n")

    # Ensure storage path is configured (first-run setup if needed)
    storage_path = ensure_storage_configured()

    # Determine if we need interactive prompts
    need_preset = preset is None
    need_location = any(x is None for x in [lat, lon, height, width])

    if interactive or need_preset or need_location:
        # Interactive mode
        if need_preset:
            preset = prompt_for_query_preset()

        if need_location:
            location = prompt_for_location()
        else:
            location = nqb.LocationSettings(
                center_lat=lat,  # type: ignore
                center_lon=lon,  # type: ignore
                height_degrees=height,  # type: ignore
                width_degrees=width,  # type: ignore
            )
    else:
        # Fully non-interactive
        location = nqb.LocationSettings(
            center_lat=lat,  # type: ignore
            center_lon=lon,  # type: ignore
            height_degrees=height,  # type: ignore
            width_degrees=width,  # type: ignore
        )

    # Build query structure
    console.print(f"\n[bold]Configuration:[/bold]")
    console.print(f"  Model: [green]GFS[/green] (auto-selected)")
    console.print(f"  Product: [green]gfs_quarter_degree[/green] (auto-selected)")
    console.print(f"  Preset: [green]{preset}[/green]")
    console.print(
        f"  Location: [green]{location.center_lat}, {location.center_lon}[/green] "
        f"({location.width_degrees}° × {location.height_degrees}°)"
    )

    # Load model data and query mask
    model_data = nqb.ModelData.model_validate(settings.GFS_DATA)
    query_mask = nqb.QueryMask.model_validate(getattr(settings.GFS_QUERIES, preset))

    # Build query structure
    qs = nqb.QueryStructure(
        bounding_box=nqb.create_bounding_box(ls=location),
        query_model=nqb.QueryModel.model_validate(
            settings.GFS_PRODUCTS.gfs_quarter_degree,
        ),
        variables=nqb.SelectedKeys(
            all_keys=model_data.variables,
            hex_mask=query_mask.variables,
            prefix="var_",
        ),
        levels=nqb.SelectedKeys(
            all_keys=model_data.levels,
            hex_mask=query_mask.levels,
            prefix="lev_",
        ),
        current_time=dt.datetime.now(tz=dt.timezone.utc),
        settings=nqb.CoreSettings.model_validate(settings.core_settings),
    )

    # Generate query URLs
    query_urls = nqb.generate_query_urls(
        qt_batch=nqb.generate_qt_batch(reference_time=qs.current_time, qs=qs),
        qs=qs,
    )

    # Generate output filename
    latest_forecast = nqb.get_latest_run_start(
        dt.datetime.now(tz=dt.timezone.utc), qs
    )
    output_path = generate_output_filename("gfs_quarter_degree", latest_forecast, storage_path)

    console.print(f"\n[bold]Target file:[/bold]")
    console.print(f"  Path: [cyan]{output_path}[/cyan]")
    console.print(f"  Forecast time: [cyan]{latest_forecast.strftime('%Y-%m-%d %H:00 UTC')}[/cyan]")

    # Check if file already exists
    file_exists = output_path.exists()
    if file_exists:
        file_size = output_path.stat().st_size
        console.print(f"  Status: [yellow]File already exists ({file_size:,} bytes)[/yellow]")
    else:
        console.print(f"  Status: [dim]File does not exist locally[/dim]")

    # Handle check-only mode
    if check_only:
        console.print(f"\n[bold]Check-only mode:[/bold] No download will be performed")
        if file_exists:
            console.print(f"[green]✓[/green] Latest forecast file exists locally")
        else:
            console.print(f"[yellow]![/yellow] Latest forecast file not found locally")
        raise typer.Exit(code=0)

    # Handle existing file
    if file_exists and not force:
        if new_only:
            console.print(f"\n[yellow]File exists and --new-only specified. Skipping download.[/yellow]")
            console.print(f"  Using existing file: [cyan]{output_path}[/cyan]")
            raise typer.Exit(code=0)
        else:
            # Interactive prompt for what to do
            console.print(f"\n[bold yellow]File already exists![/bold yellow]")
            choice = Prompt.ask(
                "What would you like to do?",
                choices=["download", "skip", "cancel"],
                default="skip",
            )
            if choice == "skip":
                console.print(f"[green]Using existing file: {output_path}[/green]")
                raise typer.Exit(code=0)
            elif choice == "cancel":
                console.print("[red]Cancelled[/red]")
                raise typer.Exit(code=1)
            # choice == "download" falls through to fetch below

    # Create backup of existing file before overwriting
    if file_exists:
        console.print(f"\n[bold]Backing up existing file...[/bold]")
        create_backup_file(output_path)

    console.print(f"\n[bold]Fetching data...[/bold]")

    # Fetch data
    result = ngf.fetch_with_timeout(
        query_urls=query_urls,
        output_path=output_path,
    )

    # Report results
    if result.success and result.data:
        console.print(
            f"\n[bold green]✓ Success![/bold green] "
            f"Downloaded {len(result.data):,} bytes in {result.total_duration_seconds:.1f}s"
        )
        console.print(f"  File: [cyan]{output_path}[/cyan]")
    else:
        console.print(
            f"\n[bold red]✗ Failed[/bold red] after {len(result.attempts)} attempts "
            f"in {result.total_duration_seconds:.1f}s"
        )
        raise typer.Exit(code=1)


@app.command()
def list_presets() -> None:
    """List available query presets."""
    console.print("[bold]Available Query Presets:[/bold]\n")
    for preset in get_available_query_presets():
        console.print(f"  • {preset}")


@app.command()
def configure(
    storage_path: Annotated[
        str | None,
        typer.Option(
            "--storage",
            "-s",
            help="Set GRIB file storage directory path",
        ),
    ] = None,
) -> None:
    """
    Configure grib-getter settings.

    Use this to set or change the GRIB file storage directory.
    If no path provided, will prompt interactively.

    Examples:
        # Interactive configuration
        grib-getter configure

        # Set storage path directly
        grib-getter configure --storage /path/to/grib_data
    """
    console.print("[bold blue]grib-getter Configuration[/bold blue]\n")

    if storage_path is None:
        # Interactive mode
        current_path = get_storage_path()
        if current_path:
            console.print(f"Current storage path: [cyan]{current_path}[/cyan]\n")

        default_path = current_path or Path.cwd() / "grib_data"
        path_input = Prompt.ask(
            "Storage directory for GRIB files",
            default=str(default_path),
        )
        storage_path = path_input

    # Convert to Path and expand/resolve
    new_path = Path(storage_path).expanduser().resolve()

    # Create directory if it doesn't exist
    if not new_path.exists():
        if Confirm.ask(f"\nDirectory doesn't exist. Create {new_path}?", default=True):
            new_path.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]✓[/green] Created directory: {new_path}")
        else:
            console.print("[red]Configuration cancelled[/red]")
            raise typer.Exit(code=1)

    # Save configuration
    save_storage_path(new_path)
    console.print("\n[green]✓ Configuration complete![/green]")


if __name__ == "__main__":
    app()
