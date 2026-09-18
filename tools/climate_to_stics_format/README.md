# Climate to STICS Format

A Galaxy tool that converts daily climate data from **ERA5**, **SAFRAN/GeoSAS**,
**DRIAS-2020**, or a custom source into the daily input files expected by the
**STICS** crop model (*Simulateur mulTIdisciplinaire pour les Cultures Standard*).

Developed as part of the [DairyFit project](https://forge.inrae.fr/dairyfit/lot1/chaine_traitement_indicateur) (INRAE).

- **Tool ID:** `climate_to_stics`
- **Tool version:** 1.0.0+galaxy1
- **Galaxy profile:** 21.05

---

## What it does

1. **Loads** climate data in various formats (NetCDF, CSV, TSV, JSON, Parquet).
2. **Renames and converts** variables according to their source (ERA5, SAFRAN,
   DRIAS, or a custom JSON mapping), applying the correct unit conversions
   automatically.
3. **Computes derived variables** that aren't present in the source (mean
   temperature, relative humidity, vapour pressure).
4. **Assigns each pixel/row** to a spatial cell ID, via a shapefile
   (rasterised onto the input grid) or an existing ID column.
5. **Automatically retrieves and merges** annual atmospheric CO2
   concentrations — no CO2 input file is needed:
   - **1959 → present**: NOAA/GML Mauna Loa annual mean, downloaded live
     from `gml.noaa.gov` (falls back to a bundled 1959–2023 snapshot if the
     network is unavailable).
   - **before 1959**: ice-core record (NASA/GISS, after Etheridge et al. 1996),
     bundled with the script.
6. **Exports** a ZIP archive containing one directory per cell and one
   headerless TSV file per year, in the exact column order STICS expects.

## Supported climate data sources

| Source | Format | Notes |
|---|---|---|
| **ERA5** (Copernicus Climate Data Store) | NetCDF, HDF5, or tabular | Also auto-detects Open-Meteo daily-archive exports (already unit-converted) |
| **SAFRAN / GeoSAS** (Météo-France) | Tabular (CSV/TSV/Parquet/JSON), GeoCSV, or NetCDF | Also auto-detects Météo-France SIM2 reanalysis columns |
| **DRIAS-2020** (bias-adjusted CMIP5/6 projections) | ZIP archive of NetCDF files (one file per variable) | Requires a shapefile to assign spatial cells |
| **Custom** | Any of the above | Requires a JSON variable mapping and manual unit selection |

## STICS output format

Each output file `{cell_id}.{year}` is a headerless TSV with columns in this
exact order:

| Column | Unit | Description |
|---|---|---|
| Cell ID | – | Integer ID of the spatial cell |
| Year | – | Calendar year |
| Month | – | Month (1–12) |
| Day of month | – | Day within the month (1–31) |
| Day of year | – | Julian day (1–365/366) |
| tasmin | °C | Daily minimum temperature |
| tasmax | °C | Daily maximum temperature |
| rsds | MJ/m²/day | Global solar radiation |
| etp | mm/day | Potential evapotranspiration |
| prtot | mm/day | Total precipitation |
| wind | m/s | Wind speed at 2 m |
| vapp | hPa | Air vapour pressure |
| co2 | ppm | Atmospheric CO2 concentration |

Full variable-mapping tables per source (ERA5, SAFRAN/GeoSAS, DRIAS-2020),
plus the shapefile and custom-mapping requirements, are documented in the
tool's in-Galaxy help panel (`<help>` section of `climate_to_stics.xml`).

## Repository contents

```
.
├── climate_to_stics.xml   # Galaxy tool wrapper (inputs, outputs, tests, help)
├── climate_to_stics.py    # Conversion script invoked by the wrapper
├── test-data/             # Test input/output files referenced by <tests>
│                          #   (add test_safran.csv here — see the <test> block
│                          #    in climate_to_stics.xml — it is not yet in this repo)
├── .shed.yml              # Tool Shed repository metadata
└── README.md              # This file
```

## Requirements

Declared in `climate_to_stics.xml` and resolved via Conda when the tool is
installed from a Tool Shed:

| Package | Version |
|---|---|
| xarray | 2024.10.0 |
| pandas | 2.2.1 |
| numpy | 1.26.4 |
| geopandas | 0.14.0 |
| rasterio | 1.3.9 |
| rioxarray | 0.15.7 |
| pyarrow | 14.0.0 |

## Installation

### From a Tool Shed
Install through the Galaxy admin panel (**Admin → Tool Sheds → search for
`climate_to_stics`**), or point your Galaxy instance's `tool_sheds_conf.xml`
at the Tool Shed this repository is published to.

### For local development / testing
With [Planemo](https://planemo.readthedocs.io/):

```bash
# Lint the tool wrapper
planemo lint climate_to_stics.xml

# Run the built-in <tests> against a local Galaxy instance
planemo test climate_to_stics.xml

# Serve the tool in a throwaway Galaxy for interactive testing
planemo serve climate_to_stics.xml
```

## Publishing / updating on a Tool Shed

```bash
# First-time setup (creates ~/.planemo.yml with your Tool Shed credentials)
planemo shed_lint --tools climate_to_stics.xml

# Create the repository on the Tool Shed (uses .shed.yml)
planemo shed_create

# Push a new revision after making changes
planemo shed_update --check_diff
```

Before publishing, edit `.shed.yml` and:
- set `owner` to your Tool Shed account name
- confirm `categories` against the current category list on your target
  Tool Shed instance

## Citing

Citations are declared in `climate_to_stics.xml` (`<citations>`), as DOIs
resolved automatically by Galaxy:

- STICS model — Brisson et al., 2003, *European Journal of Agronomy* — [10.1016/S1161-0301(02)00110-7](https://doi.org/10.1016/S1161-0301(02)00110-7)
- ERA5 reanalysis — Hersbach et al., 2020, *QJRMS* — [10.1002/qj.3803](https://doi.org/10.1002/qj.3803)
- SAFRAN — Quintana-Seguí et al., 2008, *J. Applied Meteorology and Climatology* — [10.1175/2007JAMC1636.1](https://doi.org/10.1175/2007JAMC1636.1)
- xarray — Hoyer & Hamman, 2017, *Journal of Open Research Software* — [10.5334/jors.148](https://doi.org/10.5334/jors.148)
- Ice-core CO2 record — Etheridge et al., 1996, *JGR Atmospheres* — [10.1029/95JD03410](https://doi.org/10.1029/95JD03410)

CO2 trend data: NOAA/GML Mauna Loa annual mean (Lan, Tans & Thoning) and,
before 1959, NASA/GISS's compilation of the Etheridge et al. (1996) ice-core
record — see `gml.noaa.gov/ccgg/trends/` for the current citation.

## License

TODO — add a license for this repository (e.g. MIT, Apache-2.0, CeCILL for
INRAE software) and reference it here.

## Contact

Part of the DairyFit project (INRAE), Work Package 1 — Climate Data
Processing. For issues or questions, use the project's INRAE Forge
repository: https://forge.inrae.fr/dairyfit/lot1/chaine_traitement_indicateur
