#!/usr/bin/env python3
"""
NOAA Weather Forecast Fetcher CLI

Fetch weather forecast data from NOAA's NOMADS server with an interactive
command-line interface.
"""

import datetime as dt
from pathlib import Path

import tomli_w
import typer
from loguru import logger
from rich.console import Console
from rich.logging import RichHandler
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


# =============================================================================
# LOGGING SETUP
# =============================================================================


def setup_logging() -> None:
    """
    Configure loguru with rich handler for enhanced console output.

    Should be called once at application entry point.
    """
    # Remove default handler
    logger.remove()

    # Add rich handler for beautiful console output
    _ = logger.add(
        RichHandler(
            console=console,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
        ),
        format="{message}",
        level="INFO",
    )


def get_storage_path() -> Path | None:
    """Get configured storage path, or None if not configured."""
    try:
        return Path(settings.core_settings.output_dir)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    except (AttributeError, KeyError):
        return None


def save_storage_path(storage_path: Path) -> None:
    """
    Save storage path to user.toml file.

    Separates user configuration (output_dir) from application configuration.
    This avoids polluting version-controlled settings.toml with user paths.
    """
    import tomli

    user_config_file = Path("user.toml")

    # Read current user config
    if user_config_file.exists():
        with open(user_config_file, "rb") as f:
            config = tomli.load(f)
    else:
        config = {}

    # Ensure core_settings section exists
    if "core_settings" not in config:
        config["core_settings"] = {}

    # Update output_dir
    config["core_settings"]["output_dir"] = str(storage_path)

    # Write to user.toml
    with open(user_config_file, "wb") as f:
        tomli_w.dump(config, f)

    console.print(
        f"[green]✓[/green] Storage path configured: [cyan]{storage_path}[/cyan]"
    )


def ensure_storage_configured() -> Path:
    """
    Ensure storage path is configured. Prompts user if not set.

    First-run setup: prompts for storage directory and saves to settings.
    Must reload settings after saving to pick up the new configuration.

    Returns:
        Configured storage path
    """
    global settings
    storage_path = get_storage_path()

    if storage_path is None:
        console.print("\n[bold yellow]First-time setup required[/bold yellow]")
        console.print("Please configure where GRIB files should be stored.\n")

        default_path = Path.cwd() / settings.defaults.grib_dir  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        path_input = Prompt.ask(
            "Storage directory for GRIB files",
            default=str(default_path),  # pyright: ignore[reportUnknownArgumentType]
        )

        storage_path = Path(path_input).expanduser().resolve()

        # Create directory if it doesn't exist
        if not storage_path.exists():
            if Confirm.ask(
                f"Directory doesn't exist. Create {storage_path}?", default=True
            ):
                storage_path.mkdir(parents=True, exist_ok=True)
                console.print(f"[green]✓[/green] Created directory: {storage_path}")
            else:
                console.print("[red]Setup cancelled[/red]")
                raise typer.Exit(code=1)

        save_storage_path(storage_path)

        # Reload settings to pick up the new output_dir value from user.toml
        from dynaconf import Dynaconf  # pyright: ignore[reportMissingTypeStubs]

        settings = Dynaconf(
            envvar_prefix="DYNACONF",
            settings_files=[
                "settings.toml",
                "user.toml",
                ".secrets.toml",
                "settings/*.toml",
            ],
            merge_enabled=True,
        )

    return storage_path


def get_available_query_presets() -> list[str]:
    """Get list of available query preset names from GFS settings."""
    return list(settings.GFS_QUERIES.keys())  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]


def prompt_for_query_preset() -> str:
    """
    Interactively prompt user to select a query preset.

    Auto-selects if only one preset available, otherwise shows numbered menu.
    """
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
    """
    Interactively prompt user for location parameters.

    Uses center point + expanse format (more intuitive than bounding box).
    Defaults pulled from settings.DEFAULT_LOCATION.
    """
    console.print("\n[bold]Location Configuration[/bold]")
    console.print("[dim]Using center point + expanse format[/dim]")

    # Get defaults from settings
    defaults = settings.DEFAULT_LOCATION  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

    center_lat = float(
        Prompt.ask(
            "Center latitude (-90 to 90)",
            default=str(defaults.center_lat),  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        )
    )
    center_lon = float(
        Prompt.ask(
            "Center longitude (-180 to 180)",
            default=str(defaults.center_lon),  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        )
    )
    height_degrees = float(
        Prompt.ask(
            "Height in degrees",
            default=str(defaults.height_degrees),  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        )
    )
    width_degrees = float(
        Prompt.ask(
            "Width in degrees",
            default=str(defaults.width_degrees),  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        )
    )

    return nqb.LocationSettings(
        center_lat=center_lat,
        center_lon=center_lon,
        height_degrees=height_degrees,
        width_degrees=width_degrees,
    )


