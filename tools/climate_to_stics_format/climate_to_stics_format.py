#!/usr/bin/env python3
"""
climate_to_stics.py
===================
Converts daily climate data (ERA5 / Open-Meteo, SAFRAN / GeoSAS / SIM2,
DRIAS-2020, INRAE AgroClim stations or custom tables) into STICS crop model
input files.

Each output file ``{cell_id}.{year}`` is a headerless TSV with columns:
  cell_id | year | month | day_of_month | day_of_year |
  tasmin  | tasmax | rsds | etp | prtot | wind | vapp | co2

Missing values are written as -999.9 (STICS convention).

Part of the DairyFit project (INRAE).
https://forge.inrae.fr/dairyfit/lot1/chaine_traitement_indicateur
"""

import argparse
import logging
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import geopandas as gpd
import numpy as np
import pandas as pd
import rioxarray  # noqa: F401 – registers .rio accessor on xarray objects
import xarray as xr
from rasterio.features import rasterize

__version__ = "1.1.0"

# STICS missing-value code
STICS_MISSING = -999.9

# =============================================================================
# VARIABLE MAPPING TABLES
# =============================================================================
# Each entry:  internal_name -> {"names": [aliases], "conversion": str | None}
# Conversion keys are resolved in apply_conversion().

ERA5_MAPPING: Dict = {
    # Temperatures --------------------------------------------------------
    "tasmax": {
        "names": [
            "mx2t", "mx2t24",
            "maximum_2m_temperature_since_previous_post_processing",
        ],
        "unit_in": "K",
        "unit_out": "°C",
        "conversion": "K_to_C",
    },
    "tasmin": {
        "names": [
            "mn2t", "mn2t24",
            "minimum_2m_temperature_since_previous_post_processing",
        ],
        "unit_in": "K",
        "unit_out": "°C",
        "conversion": "K_to_C",
    },
    # Radiation -----------------------------------------------------------
    "rsds": {
        "names": ["ssrd", "surface_solar_radiation_downwards",
                  "surface_solar_radiation_downward"],
        "unit_in": "J/m²  (daily accumulation)",
        "unit_out": "MJ/m²/day",
        "conversion": "J_to_MJ",
    },
    # Precipitation -------------------------------------------------------
    "prtot": {
        "names": ["tp", "total_precipitation"],
        "unit_in": "m/day",
        "unit_out": "mm/day",
        "conversion": "m_to_mm",
    },
    # ETP -----------------------------------------------------------------
    "etp": {
        "names": ["pev", "potential_evaporation", "e", "evaporation"],
        "unit_in": "m/day  (often negative in ERA5)",
        "unit_out": "mm/day",
        "conversion": "m_to_mm_abs",
    },
    # Wind ----------------------------------------------------------------
    # If si10 is absent the script will compute it from u10 + v10 (see
    # compute_derived_variables).
    "wind": {
        "names": ["si10", "wind_speed", "10m_wind_speed"],
        "unit_in": "m/s  (10 m height)",
        "unit_out": "m/s  (2 m height, after correction)",
        "conversion": "wind_height",
    },
    "u10": {
        "names": ["u10", "10m_u_component_of_wind"],
        "unit_in": "m/s",
        "unit_out": "m/s",
        "conversion": None,
    },
    "v10": {
        "names": ["v10", "10m_v_component_of_wind"],
        "unit_in": "m/s",
        "unit_out": "m/s",
        "conversion": None,
    },
    # Dew-point (used to compute vapp) ------------------------------------
    "d2m": {
        "names": ["d2m", "2m_dewpoint_temperature", "dewpoint_temperature"],
        "unit_in": "K",
        "unit_out": "°C",
        "conversion": "K_to_C",
    },
}

SAFRAN_MAPPING: Dict = {
    # GeoSAS / SAFRAN standard column names -------------------------------
    "tasmax": {
        "names": ["Tmax", "T_max", "tmax", "tasmax", "TMAX", "TMax"],
        "unit_in": "°C",
        "unit_out": "°C",
        "conversion": None,
    },
    "tasmin": {
        "names": ["Tmin", "T_min", "tmin", "tasmin", "TMIN", "TMin"],
        "unit_in": "°C",
        "unit_out": "°C",
        "conversion": None,
    },
    "rsds": {
        "names": [
            "Rg", "GLO", "rg", "rsds", "RAY_GLOB", "Rayonnement",
            "radiation_globale",
        ],
        "unit_in": "MJ/m²/day",
        "unit_out": "MJ/m²/day",
        "conversion": None,
    },
    "prtot": {
        "names": [
            "RR", "Precip", "precip", "prtot", "PRECIP",
            "precipitation", "Precipitation",
        ],
        "unit_in": "mm/day",
        "unit_out": "mm/day",
        "conversion": None,
    },
    "etp": {
        "names": ["ETP", "Etp", "etp", "evapotranspiration", "ETref"],
        "unit_in": "mm/day",
        "unit_out": "mm/day",
        "conversion": None,
    },
    "wind": {
        "names": [
            "FF", "Wind", "wind", "Vent", "vent", "sfcWind",
            "vitesse_vent",
        ],
        "unit_in": "m/s  (10 m height)",
        "unit_out": "m/s  (2 m height, after correction)",
        "conversion": "wind_height",
    },
    "hr": {
        "names": ["HU", "Hrel", "HR", "hrel", "hu", "humidite", "humidity",
                  "humidite_relative", "relative_humidity"],
        "unit_in": "%",
        "unit_out": "%",
        "conversion": None,
    },
    # vapp may be directly available in some GeoSAS outputs ---------------
    "vapp": {
        "names": ["vapp", "Vapp", "vapour_pressure", "pression_vapeur", "ea"],
        "unit_in": "hPa",
        "unit_out": "hPa",
        "conversion": None,
    },
}

DRIAS_MAPPING: Dict = {
    # DRIAS-2020 uses bias-adjusted CMIP5/6 variable names ----------------
    "tasmax": {
        "names": ["tasmaxAdjust", "tasmax"],
        "unit_in": "K",
        "unit_out": "°C",
        "conversion": "K_to_C",
    },
    "tasmin": {
        "names": ["tasminAdjust", "tasmin"],
        "unit_in": "K",
        "unit_out": "°C",
        "conversion": "K_to_C",
    },
    "huss": {
        "names": ["hussAdjust", "huss"],
        "unit_in": "kg/kg",
        "unit_out": "g/kg  (then used to derive hr)",
        "conversion": None,   # handled in compute_derived_variables
    },
    "wind": {
        "names": ["sfcWindAdjust", "sfcWind"],
        "unit_in": "m/s  (10 m height)",
        "unit_out": "m/s  (2 m height, after correction)",
        "conversion": "wind_height",
    },
    "rsds": {
        "names": ["rsdsAdjust", "rsds"],
        "unit_in": "W/m²",
        "unit_out": "MJ/m²/day",
        "conversion": "Wm2_to_MJ",
    },
    "prtot": {
        "names": ["prtotAdjust", "prtot"],
        "unit_in": "kg/m²/s",
        "unit_out": "mm/day",
        "conversion": "kgm2s_to_mm",
    },
    "etp": {
        "names": ["evspsblpotAdjust", "evspsblpot"],
        "unit_in": "kg/m²/s",
        "unit_out": "mm/day",
        "conversion": "kgm2s_to_mm",
    },
}

