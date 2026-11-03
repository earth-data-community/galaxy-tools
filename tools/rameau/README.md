---
title: "RAMEAU hydrogeological modelling"
date: 2026-10-19
draft: false
weight: 1
---

# RAMEAU hydrogeological modelling

Runs **RAMEAU**, a software developed at the French Geological Survey (**BRGM**) for the modelling of river flows and/or groundwater levels in watersheds of various scales. The tool supports global (single watershed) and semi-distributed (multi-watershed) rainfall-runoff and rainfall-groundwater level models.

## Modes

- **Optimization**: estimates the model parameters by calibration against observed river flow and/or groundwater level.
- **Simulation**: produces simulated time series from an already calibrated model.
- **Forecast**: produces ensemble forecasts from an already calibrated model.

Several modes can be selected in a single job; optimization is then always run first.

## Input

- **Parameter file** (TOML) — required for every mode.
- **Connectivity file** (CSV) — required only when the TOML file describes several watersheds (semi-distributed modelling).
- **Data files** (CSV, **tab-separated**):
  - **PET** (mm) and **Rainfall** (mm) — always required.
  - **River flow** (m³/s) — for rainfall-runoff and rainfall-runoff-level models.
  - **Groundwater level** (m) — for rainfall-level and rainfall-runoff-level models.
  - **Temperature** (°C) and **Snowfall** (mm) — when the snow module is used.
  - **Surface water withdrawals** and **Groundwater withdrawals** — when the influence of pumping in rivers or aquifers is modelled.

## Output

- A **TOML file** with the model parameters (optimized parameters for optimization and forecast).
- A Galaxy **list collection** whose content depends on the execution mode and model type: simulated river flow and/or groundwater level time series, performance indicators (optimization and simulation), or ensemble forecasts (e.g. `forecast_riverflow.csv`, `forecast_watertable.csv`).

## Requirements

Docker container [`brgmcode/rameau`](https://hub.docker.com/r/brgmcode/rameau), which wraps the [`rameau`](https://pypi.org/project/rameau/) Python package.

## Notes

- Documentation: https://rameau.readthedocs.io/
- Source code: https://gitlab.com/brgm/hydrogeological-modelling/rameau
- Citation: Vergnes, J.-P. and Hallouin, T., *Rameau: a software dedicated to the modelling of river flows and/or groundwater levels in watersheds of various scales*, Zenodo, [doi:10.5281/zenodo.15095481](https://doi.org/10.5281/zenodo.15095481)
- The tool uses `profile="20.01"` on purpose: the container entrypoint expects the multiple-choice **run** parameter as a comma-separated string in `inputs.json`, which Galaxy only provides for profiles older than 20.05.