def generate_output_filename(
    model_name: str,
    product_name: str,  # pyright: ignore[reportUnusedParameter]
    preset_name: str,
    forecast_time: dt.datetime,
    forecast_hour: int,
    storage_path: Path,
) -> Path:
    """
    Generate output filename in run-specific folder structure.

    New structure for async batch downloading support:
    - Folder: YYYYMMDD_HH_{model_name}_{preset_name}/
    - File: YYYYMMDD_HH_FFF_{model_name}_{preset_name}.grib
      where FFF is the forecast hour (000 for analysis, 001, 006, 012, etc.)

    Args:
        model_name: Model identifier (e.g., 'GFS')
        product_name: Product identifier (e.g., 'gfs_quarter_degree')
        preset_name: Query preset name (e.g., 'sailing_basic')
        forecast_time: Forecast run datetime
        forecast_hour: Forecast hour (0 for analysis file)
        storage_path: Base directory where GRIB files are stored

    Returns:
        Path to output file in run-specific subdirectory
    """
    date_part = forecast_time.strftime("%Y%m%d")
    hour_part = forecast_time.strftime("%H")

    # Create run-specific folder name
    folder_name = f"{date_part}_{hour_part}_{model_name}_{preset_name}"
    run_folder = storage_path / folder_name

    # Create filename with forecast hour
    filename = (
        f"{date_part}_{hour_part}_{forecast_hour:03d}_{model_name}_{preset_name}.grib"
    )

    return run_folder / filename