# Météo-France SIM2 (SAFRAN reanalysis, "quotidien" product) --------------
# Source: Météo-France variable dictionary (cf. safranpack vignette,
# data.gouv.fr). Radiation SSI_Q is the daily-accumulated visible/global
# radiation in J/cm²/day (→ MJ/m²/day via ×0.01). Total precipitation is
# the sum of liquid (PRELIQ_Q) and solid/snow (PRENEI_Q); that sum is
# pre-computed into a 'prtot' column before mapping (see run()).
SIM2_MAPPING: Dict = {
    "tasmax": {
        "names": ["TSUP_H_Q"], "unit_in": "°C", "unit_out": "°C",
        "conversion": None,
    },
    "tasmin": {
        "names": ["TINF_H_Q"], "unit_in": "°C", "unit_out": "°C",
        "conversion": None,
    },
    "rsds": {
        "names": ["SSI_Q"], "unit_in": "J/cm²/day",
        "unit_out": "MJ/m²/day", "conversion": "Jcm2_to_MJ",
    },
    "prtot": {
        "names": ["prtot", "PRELIQ_Q"], "unit_in": "mm/day",
        "unit_out": "mm/day", "conversion": None,
    },
    "etp": {
        "names": ["ETP_Q"], "unit_in": "mm/day", "unit_out": "mm/day",
        "conversion": None,
    },
    "wind": {
        "names": ["FF_Q"], "unit_in": "m/s  (10 m height)",
        "unit_out": "m/s  (2 m height, after correction)",
        "conversion": "wind_height",
    },
    "hr": {
        "names": ["HU_Q"], "unit_in": "%", "unit_out": "%",
        "conversion": None,
    },
}

# Open-Meteo daily archive (ERA5 / ERA5-Land via api.open-meteo.com) -------
# Produced by the upstream "ERA5 Daily Extractor" tool. Unlike raw CDS, all
# variables are ALREADY in target units (°C, mm/day, MJ/m²/day, %), so no
# unit conversion is applied — EXCEPT wind, given in km/h at 10 m height
# (→ m/s at 2 m via kmh_to_ms_height). Humidity is relative humidity, so vapp
# is derived from hr + tmean (Tetens) rather than from a dew-point.
OPENMETEO_MAPPING: Dict = {
    "tasmax": {
        "names": ["temperature_2m_max"], "unit_in": "°C",
        "unit_out": "°C", "conversion": None,
    },
    "tasmin": {
        "names": ["temperature_2m_min"], "unit_in": "°C",
        "unit_out": "°C", "conversion": None,
    },
    "rsds": {
        "names": ["shortwave_radiation_sum"], "unit_in": "MJ/m²/day",
        "unit_out": "MJ/m²/day", "conversion": None,
    },
    "prtot": {
        "names": ["precipitation_sum"], "unit_in": "mm/day",
        "unit_out": "mm/day", "conversion": None,
    },
    "etp": {
        "names": ["et0_fao_evapotranspiration"], "unit_in": "mm/day",
        "unit_out": "mm/day", "conversion": None,
    },
    "wind": {
        "names": ["wind_speed_10m_mean"],
        "unit_in": "km/h  (10 m height)",
        "unit_out": "m/s  (2 m height, after correction)",
        "conversion": "kmh_to_ms_height",
    },
    "hr": {
        "names": ["relative_humidity_2m_mean"], "unit_in": "%",
        "unit_out": "%", "conversion": None,
    },
}

# INRAE AgroClim network, daily station files ------------------------------
# Source: "Daily and hourly climatic data from 54 stations of the INRAE
# Agroclim network" (Recherche Data Gouv, doi:10.57745/BQ0BWB), files
# Station_Agroclim_INRAE_{station_id}_daily_{first}_{last}.csv and variable
# dictionary variables_brutes_et_elaborees.csv. Global radiation RG is a
# daily sum in J/cm² (→ MJ/m²/day via ×0.01). Wind V is measured at 2 m on
# INRAE stations, i.e. already at the STICS reference height: no height
# correction is applied.
AGROCLIM_MAPPING: Dict = {
    "tasmax": {
        "names": ["tx", "TX"], "unit_in": "°C", "unit_out": "°C",
        "conversion": None,
    },
    "tasmin": {
        "names": ["tn", "TN"], "unit_in": "°C", "unit_out": "°C",
        "conversion": None,
    },
    "rsds": {
        "names": ["rg", "RG"], "unit_in": "J/cm²/day",
        "unit_out": "MJ/m²/day", "conversion": "Jcm2_to_MJ",
    },
    "prtot": {
        "names": ["rr", "RR"], "unit_in": "mm/day", "unit_out": "mm/day",
        "conversion": None,
    },
    "etp": {
        "names": ["etpp", "ETPP"], "unit_in": "mm/day (Penman)",
        "unit_out": "mm/day", "conversion": None,
    },
    "wind": {
        "names": ["v", "V"], "unit_in": "m/s  (2 m height)",
        "unit_out": "m/s  (2 m height)", "conversion": None,
    },
    "hr": {
        "names": ["um", "UM"], "unit_in": "%", "unit_out": "%",
        "conversion": None,
    },
}

# Name of the station identifier column in AgroClim daily files
AGROCLIM_STATION_COLUMN = "station_id"

# Aggregated lookup
ALL_MAPPINGS = {
    "era5": ERA5_MAPPING,
    "safran": SAFRAN_MAPPING,
    "drias": DRIAS_MAPPING,
    "agroclim": AGROCLIM_MAPPING,
}

# Custom source: unit choice (Galaxy select value) -> conversion key ------
CUSTOM_UNIT_CONVERSIONS: Dict[str, Dict[str, Optional[str]]] = {
    "temp": {"celsius": None, "kelvin": "K_to_C"},
    "rsds": {
        "mj_m2": None, "j_m2": "J_to_MJ", "j_cm2": "Jcm2_to_MJ",
        "w_m2": "Wm2_to_MJ",
    },
    "precip": {"mm": None, "m": "m_to_mm", "kg_m2_s": "kgm2s_to_mm"},
    "etp": {
        "mm": None, "m_neg": "m_to_mm_abs", "kg_m2_s": "kgm2s_to_mm",
    },
    "wind": {
        "ms_2m": None, "ms_10m": "wind_height",
        "kmh_2m": "kmh_to_ms", "kmh_10m": "kmh_to_ms_height",
    },
}

# =============================================================================
# CO2 CONCENTRATION TABLE  (live Mauna Loa annual mean + pre-1959 ice core)
# =============================================================================
# Annual atmospheric CO2 (ppm, dry-air mole fraction) is assembled from two
# sources instead of being supplied by the user:
#
#   • 1959 → present : NOAA/GML Mauna Loa annual mean, downloaded live from
#       https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.txt
#       (Lan, Tans & Thoning, NOAA/GML ; Keeling, Scripps Institution of
#       Oceanography).
#   • before 1959    : ice-core record adjusted for the global mean, taken
#       from NASA/GISS (Fig1A.ext) after Etheridge et al. 1996. These values
#       are hard-coded below (no extra download needed).

MLO_ANNMEAN_URL = (
    "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.txt"
)

