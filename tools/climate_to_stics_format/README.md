# Climate to STICS Format

Galaxy tool converting daily weather data into the input files of the **STICS** crop model.

## Supported sources

| Source | Input | Cell / station ID |
|---|---|---|
| ERA5 | Open-Meteo daily table, or Copernicus CDS daily NetCDF grid | selected column (table); shapefile or one cell per pixel (NetCDF) |
| SAFRAN | GeoSAS export, Météo-France SIM2 file, or NetCDF grid | selected column (table); shapefile or one cell per pixel (NetCDF) |
| DRIAS-2020 | ZIP archive with one NetCDF file per variable | shapefile (required) |
| AgroClim | INRAE station daily files from Recherche Data Gouv ([doi:10.57745/BQ0BWB](https://doi.org/10.57745/BQ0BWB)) | `station_id` column |
| Custom | any daily table; columns and units selected in the form | selected column |

Each source has its own variable names and unit conversions. Wind speed measured at 10 m is corrected to the 2 m STICS reference height (factor 0.7 by default); AgroClim INRAE stations already measure wind at 2 m.

## Output

A ZIP archive `stics_output/{cell}/{cell}.{year}` with one headerless file per cell and per year, with space-separated, right-aligned columns like the weather files shipped with JavaSTICS (13 columns: cell, year, month, day, day of year, Tmin, Tmax, radiation, ETP, precipitation, wind, vapour pressure, CO2). Missing values are written as `-999.9`. A processing log is also produced.

Annual CO2 comes from the Mauna Loa series (NOAA/GML, downloaded at run time, bundled fallback) from 1959 and from an ice-core record before.

## References

- Brisson, N. et al. (2003). An overview of the crop model STICS. *European Journal of Agronomy*, 18(3-4), 309–332. https://doi.org/10.1016/S1161-0301(02)00110-7
- Hersbach, H. et al. (2020). The ERA5 global reanalysis. *QJRMS*, 146(730), 1999–2049. https://doi.org/10.1002/qj.3803
- Zippenfenig, P. (2023). Open-Meteo.com Weather API. https://doi.org/10.5281/zenodo.7970649
- Quintana-Seguí, P. et al. (2008). Analysis of near-surface atmospheric variables: validation of the SAFRAN analysis over France. *JAMC*, 47(1), 92–107. https://doi.org/10.1175/2007JAMC1636.1
- Vidal, J.-P. et al. (2010). A 50-year high-resolution atmospheric reanalysis over France with the Safran system. *Int. J. Climatol.*, 30, 1627–1644. https://doi.org/10.1002/joc.2003
- Furusho-Percot, C. et al. (2025). French agroclimatic research network dataset. *Data in Brief*, 61. https://doi.org/10.1016/j.dib.2025.111809
- Etheridge, D.M. et al. (1996). Natural and anthropogenic changes in atmospheric CO2 over the last 1000 years. *JGR: Atmospheres*, 101(D2), 4115–4128. https://doi.org/10.1029/95JD03410
- Hoyer, S. & Hamman, J. (2017). xarray: N-D labeled arrays and datasets in Python. *JORS*, 5(1). https://doi.org/10.5334/jors.148