def create_backup_file(original_path: Path) -> Path:
    """
    Create a backup of an existing file before overwriting.

    Critical for bandwidth-limited environments where corrupted downloads
    could lose good data from earlier successful downloads.

    Backup naming: {original_name}.{NN}.bak where NN is 00 to max_count-1
    Finds next available number; if all slots used, overwrites the last one.

    Backup settings (max_count, extension) configured in settings.toml.

    Args:
        original_path: Path to file that will be backed up

    Returns:
        Path to created backup file
    """
    # Find next available backup number
    backup_num = 0
    while backup_num < settings.backup.max_count:  # pyright: ignore[reportUnknownMemberType]
        backup_path = Path(
            f"{original_path}.{backup_num:02d}{settings.backup.extension}"  # pyright: ignore[reportUnknownMemberType]
        )
        if not backup_path.exists():
            break
        backup_num += 1
    else:
        # If all backup slots full, overwrite the last one
        final_backup_num = settings.backup.max_count - 1  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        backup_path = Path(
            f"{original_path}.{final_backup_num:02d}{settings.backup.extension}"  # pyright: ignore[reportUnknownMemberType]
        )

    # Create backup by renaming original
    _ = original_path.rename(backup_path)
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
    setup_logging()

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
                center_lat=lat,  # pyright: ignore[reportArgumentType]
                center_lon=lon,  # pyright: ignore[reportArgumentType]
                height_degrees=height,  # pyright: ignore[reportArgumentType]
                width_degrees=width,  # pyright: ignore[reportArgumentType]
            )
    else:
        # Fully non-interactive
        location = nqb.LocationSettings(
            center_lat=lat,  # pyright: ignore[reportArgumentType]
            center_lon=lon,  # pyright: ignore[reportArgumentType]
            height_degrees=height,  # pyright: ignore[reportArgumentType]
            width_degrees=width,  # pyright: ignore[reportArgumentType]
        )

    # Display configuration summary
    console.print("\n[bold]Configuration:[/bold]")
    console.print(
        f"  Model: [green]{settings.defaults.model_name}[/green] (auto-selected)"  # pyright: ignore[reportUnknownMemberType]
    )
    console.print(
        f"  Product: [green]{settings.defaults.product_name}[/green] (auto-selected)"  # pyright: ignore[reportUnknownMemberType]
    )
    console.print(f"  Preset: [green]{preset}[/green]")
    console.print(
        f"  Location: [green]{location.center_lat}, {location.center_lon}[/green] "  # pyright: ignore[reportImplicitStringConcatenation]
        f"({location.width_degrees}° × {location.height_degrees}°)"
    )

    # Load model data and query mask from configuration
    model_data = nqb.ModelData.model_validate(settings.GFS_DATA)  # pyright: ignore[reportUnknownMemberType]
    query_mask = nqb.QueryMask.model_validate(getattr(settings.GFS_QUERIES, preset))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]

    # Build query structure for NOAA API
    qs = nqb.QueryStructure(
        bounding_box=nqb.create_bounding_box(ls=location),
        query_model=nqb.QueryModel.model_validate(
            settings.GFS_PRODUCTS.gfs_quarter_degree,  # pyright: ignore[reportUnknownMemberType]
        ),
        variables=nqb.SelectedKeys(
            all_keys=model_data.variables,
            hex_mask=query_mask.variables,
            prefix=settings.query.var_prefix,  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        ),
        levels=nqb.SelectedKeys(
            all_keys=model_data.levels,
            hex_mask=query_mask.levels,
            prefix=settings.query.lev_prefix,  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        ),
        current_time=dt.datetime.now(tz=dt.timezone.utc),
        settings=nqb.CoreSettings.model_validate(settings.core_settings),  # pyright: ignore[reportUnknownMemberType]
    )

    # Generate query URLs (tries most recent to older forecasts)
    query_urls = nqb.generate_query_urls(
        qt_batch=nqb.generate_qt_batch(reference_time=qs.current_time, qs=qs),
        qs=qs,
    )

    # Generate output path in run-specific folder
    latest_forecast = nqb.get_latest_run_start(dt.datetime.now(tz=dt.timezone.utc), qs)
    output_path = generate_output_filename(
        model_name=settings.defaults.model_name,  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        product_name=settings.defaults.product_name,  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        preset_name=preset,
        forecast_time=latest_forecast,
        forecast_hour=0,  # Analysis file is hour 000
        storage_path=storage_path,
    )

    console.print("\n[bold]Target file:[/bold]")
    console.print(f"  Path: [cyan]{output_path}[/cyan]")
    console.print(
        f"  Forecast time: [cyan]{latest_forecast.strftime('%Y-%m-%d %H:00 UTC')}[/cyan]"
    )

    # Check if file already exists locally
    file_exists = output_path.exists()
    if file_exists:
        file_size = output_path.stat().st_size
        console.print(
            f"  Status: [yellow]File already exists ({file_size:,} bytes)[/yellow]"
        )
    else:
        console.print("  Status: [dim]File does not exist locally[/dim]")

    # Handle check-only mode (no download, just report)
    if check_only:
        console.print("\n[bold]Check-only mode:[/bold] No download will be performed")
        if file_exists:
            console.print("[green]✓[/green] Latest forecast file exists locally")
        else:
            console.print("[yellow]![/yellow] Latest forecast file not found locally")
        raise typer.Exit(code=0)

    # Handle existing file (bandwidth optimization)
    if file_exists and not force:
        if new_only:
            # --new-only flag: skip if file exists (for automated scripts)
            console.print(
                "\n[yellow]File exists and --new-only specified. Skipping download.[/yellow]"
            )
            console.print(f"  Using existing file: [cyan]{output_path}[/cyan]")
            raise typer.Exit(code=0)
        else:
            # Interactive mode: ask user what to do
            console.print("\n[bold yellow]File already exists![/bold yellow]")
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
            # choice == "download" falls through

    # Create backup before overwriting (data integrity protection)
    if file_exists:
        console.print("\n[bold]Backing up existing file...[/bold]")
        _ = create_backup_file(output_path)

    console.print("\n[bold]Fetching data...[/bold]")

    # Fetch data
    result = ngf.fetch_with_timeout(
        query_urls=query_urls,
        output_path=output_path,
    )

    # Report results
    if result.success and result.data:
        console.print(
            f"\n[bold green]✓ Success![/bold green] "  # pyright: ignore[reportImplicitStringConcatenation]
            f"Downloaded {len(result.data):,} bytes in {result.total_duration_seconds:.1f}s"
        )
        console.print(f"  File: [cyan]{output_path}[/cyan]")
    else:
        console.print(
            f"\n[bold red]✗ Failed[/bold red] after {len(result.attempts)} attempts "  # pyright: ignore[reportImplicitStringConcatenation]
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
    setup_logging()

    console.print("[bold blue]grib-getter Configuration[/bold blue]\n")

    if storage_path is None:
        # Interactive mode
        current_path = get_storage_path()
        if current_path:
            console.print(f"Current storage path: [cyan]{current_path}[/cyan]\n")

        default_path = current_path or Path.cwd() / settings.defaults.grib_dir  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        path_input = Prompt.ask(
            "Storage directory for GRIB files",
            default=str(default_path),  # pyright: ignore[reportUnknownArgumentType]
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