# Pre-1959 ice-core CO2 (ppm), global-mean adjusted.
# Source: NASA/GISS Fig1A.ext  (1850-1957 Etheridge et al. 1996 ; 1958 SIO).
ICE_CORE_CO2: Dict[int, float] = {
    1850: 285.2, 1851: 285.1, 1852: 285.0, 1853: 285.0, 1854: 284.9,
    1855: 285.1, 1856: 285.4, 1857: 285.6, 1858: 285.9, 1859: 286.1,
    1860: 286.4, 1861: 286.6, 1862: 286.7, 1863: 286.8, 1864: 286.9,
    1865: 287.1, 1866: 287.2, 1867: 287.3, 1868: 287.4, 1869: 287.5,
    1870: 287.7, 1871: 287.9, 1872: 288.0, 1873: 288.2, 1874: 288.4,
    1875: 288.6, 1876: 288.7, 1877: 288.9, 1878: 289.5, 1879: 290.1,
    1880: 290.8, 1881: 291.4, 1882: 292.0, 1883: 292.5, 1884: 292.9,
    1885: 293.3, 1886: 293.8, 1887: 294.0, 1888: 294.1, 1889: 294.2,
    1890: 294.4, 1891: 294.6, 1892: 294.8, 1893: 294.7, 1894: 294.8,
    1895: 294.8, 1896: 294.9, 1897: 294.9, 1898: 294.9, 1899: 295.3,
    1900: 295.7, 1901: 296.2, 1902: 296.6, 1903: 297.0, 1904: 297.5,
    1905: 298.0, 1906: 298.4, 1907: 298.8, 1908: 299.3, 1909: 299.7,
    1910: 300.1, 1911: 300.6, 1912: 301.0, 1913: 301.3, 1914: 301.4,
    1915: 301.6, 1916: 302.0, 1917: 302.4, 1918: 302.8, 1919: 303.0,
    1920: 303.4, 1921: 303.7, 1922: 304.1, 1923: 304.5, 1924: 304.9,
    1925: 305.3, 1926: 305.8, 1927: 306.2, 1928: 306.6, 1929: 307.2,
    1930: 307.5, 1931: 308.0, 1932: 308.3, 1933: 308.9, 1934: 309.3,
    1935: 309.7, 1936: 310.1, 1937: 310.6, 1938: 311.0, 1939: 311.2,
    1940: 311.3, 1941: 311.0, 1942: 310.7, 1943: 310.5, 1944: 310.2,
    1945: 310.3, 1946: 310.3, 1947: 310.4, 1948: 310.5, 1949: 310.9,
    1950: 311.3, 1951: 311.8, 1952: 312.2, 1953: 312.6, 1954: 313.2,
    1955: 313.7, 1956: 314.3, 1957: 314.8, 1958: 315.34,
}

# Offline snapshot of the Mauna Loa annual mean (ppm), used ONLY if the live
# download fails. NOAA file creation Oct-2024, covers 1959-2023.
MLO_CO2_FALLBACK: Dict[int, float] = {
    1959: 315.98, 1960: 316.91, 1961: 317.64, 1962: 318.45, 1963: 318.99,
    1964: 319.62, 1965: 320.04, 1966: 321.37, 1967: 322.18, 1968: 323.05,
    1969: 324.62, 1970: 325.68, 1971: 326.32, 1972: 327.46, 1973: 329.68,
    1974: 330.19, 1975: 331.13, 1976: 332.03, 1977: 333.84, 1978: 335.41,
    1979: 336.84, 1980: 338.76, 1981: 340.12, 1982: 341.48, 1983: 343.15,
    1984: 344.87, 1985: 346.35, 1986: 347.61, 1987: 349.31, 1988: 351.69,
    1989: 353.20, 1990: 354.45, 1991: 355.70, 1992: 356.54, 1993: 357.21,
    1994: 358.96, 1995: 360.97, 1996: 362.74, 1997: 363.88, 1998: 366.84,
    1999: 368.54, 2000: 369.71, 2001: 371.32, 2002: 373.45, 2003: 375.98,
    2004: 377.70, 2005: 379.98, 2006: 382.09, 2007: 384.02, 2008: 385.83,
    2009: 387.64, 2010: 390.10, 2011: 391.85, 2012: 394.06, 2013: 396.74,
    2014: 398.81, 2015: 401.01, 2016: 404.41, 2017: 406.76, 2018: 408.72,
    2019: 411.65, 2020: 414.21, 2021: 416.41, 2022: 418.53, 2023: 421.08,
}


def fetch_mauna_loa_co2() -> pd.DataFrame:
    """
    Download the NOAA/GML Mauna Loa annual-mean CO2 series (1959 → present).

    The remote file is whitespace-delimited with '#' comment lines and three
    columns: year, mean, unc. If the download fails (no network, NOAA
    unreachable...), a bundled snapshot is used instead.

    Returns
    -------
    DataFrame with columns ['year', 'co2'].
    """
    try:
        mlo = pd.read_csv(
            MLO_ANNMEAN_URL,
            comment="#",
            sep=r"\s+",
            names=["year", "co2", "unc"],
            usecols=["year", "co2"],
        )
        mlo["year"] = mlo["year"].astype(int)
        logging.info(
            f"  Mauna Loa CO2 downloaded: {len(mlo)} years "
            f"[{mlo['year'].min()}-{mlo['year'].max()}]"
        )
        return mlo[["year", "co2"]]
    except Exception as exc:  # noqa: BLE001 – we want any failure to fall back
        logging.warning(
            f"  Could not download Mauna Loa CO2 ({exc}); "
            "falling back to the bundled snapshot (1959-2023)."
        )
        return pd.DataFrame(
            {"year": list(MLO_CO2_FALLBACK),
             "co2": list(MLO_CO2_FALLBACK.values())}
        )


def build_co2_table() -> pd.DataFrame:
    """
    Assemble the full annual CO2 table used to fill the STICS 'co2' column:

      • 1959 → present : live Mauna Loa annual mean (NOAA/GML)
      • before 1959    : ice-core record (NASA/GISS, Etheridge et al. 1996)

    Mauna Loa is authoritative from its first year on; the ice-core values are
    only used for years strictly before the Mauna Loa record starts.

    Returns
    -------
    DataFrame with columns ['year', 'co2'] sorted by year.
    """
    mlo = fetch_mauna_loa_co2()
    mlo_start = int(mlo["year"].min())

    ice = pd.DataFrame(
        {"year": list(ICE_CORE_CO2), "co2": list(ICE_CORE_CO2.values())}
    )
    ice = ice[ice["year"] < mlo_start]

    co2 = (
        pd.concat([ice, mlo], ignore_index=True)
        .drop_duplicates(subset="year", keep="last")
        .sort_values("year")
        .reset_index(drop=True)
    )
    logging.info(
        f"  CO2 table ready: {len(co2)} years "
        f"[{co2['year'].min()}-{co2['year'].max()}] "
        f"(ice core < {mlo_start}, Mauna Loa >= {mlo_start})"
    )
    return co2


# =============================================================================
# UNIT CONVERSION
# =============================================================================

