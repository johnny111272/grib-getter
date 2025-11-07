# Query Builder Reference

Constructs query URLs for NOAA's NOMADS GRIB filter service.

## Data Models

::: noaa_query_builder.ModelData
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.QueryModel
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.QueryMask
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.QueryTime
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.SelectedKeys
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.BoundingBox
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.CoreSettings
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.LocationSettings
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.QueryStructure
    options:
      show_root_heading: true
      show_source: true

## Main Functions

::: noaa_query_builder.generate_query_urls
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.build_query_url
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.collect_query_arguments
    options:
      show_root_heading: true
      show_source: true

## Geographic Calculations

::: noaa_query_builder.create_bounding_box
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.calculate_latitude_bounds
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.calculate_longitude_bounds
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.clamp_latitude
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.normalize_longitude
    options:
      show_root_heading: true
      show_source: true

## Time Calculations

::: noaa_query_builder.build_qt
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.generate_qt_batch
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.get_latest_run_start
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.get_latest_of_multiple
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.crop_to_hour
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.format_date_utc
    options:
      show_root_heading: true
      show_source: true

## Mask Operations

::: noaa_query_builder.get_binary_mask_from_hex
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.get_url_encoded_keys
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.build_new_mask
    options:
      show_root_heading: true
      show_source: true

::: noaa_query_builder.reveal_masked_values
    options:
      show_root_heading: true
      show_source: true
