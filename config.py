from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="DYNACONF",
    settings_files=[
        "settings.toml",  # Application defaults
        "user.toml",  # User-specific config (e.g., output_dir)
        ".secrets.toml",  # Secrets (API keys, etc.)
        "settings/*.toml",  # Model configs auto-discovered (gfs.toml, nam.toml, etc.)
    ],
    merge_enabled=True,  # Merge nested dictionaries instead of replacing
)

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load these files in the order.
# user.toml is loaded after settings.toml so user config overrides/extends defaults
# merge_enabled ensures [core_settings] in user.toml merges with settings.toml
# Glob pattern "settings/*.toml" auto-discovers new model configs - just add a file!