def apply_conversion(
    data: Union[xr.DataArray, pd.Series, np.ndarray],
    conversion_key: Optional[str],
    wind_factor: float = 0.7,
) -> Union[xr.DataArray, pd.Series, np.ndarray]:
    """Apply a named unit conversion. Returns data unchanged if key None."""
    if conversion_key is None:
        return data

    conversions = {
        "K_to_C": lambda x: x - 273.15,
        "J_to_MJ": lambda x: x / 1_000_000,
        "m_to_mm": lambda x: x * 1_000,
        "m_to_mm_abs": lambda x: np.abs(x) * 1_000,
        # W/m² × s/day ÷ 10⁶
        "Wm2_to_MJ": lambda x: x * 86_400 / 1_000_000,
        # J/cm²/day → MJ/m²/day
        "Jcm2_to_MJ": lambda x: x * 0.01,
        # kg/m²/s → mm/day
        "kgm2s_to_mm": lambda x: x * 86_400,
        "wind_height": lambda x: x * wind_factor,
        # km/h → m/s
        "kmh_to_ms": lambda x: x / 3.6,
        # Open-Meteo wind is km/h at 10 m: convert to m/s AND apply the
        # 10 m → 2 m height correction in one step.
        "kmh_to_ms_height": lambda x: (x / 3.6) * wind_factor,
    }

    if conversion_key not in conversions:
        raise ValueError(
            f"Unknown conversion key '{conversion_key}'. "
            f"Available: {list(conversions)}"
        )
    return conversions[conversion_key](data)


# =============================================================================
# DATA LOADING
# =============================================================================

def detect_format(path: str) -> str:
    """Guess file format from extension."""
    suffix = Path(path).suffix.lower().lstrip(".")
    return suffix if suffix else "unknown"


def read_tabular_robust(path: str) -> pd.DataFrame:
    """
    Read a delimited text file (CSV / GeoCSV / TSV / GeoSAS export) while
    coping with two common quirks:

      * a metadata pre-amble made of lines starting with '#'
      * an unknown delimiter (',', ';', tab or '|')  — GeoSAS / SAFRAN
        exports are frequently semicolon-separated.

    The delimiter is sniffed from the first real (non-comment, non-blank)
    lines; if sniffing fails we keep the candidate that splits the header
    into the most fields.
    """
    import csv as _csv

    sample_lines = []
    with open(path, "r", newline="") as fh:
        for line in fh:
            if line.strip() and not line.lstrip().startswith("#"):
                sample_lines.append(line)
                if len(sample_lines) >= 5:
                    break
    if not sample_lines:
        raise ValueError(
            f"File '{path}' contains no data rows "
            "(only comments/blank lines)."
        )

    sample = "".join(sample_lines)
    candidates = [",", ";", "\t", "|"]
    try:
        sniffed = _csv.Sniffer().sniff(
            sample, delimiters="".join(candidates)
        )
        delimiter = sniffed.delimiter
    except _csv.Error:
        header = sample_lines[0]
        delimiter = max(candidates, key=header.count)
        if header.count(delimiter) == 0:
            delimiter = ","  # single-column file

    df = pd.read_csv(path, sep=delimiter, engine="python", comment="#")
    # Strip surrounding whitespace from column names (GeoSAS adds spaces)
    df.columns = [str(c).strip() for c in df.columns]
    logging.info(
        f"  tabular read: delimiter={delimiter!r}, "
        f"{df.shape[0]} rows × {df.shape[1]} cols"
    )
    return df


def load_single_file(
    path: str,
    fmt: str = "auto",
) -> Tuple[Union[xr.Dataset, pd.DataFrame], str]:
    """
    Load a climate data file.

    Returns
    -------
    (data, dtype) where dtype is "xarray" or "dataframe".
    """
    if fmt in ("auto", ""):
        fmt = detect_format(path)

    # NetCDF --------------------------------------------------------------
    if fmt in ("nc", "netcdf", "netcdf4", "nc4"):
        return xr.open_dataset(path), "xarray"

    # CSV / GeoCSV / TSV / tabular (Galaxy default) -----------------------
    # All delimited text formats go through the robust reader, which
    # auto-detects the separator and skips '#' metadata lines.
    if fmt in ("csv", "geocsv", "tsv", "tabular", "tab", "txt"):
        return read_tabular_robust(path), "dataframe"

    # Fall-back: try NetCDF then robust tabular --------------------------
    logging.warning(f"Unknown format '{fmt}', attempting NetCDF then tabular.")
    try:
        return xr.open_dataset(path), "xarray"
    except Exception:
        return read_tabular_robust(path), "dataframe"


def load_drias_zip(zip_path: str, extract_dir: str) -> Dict[str, xr.Dataset]:
    """
    Extract a ZIP of DRIAS NetCDF files and return a dict
    ``{internal_var_name: xr.Dataset}``.
    """
    import glob

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    patterns = {
        "tasmax": "*tasmax*.nc",
        "tasmin": "*tasmin*.nc",
        "huss": "*huss*.nc",
        "wind": "*sfcWind*.nc",
        "rsds": "*rsds*.nc",
        "prtot": "*prtot*.nc",
        "etp": "*evspsblpot*.nc",
    }

    datasets: Dict[str, xr.Dataset] = {}
    for varname, pattern in patterns.items():
        hits = glob.glob(
            os.path.join(extract_dir, "**", pattern), recursive=True
        )
        if not hits:
            hits = glob.glob(os.path.join(extract_dir, pattern))
        if hits:
            datasets[varname] = xr.open_dataset(sorted(hits)[0])
            logging.info(f"  DRIAS {varname}: {Path(sorted(hits)[0]).name}")
        else:
            logging.warning(
                f"  DRIAS: no file found for '{varname}' "
                f"(pattern: {pattern})"
            )

    return datasets


# =============================================================================
# VARIABLE MAPPING HELPERS
# =============================================================================

def find_var(
    data: Union[xr.Dataset, pd.DataFrame],
    candidates: list,
) -> Optional[str]:
    """Return the first candidate name that exists in the dataset/dataframe."""
    existing = (
        list(data.data_vars) if isinstance(data, xr.Dataset)
        else list(data.columns)
    )
    for name in candidates:
        if name in existing:
            return name
    return None


def pick_drias_variable(ds: xr.Dataset, candidates: list) -> xr.DataArray:
    """
    Return the climate variable of a single-variable DRIAS file.

    Known names are tried first; otherwise the first data variable with a
    time dimension is used (this skips grid-mapping variables such as
    'Lambert_Conformal' and auxiliary lat/lon arrays).
    """
    found = find_var(ds, candidates)
    if found is not None:
        return ds[found]
    for name, da in ds.data_vars.items():
        if any(d in da.dims for d in ("time", "valid_time")):
            return da
    raise ValueError(
        f"No time-dependent variable found in DRIAS file "
        f"(variables: {list(ds.data_vars)})."
    )


def build_custom_mapping(df: pd.DataFrame, args: argparse.Namespace) -> Dict:
    """
    Build a mapping table for the 'custom' source from the 1-based column
    indices and unit choices given on the command line.
    """
    columns = {
        "tasmax": (args.col_tasmax, CUSTOM_UNIT_CONVERSIONS["temp"][args.unit_temp]),
        "tasmin": (args.col_tasmin, CUSTOM_UNIT_CONVERSIONS["temp"][args.unit_temp]),
        "rsds": (args.col_rsds, CUSTOM_UNIT_CONVERSIONS["rsds"][args.unit_rsds]),
        "prtot": (args.col_prtot, CUSTOM_UNIT_CONVERSIONS["precip"][args.unit_precip]),
        "etp": (args.col_etp, CUSTOM_UNIT_CONVERSIONS["etp"][args.unit_etp]),
        "wind": (args.col_wind, CUSTOM_UNIT_CONVERSIONS["wind"][args.unit_wind]),
        "hr": (args.col_hr, None),
        "vapp": (args.col_vapp, None),
    }
    mapping: Dict = {}
    for internal_name, (index, conversion) in columns.items():
        if index is None:
            continue
        mapping[internal_name] = {
            "names": [column_name_from_index(df, index)],
            "conversion": conversion,
        }
    return mapping


