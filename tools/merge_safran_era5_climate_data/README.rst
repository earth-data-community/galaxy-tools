---
title: "Merge SAFRAN and ERA5 climate data"
date: 2026-10-21
draft: false
weight: 1
---

Merge SAFRAN and ERA5 climate data
===================================

A Galaxy tool that joins a SAFRAN climate reanalysis file (metropolitan
France, typically produced by the `Get SAFRAN data (GEOSAS API)
<https://github.com/galaxyecology/tools-ecology/tree/master/tools/get_safran_data_geosas_api>`_
tool) and an ERA5 / ERA5-Land reanalysis file for the same sites into a
single table, matched on a site identifier and a date.

It is meant to complete SAFRAN atmospheric variables (temperature,
precipitation, potential evapotranspiration, ...) with ERA5 variables that
SAFRAN does not provide, such as depth-resolved soil moisture and soil
temperature, for the same site and date.

Usage
-----

The tool takes two CSV files with a header row:

- a SAFRAN file, and
- an ERA5 / ERA5-Land file

For each file, you pick which column holds the site identifier, which
column holds the date, and (optionally) which climate variable columns to
keep. The two files do not need to share column names, column order, or the
same set of sites.

You then choose how the two files are combined:

- **Inner join** -- keep only the site/date combinations present in both files.
- **Left join** -- keep every SAFRAN record; ERA5 columns are left empty
  where there is no matching ERA5 record.
- **Right join** -- keep every ERA5 record; SAFRAN columns are left empty
  where there is no matching SAFRAN record.
- **Outer join** -- keep every record from either file.

An optional date range can restrict the merge to a given period, and the
number of decimal places used to round numeric columns can be adjusted.

Output
------

A single CSV file with ``site_name``, ``date``, and the selected climate
variable columns from both sources, sorted by site and then date. Columns
that exist with the same name in both input files get a ``_safran`` /
``_era5`` suffix so both are kept.

Requirements
------------

- Python >= 3.9
- pandas (pinned in the tool's ``<requirements>``)

Testing
-------

Run ``planemo test merge_safran_era5_climate_data.xml`` from this directory.
The ``test-data/`` folder contains small, hand-crafted SAFRAN/ERA5 fixtures
covering every join mode (inner/left/right/outer) and the date-range filter.

Citations
---------

- Vidal, J.-P. et al. (2010). *A 50-year high-resolution atmospheric
  reanalysis over France with the Safran system.* Int. J. Climatol., 30(11).
  https://doi.org/10.1002/joc.2003
- Habets, F. et al. (2008). *The SAFRAN-ISBA-MODCOU hydrometeorological
  model applied over France.* J. Geophys. Res. Atmos., 113(D6).
  https://doi.org/10.1029/2007JD008548
- Hersbach, H. et al. (2020). *The ERA5 global reanalysis.* Q. J. R.
  Meteorol. Soc., 146(730). https://doi.org/10.1002/qj.3803
- The pandas development team. *pandas-dev/pandas: Pandas.*
  https://doi.org/10.5281/zenodo.3509134

Author
------

Mathieu Guimont, `Data Terra <https://www.data-terra.org/>`_, `ALAMOD
<https://www.pepr-faircarbon.fr/projets/alamod/>`_