def column_name_from_index(df: pd.DataFrame, index: int) -> str:
    """Translate a 1-based Galaxy column index into a DataFrame column."""
    if not 1 <= index <= len(df.columns):
        raise ValueError(
            f"Column {index} does not exist: the file has "
            f"{len(df.columns)} columns ({list(df.columns)})."
        )
    return df.columns[index - 1]


def apply_mapping(
    data: Union[xr.Dataset, pd.DataFrame],
    mapping: Dict,
    wind_factor: float = 0.7,
) -> Dict:
    """
    Scan *data* for every variable defined in *mapping*, apply unit
    conversions and return a dict ``{internal_name: array-like}``.
    """
    result: Dict = {}
    for internal_name, info in mapping.items():
        found = find_var(data, info["names"])
        if found is None:
            logging.debug(
                f"  '{internal_name}' not found (tried: {info['names']})"
            )
            continue

        raw = (
            data[found] if isinstance(data, xr.Dataset)
            else data[found]
        )
        converted = apply_conversion(raw, info.get("conversion"), wind_factor)
        result[internal_name] = converted
        logging.info(
            f"  mapped '{found}' → '{internal_name}'  "
            f"(conversion: {info.get('conversion', 'none')})"
        )

    return result


# =============================================================================
# DERIVED VARIABLE COMPUTATION
# =============================================================================

def _where(condition, x, y, dtype="xarray"):
    """Conditional where() for both xarray and numpy/pandas."""
    if dtype == "xarray":
        return xr.where(condition, x, y)
    return np.where(condition, x, y)


def compute_derived_variables(
    vars_dict: Dict,
    wind_factor: float = 0.7,
) -> Dict:
    """
    Compute any missing derived variables in-place:

    - tmean       = (tasmax + tasmin) / 2
    - psat        = Magnus–Tetens saturation vapour pressure (for huss path)
    - hr          = relative humidity from huss + psat   (DRIAS path)
    - vapp        = vapour pressure from hr + tmean      (DRIAS / SAFRAN path)
    - vapp        = August–Roche–Magnus from d2m         (ERA5 path)
    - wind        = √(u10² + v10²) × wind_factor         (ERA5 component path)
    """

    if not vars_dict:
        # Nothing was mapped; let the caller raise a helpful error instead of
        # crashing here with an opaque StopIteration.
        return vars_dict

    # Detect whether we are working with xarray or numpy/pandas
    sample = next(iter(vars_dict.values()))
    is_xr = isinstance(sample, (xr.DataArray, xr.Dataset))
    dtype = "xarray" if is_xr else "pandas"

    # --- tmean -----------------------------------------------------------
    have_tmax_tmin = "tasmax" in vars_dict and "tasmin" in vars_dict
    if "tmean" not in vars_dict and have_tmax_tmin:
        vars_dict["tmean"] = 0.5 * (vars_dict["tasmax"] + vars_dict["tasmin"])
        logging.info("  derived: tmean = (tasmax + tasmin) / 2")

    tmean = vars_dict.get("tmean")

    # --- psat (for DRIAS: huss → hr) -------------------------------------
    if tmean is not None and "huss" in vars_dict and "hr" not in vars_dict:
        psat = _where(
            tmean < 0,
            10 ** (2.7862 + (9.7561 * tmean) / (272.67 + tmean)),
            10 ** (2.7862 + (7.5526 * tmean) / (239.21 + tmean)),
            dtype=dtype,
        )
        # huss arrives in kg/kg; convert to g/kg first
        huss_gkg = vars_dict["huss"] * 1_000
        hr = huss_gkg / 0.622 / psat * 10_000
        hr = _where(hr > 100, 100, hr, dtype=dtype)
        vars_dict["hr"] = hr
        vars_dict["huss"] = huss_gkg
        logging.info("  derived: hr from huss + psat (Magnus–Tetens)")

    # --- vapp from hr + tmean (DRIAS / SAFRAN) ---------------------------
    if "vapp" not in vars_dict and "hr" in vars_dict and tmean is not None:
        TVAR = 6.1070 * (
            (1 + (2.0 ** 0.5) * np.sin((tmean * 0.017453293) / 3)) ** 8.827
        )
        vars_dict["vapp"] = (vars_dict["hr"] / 100) * TVAR
        logging.info("  derived: vapp from hr + tmean (Tetens)")

    # --- vapp from ERA5 dew-point ----------------------------------------
    if "vapp" not in vars_dict and "d2m" in vars_dict:
        td_c = vars_dict["d2m"]  # already converted to °C
        vars_dict["vapp"] = 6.1078 * np.exp(17.269 * td_c / (237.3 + td_c))
        logging.info("  derived: vapp from d2m (August–Roche–Magnus)")

    # --- wind from u10 + v10 (ERA5 components) ---------------------------
    have_uv = "u10" in vars_dict and "v10" in vars_dict
    if "wind" not in vars_dict and have_uv:
        vars_dict["wind"] = (
            np.sqrt(vars_dict["u10"] ** 2 + vars_dict["v10"] ** 2)
            * wind_factor
        )
        logging.info(f"  derived: wind = √(u10²+v10²) × {wind_factor}")

    return vars_dict


# =============================================================================
# SPATIAL PROCESSING
# =============================================================================

def assign_cells_from_shapefile(
    ds: xr.Dataset,
    shapefile_path: str,
    epsg: str,
) -> xr.Dataset:
    """Rasterize the cell shapefile onto the xarray grid."""
    ds.rio.write_crs(epsg, inplace=True)
    x_dim, y_dim = spatial_dims(ds)
    cell_gdf = gpd.read_file(shapefile_path).to_crs(ds.rio.crs)

    if "cell" not in cell_gdf.columns:
        raise ValueError(
            "The shapefile must contain a column named 'cell' with "
            "numeric cell IDs."
        )

    cell_raster = rasterize(
        [(geom, int(val)) for geom, val in
         zip(cell_gdf.geometry, cell_gdf["cell"])],
        out_shape=(ds.sizes[y_dim], ds.sizes[x_dim]),
        transform=ds.rio.transform(),
        fill=-1,
    )
    ds["cell_id"] = ((y_dim, x_dim), cell_raster)
    logging.info(
        f"  rasterised {len(cell_gdf)} cells onto "
        f"{ds.sizes[x_dim]}×{ds.sizes[y_dim]} grid"
    )
    return ds


def spatial_dims(ds: xr.Dataset) -> Tuple[str, str]:
    """
    Return the (x, y) dimension names of a gridded dataset: 'x'/'y' for
    projected grids (SAFRAN, DRIAS), 'longitude'/'latitude' for ERA5 CDS
    files, 'lon'/'lat' for others (detected by rioxarray).
    """
    try:
        return ds.rio.x_dim, ds.rio.y_dim
    except Exception as exc:  # rioxarray raises MissingSpatialDimensionError
        raise ValueError(
            "Cannot find the spatial dimensions of the NetCDF file "
            "(expected x/y, longitude/latitude or lon/lat). "
            f"Dimensions found: {list(ds.dims)}"
        ) from exc


def assign_cells_per_pixel(ds: xr.Dataset) -> xr.Dataset:
    """Give every grid pixel its own integer cell ID (row-major order)."""
    x_dim, y_dim = spatial_dims(ds)
    n_y, n_x = ds.sizes[y_dim], ds.sizes[x_dim]
    yy, xx = np.mgrid[0:n_y, 0:n_x]
    ds["cell_id"] = ((y_dim, x_dim), (yy * n_x + xx).astype(int))
    logging.warning(
        "No shapefile provided; each grid pixel is treated as its own "
        f"cell (IDs 0..{n_y * n_x - 1}, row-major order)."
    )
    return ds


def build_xarray_dataset(vars_dict: Dict) -> xr.Dataset:
    """Merge DataArray-valued entries into a single xr.Dataset."""
    parts = []
    for name, val in vars_dict.items():
        if isinstance(val, xr.DataArray):
            parts.append(val.to_dataset(name=name))
        elif isinstance(val, xr.Dataset):
            parts.append(val)
        # numpy/pandas arrays are ignored here (handled via DataFrame path)
    return xr.merge(parts, compat="override")


def xarray_to_flat_df(
    ds: xr.Dataset,
    drop_cols: Optional[list] = None,
) -> pd.DataFrame:
    """Flatten a gridded Dataset to a DataFrame, drop NaN rows."""
    df = ds.to_dataframe().reset_index()
    # Drop rows where all climate variables are NaN (ocean / outside domain)
    key_var_names = ["tasmin", "tasmax", "prtot", "rsds"]
    key_vars = [v for v in key_var_names if v in df.columns]
    if key_vars:
        df = df.dropna(subset=key_vars[:1])
    for col in drop_cols or []:
        if col in df.columns:
            df = df.drop(columns=[col])
    return df


# =============================================================================
# DATE / TIME COLUMNS
# =============================================================================

DATE_COLUMN_CANDIDATES = [
    "time", "valid_time", "date", "Date", "DATE", "Time", "date_j",
]


def parse_dates(values: pd.Series) -> pd.Series:
    """
    Parse a date column. Integer dates such as Météo-France SIM2
    ``20200131`` are read as YYYYMMDD (and not as epoch nanoseconds).
    """
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_datetime(values.astype("int64").astype(str),
                              format="%Y%m%d")
    return pd.to_datetime(values)


def add_temporal_columns(
    df: pd.DataFrame,
    time_col: Optional[str] = None,
) -> pd.DataFrame:
    """Add Year / Month / Day of month / Day of year from a time column."""
    if time_col is None:
        time_col = next(
            (c for c in DATE_COLUMN_CANDIDATES if c in df.columns), None
        )
    if time_col is None:
        raise ValueError(
            "Cannot find a date/time column. "
            f"Expected one of: {', '.join(DATE_COLUMN_CANDIDATES)}."
        )

    dt = parse_dates(df[time_col])
    df["Year"] = dt.dt.year
    df["Month"] = dt.dt.month
    df["Day of month"] = dt.dt.day
    df["Day of year"] = dt.dt.dayofyear
    return df


# =============================================================================
# STICS FILE EXPORT
# =============================================================================

STICS_COLUMNS = [
    "Cell ID",
    "Year", "Month", "Day of month", "Day of year",
    "tasmin", "tasmax", "rsds", "etp", "prtot", "wind", "vapp",
]

# Space-separated, right-aligned columns, as in the weather files shipped
# with JavaSTICS ("lusigna 1996  1  1   1     8.0   11.1 ..."): station,
# year, month, day, day of year, then the 8 daily values and CO2. Every
# field is preceded by at least one space, whatever its width.
STICS_LINE_FORMAT = "%d %4d %2d %2d %3d" + " %7.2f" * 8


def write_stics_file(df_y: pd.DataFrame, out_path: str) -> None:
    """Write one STICS weather file (one cell, one year, no header)."""
    values = df_y.to_numpy(dtype=float)
    values[np.isnan(values)] = STICS_MISSING
    with open(out_path, "w", encoding="ascii", newline="\n") as fh:
        np.savetxt(fh, values, fmt=STICS_LINE_FORMAT)


def export_stics_files(
    df: pd.DataFrame,
    co2_df: pd.DataFrame,
    output_dir: str,
) -> int:
    """
    Write one STICS file per (cell × year).

    Returns
    -------
    Total number of files written.
    """
    # Normalise CO2 table
    co2_df = co2_df.drop(columns=["cell"], errors="ignore").copy()
    co2_df["year"] = co2_df["year"].astype(int)

    # Ensure cell ID column exists
    if "Cell ID" not in df.columns:
        raise ValueError(
            "Column 'Cell ID' is missing. "
            "Check shapefile rasterisation or cell_id_column parameter."
        )

    df = df[df["Cell ID"] != -1].copy()

    # Every STICS column must be present, in the STICS order. A variable
    # that the source does not provide is written as missing (-999.9).
    for col in STICS_COLUMNS:
        if col not in df.columns:
            logging.warning(
                f"  '{col}' not available from this source: written as "
                f"{STICS_MISSING} (missing value) in every STICS file"
            )
            df[col] = STICS_MISSING
    df = df[STICS_COLUMNS]

    n_missing = int(df[STICS_COLUMNS[5:]].isna().sum().sum())
    if n_missing:
        logging.warning(
            f"  {n_missing} missing daily values written as {STICS_MISSING}"
        )

    cells = sorted(df["Cell ID"].unique())
    n_cells = len(cells)
    files_written = 0

    logging.info(f"  exporting {n_cells} cells to {output_dir}")

    for idx, cell_id in enumerate(cells):
        df_c = df[df["Cell ID"] == cell_id]
        c_dir = os.path.join(output_dir, str(int(cell_id)))
        os.makedirs(c_dir, exist_ok=True)

        years = sorted(df_c["Year"].unique())
        logging.info(
            f"  [{idx + 1:>4}/{n_cells}] cell {int(cell_id):>6} – "
            f"{len(years)} years [{min(years)}–{max(years)}]"
        )

        for year in years:
            df_y = df_c[df_c["Year"] == year].copy()

            co2_y = co2_df[co2_df["year"] == int(year)]
            df_y = df_y.merge(
                co2_y, left_on="Year", right_on="year", how="left"
            )
            df_y = df_y.drop(columns=["year"], errors="ignore")

            out_path = os.path.join(c_dir, f"{int(cell_id)}.{int(year)}")
            write_stics_file(df_y[STICS_COLUMNS + ["co2"]], out_path)
            files_written += 1

    logging.info(f"  {files_written} STICS files written")
    return files_written


# =============================================================================
# ZIP OUTPUT
# =============================================================================

def zip_directory(src_dir: str, dst_zip: str) -> None:
    """Recursively zip *src_dir* into *dst_zip*."""
    with zipfile.ZipFile(dst_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(src_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                arcname = os.path.relpath(fpath, os.path.dirname(src_dir))
                zf.write(fpath, arcname)
    logging.info(f"  archive written: {dst_zip}")


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def extract_shapefile(shapefile_zip: str, tmpdir: str) -> str:
    """Extract a zipped shapefile and return the path of its .shp file."""
    shp_dir = os.path.join(tmpdir, "shapefile")
    os.makedirs(shp_dir, exist_ok=True)
    with zipfile.ZipFile(shapefile_zip, "r") as zf:
        zf.extractall(shp_dir)
    shp_hits = sorted(Path(shp_dir).rglob("*.shp"))
    if not shp_hits:
        raise ValueError("No .shp file found inside the shapefile ZIP.")
    logging.info(f"shapefile: {shp_hits[0].name}")
    return str(shp_hits[0])


def gridded_to_dataframe(
    vars_dict: Dict,
    epsg: str,
    shapefile_path: Optional[str],
) -> pd.DataFrame:
    """Assign cells to a gridded dataset and flatten it to a DataFrame."""
    clim_ds = build_xarray_dataset(vars_dict)
    clim_ds.rio.write_crs(epsg, inplace=True)

    if shapefile_path:
        logging.info("--- Rasterising cells ---")
        clim_ds = assign_cells_from_shapefile(clim_ds, shapefile_path, epsg)
    else:
        clim_ds = assign_cells_per_pixel(clim_ds)

    df = xarray_to_flat_df(clim_ds, drop_cols=["spatial_ref"])
    df["Cell ID"] = df["cell_id"].astype(int)
    df = add_temporal_columns(df)
    return average_pixels_per_cell(df)


DATE_KEYS = ["Cell ID", "Year", "Month", "Day of month", "Day of year"]


def average_pixels_per_cell(df: pd.DataFrame) -> pd.DataFrame:
    """
    STICS needs one row per day. When a shapefile cell covers several grid
    pixels, the daily values of these pixels are averaged.
    """
    df = df[df["Cell ID"] != -1]
    pixels = df.groupby(DATE_KEYS).size()
    if pixels.max() <= 1:
        return df
    n_cells = int((pixels.groupby(level="Cell ID").max() > 1).sum())
    logging.info(
        f"  {n_cells} cell(s) cover several grid pixels (up to "
        f"{int(pixels.max())}): daily values averaged over each cell"
    )
    value_cols = [c for c in STICS_COLUMNS[5:] if c in df.columns]
    return df.groupby(DATE_KEYS, as_index=False)[value_cols].mean()


def check_one_row_per_day(df: pd.DataFrame) -> None:
    """Fail on duplicated (cell, date) rows in tabular data."""
    dup = df.duplicated(subset=DATE_KEYS, keep=False)
    if dup.any():
        sample = df.loc[dup, DATE_KEYS].head(3).to_dict("records")
        raise ValueError(
            f"{int(dup.sum())} rows share the same cell/site and date "
            f"(e.g. {sample}). If the file holds several sites, select "
            "the column that identifies them."
        )


def assign_cell_ids(df: pd.DataFrame, cell_col: Optional[str]) -> pd.DataFrame:
    """
    Fill the 'Cell ID' column from *cell_col*.

    - no column: every row belongs to a single site, Cell ID 1;
    - integer IDs: used as is;
    - other IDs (site codes...): numbered 1..N in sorted order, the
      correspondence being written to the log.
    """
    if cell_col is None:
        logging.info(
            "  no cell/site ID column selected: all rows are treated as "
            "a single site (Cell ID 1)"
        )
        df["Cell ID"] = 1
        return df

    logging.info(f"  cell/site ID column: '{cell_col}'")
    ids = pd.to_numeric(df[cell_col], errors="coerce")
    is_integer = (
        ids.notna().all()
        and np.all(np.mod(ids, 1) == 0)
    )
    if is_integer:
        df["Cell ID"] = ids.astype(int)
        return df

    codes, uniques = pd.factorize(df[cell_col], sort=True)
    df["Cell ID"] = np.where(codes >= 0, codes + 1, -1)
    logging.info(
        f"  '{cell_col}' does not hold integer IDs; sites numbered 1..N:"
    )
    for number, label in enumerate(uniques, start=1):
        logging.info(f"    {number} = {label}")
    return df


def load_drias(
    args: argparse.Namespace,
    tmpdir: str,
    shapefile_path: Optional[str],
) -> pd.DataFrame:
    """DRIAS-2020 branch: one NetCDF file per variable inside a ZIP."""
    if not shapefile_path:
        raise ValueError(
            "DRIAS NetCDF data requires --shapefile_zip to assign cells."
        )

    logging.info("--- Loading DRIAS NetCDF files ---")
    drias_dir = os.path.join(tmpdir, "drias")
    os.makedirs(drias_dir, exist_ok=True)
    drias_datasets = load_drias_zip(args.drias_zip, drias_dir)
    if not drias_datasets:
        raise ValueError("No DRIAS NetCDF file found in the ZIP archive.")

    vars_dict: Dict = {}
    for var_key, ds in drias_datasets.items():
        info = DRIAS_MAPPING[var_key]
        da = pick_drias_variable(ds, info["names"])
        vars_dict[var_key] = apply_conversion(
            da, info["conversion"], args.wind_correction_factor
        )
        logging.info(
            f"  mapped '{da.name}' → '{var_key}'  "
            f"(conversion: {info['conversion']})"
        )

    logging.info("--- Computing derived variables ---")
    vars_dict = compute_derived_variables(
        vars_dict, args.wind_correction_factor
    )
    return gridded_to_dataframe(vars_dict, args.epsg, shapefile_path)


def load_input_files(
    paths: List[str],
    fmt: str,
) -> Tuple[Union[xr.Dataset, pd.DataFrame], str]:
    """Load one file, or concatenate several tabular files (one per site)."""
    if len(paths) == 1:
        return load_single_file(paths[0], fmt)

    frames = []
    for path in paths:
        data, data_type = load_single_file(path, fmt)
        if data_type != "dataframe":
            raise ValueError(
                "Several input files can only be combined when they are "
                "tabular (CSV / TSV)."
            )
        frames.append(data)
    logging.info(f"  {len(frames)} tabular files concatenated")
    return pd.concat(frames, ignore_index=True), "dataframe"


def select_mapping(
    raw_data: Union[xr.Dataset, pd.DataFrame],
    args: argparse.Namespace,
) -> Tuple[Union[xr.Dataset, pd.DataFrame], Dict]:
    """Choose the variable mapping table for a single-file source."""
    is_tabular = isinstance(raw_data, pd.DataFrame)

    if args.source_type == "custom":
        if not is_tabular:
            raise ValueError("The custom source only accepts tabular files.")
        return raw_data, build_custom_mapping(raw_data, args)

    base_mapping = ALL_MAPPINGS[args.source_type]

    # Météo-France SIM2 (SAFRAN reanalysis): detected by its signature
    # columns, switched to the dedicated mapping with correct units.
    if args.source_type == "safran" and is_tabular:
        sim2_signature = {"TINF_H_Q", "TSUP_H_Q", "SSI_Q"}
        if sim2_signature & set(raw_data.columns):
            logging.info("  detected Météo-France SIM2 columns → SIM2 mapping")
            raw_data = raw_data.copy()
            # Total precipitation = liquid + solid (snow)
            if {"PRELIQ_Q", "PRENEI_Q"} <= set(raw_data.columns):
                raw_data["prtot"] = (
                    raw_data["PRELIQ_Q"].fillna(0)
                    + raw_data["PRENEI_Q"].fillna(0)
                )
                logging.info("  derived: prtot = PRELIQ_Q + PRENEI_Q")
            base_mapping = SIM2_MAPPING

    # Open-Meteo daily archive (ERA5 Daily Extractor output): Open-Meteo
    # column names, units already converted except wind (km/h).
    if args.source_type == "era5" and is_tabular:
        openmeteo_signature = {
            "temperature_2m_max", "et0_fao_evapotranspiration",
            "shortwave_radiation_sum",
        }
        if openmeteo_signature & set(raw_data.columns):
            logging.info(
                "  detected Open-Meteo columns → Open-Meteo mapping "
                "(units already converted; wind km/h→m/s)"
            )
            base_mapping = OPENMETEO_MAPPING

    return raw_data, base_mapping


def load_single_source(
    args: argparse.Namespace,
    shapefile_path: Optional[str],
) -> pd.DataFrame:
    """ERA5 / SAFRAN / AgroClim / custom branch (one or more files)."""
    logging.info(f"--- Loading {args.source_type} file(s) ---")
    raw_data, data_type = load_input_files(args.input_file, args.input_format)
    logging.info(f"  loaded as {data_type} (format: {args.input_format})")

    raw_data, base_mapping = select_mapping(raw_data, args)
    vars_dict = apply_mapping(
        raw_data, base_mapping, args.wind_correction_factor
    )

    if not vars_dict:
        present = (
            list(raw_data.data_vars) if isinstance(raw_data, xr.Dataset)
            else list(raw_data.columns)
        )
        expected = sorted({
            alias
            for info in base_mapping.values()
            for alias in info["names"]
        })
        raise ValueError(
            "No climate variable could be mapped for source "
            f"'{args.source_type}'.\n"
            f"  Variables found in the file : {present}\n"
            f"  Names expected ({args.source_type}) : {expected}\n"
            "  → Check the delimiter / header of your file, or use the "
            "'custom' source to select the columns yourself."
        )

    logging.info("--- Computing derived variables ---")
    vars_dict = compute_derived_variables(
        vars_dict, args.wind_correction_factor
    )

    # ---- gridded NetCDF ----------------------------------------------
    if data_type == "xarray":
        return gridded_to_dataframe(vars_dict, args.epsg, shapefile_path)

    # ---- tabular -----------------------------------------------------
    df = raw_data.copy()
    for col, series in vars_dict.items():
        df[col] = series

    if args.source_type == "agroclim":
        if AGROCLIM_STATION_COLUMN not in df.columns:
            raise ValueError(
                f"Column '{AGROCLIM_STATION_COLUMN}' not found: this does "
                "not look like an AgroClim daily station file. Columns "
                f"present: {list(raw_data.columns)}"
            )
        cell_col: Optional[str] = AGROCLIM_STATION_COLUMN
    elif args.cell_id_column_index is not None:
        cell_col = column_name_from_index(raw_data, args.cell_id_column_index)
    else:
        cell_col = None
    df = assign_cell_ids(df, cell_col)

    time_col = (
        column_name_from_index(raw_data, args.col_date)
        if args.source_type == "custom" else None
    )
    df = add_temporal_columns(df, time_col)
    check_one_row_per_day(df)
    return df


def run(args: argparse.Namespace) -> None:
    logging.info(f"=== Climate to STICS v{__version__} ===")
    logging.info(f"source_type : {args.source_type}")
    logging.info(f"epsg        : {args.epsg}")
    logging.info(f"wind factor : {args.wind_correction_factor}")

    # Build CO2 table automatically: live Mauna Loa (1959+) + ice core (<1959)
    logging.info("--- Building CO2 table (Mauna Loa + ice core) ---")
    co2_df = build_co2_table()

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = os.path.join(tmpdir, "stics_output")
        os.makedirs(output_dir, exist_ok=True)

        shapefile_path = (
            extract_shapefile(args.shapefile_zip, tmpdir)
            if args.shapefile_zip else None
        )

        if args.source_type == "drias":
            df = load_drias(args, tmpdir, shapefile_path)
        else:
            df = load_single_source(args, shapefile_path)

        logging.info("--- Exporting STICS files ---")
        n_files = export_stics_files(df, co2_df, output_dir)

        logging.info("--- Zipping output ---")
        zip_directory(output_dir, args.output_zip)

    logging.info(f"Done. {n_files} files written → {args.output_zip}")


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Transform climate data (ERA5 / SAFRAN / DRIAS / AgroClim / "
            "custom) into STICS daily input files."
        )
    )
    p.add_argument("--version", action="version", version=__version__)

    # Source type
    p.add_argument(
        "--source_type",
        required=True,
        choices=["era5", "safran", "drias", "agroclim", "custom"],
    )

    # Input files
    p.add_argument(
        "--input_file", nargs="+",
        help="Climate data file(s). Several tabular files (e.g. one per "
             "AgroClim station) are concatenated.",
    )
    p.add_argument(
        "--input_format", default="auto",
        help="File format: netcdf | tabular | csv | tsv | auto",
    )
    p.add_argument(
        "--drias_zip",
        help="ZIP of DRIAS NetCDF files (one per variable)",
    )

    # Spatial
    p.add_argument("--epsg", default="EPSG:4326")
    p.add_argument("--shapefile_zip", default=None)
    p.add_argument(
        "--cell_id_column_index", type=int, default=None,
        help="1-based index of the cell/site ID column (tabular data). "
             "Without it, all rows form a single site with Cell ID 1.",
    )

    # Advanced
    p.add_argument("--wind_correction_factor", type=float, default=0.7)

    # Custom source: 1-based column indices and units
    custom = p.add_argument_group("custom source")
    for name in ("date", "tasmax", "tasmin", "rsds", "prtot",
                 "etp", "wind", "hr", "vapp"):
        custom.add_argument(f"--col_{name}", type=int, default=None)
    for name, choices in CUSTOM_UNIT_CONVERSIONS.items():
        custom.add_argument(
            f"--unit_{name}", choices=list(choices), default=list(choices)[0]
        )

    # Output
    p.add_argument("--output_zip", required=True)
    p.add_argument("--log_file", default=None)

    args = p.parse_args()

    if args.source_type == "drias":
        if not args.drias_zip:
            p.error("--drias_zip is required for the 'drias' source")
    elif not args.input_file:
        p.error("--input_file is required for this source")

    if args.source_type == "custom":
        required = ("date", "tasmax", "tasmin", "rsds", "prtot")
        missing = [n for n in required if getattr(args, f"col_{n}") is None]
        if missing:
            p.error(
                "the custom source requires "
                + ", ".join(f"--col_{n}" for n in missing)
            )

    return args


def setup_logging(log_file: Optional[str]) -> None:
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(
            logging.FileHandler(log_file, mode="w", encoding="utf-8")
        )
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)


if __name__ == "__main__":
    args = parse_args()
    setup_logging(args.log_file)
    try:
        run(args)
    except Exception as exc:
        logging.error(f"Fatal error: {exc}", exc_info=True)
        sys.exit(1)
