"""
Code taken from https://github.com/tom-andersson/icenet-paper and adjusted to fit the galaxy interface.
"""
import argparse
import json

import pandas as pd
"""
Creates API request text files for downloading Icenet Data with the Copernicus Climate Data Store according to the config file.
"""
parser = argparse.ArgumentParser()
parser.add_argument('--var', nargs="+")
parser.add_argument("--forecast_start", type=str, help="forecast start date")
parser.add_argument("--forecast_end", type=str, help="forecast end date")
parser.add_argument("--config", type=str, help="config file")
args = parser.parse_args()


args = parser.parse_args()
forecast_start = args.forecast_start
forecast_end = args.forecast_end
config = args.config
variable = args.var

with open(config, 'r') as readfile:
    config = json.load(readfile)
max_lag = config["input_data"][variable[0]]["abs"]["max_lag"]

forecast_start_year = pd.Timestamp(forecast_start).year
forecast_start_month = pd.Timestamp(forecast_start).month

forecast_end_year = pd.Timestamp(forecast_end).year
forecast_end_month = pd.Timestamp(forecast_end).month

area = [90, -180, 0, 180]  # Latitude/longitude boundaries to download


# Which years to download

past_year = []
if ((forecast_start_month - (6 + max_lag)) <= 0):
    past_year = [forecast_start_year - 1]

years = past_year + [i for i in range(forecast_start_year, forecast_end_year + 1)]

months = []
for i in range(0, 13):
    if ((forecast_start_month - (6 + max_lag) + i < forecast_start_month) or (forecast_start_month - (6 + max_lag) + i < forecast_end_month)):
        months = months + [(forecast_start_month - (6 + max_lag) + 12 + i) % 12 if (forecast_start_month - (6 + max_lag) + 12 + i) % 12 != 0 else 12]
    else:
        break
print(years)
print(months)

# Near-real-time data contains ERA5T with 'expver' coord -- remove 'expver'
#   dim and concatenate into one array
fix_near_real_time_era5_coords = True

# Variable information
################################################################################

# To add more variables, go to the following dataset sites, fill in the download
#   form for the desired variable, and check the variable's CDI name by clicking
#   'show API request':
#   - Surface vars: https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-single-levels-monthly-means?tab=form
#   - Pressure level vars: https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-pressure-levels-monthly-means?tab=overview
variables = {
    'tas': {
        'cdi_name': '2m_temperature',
    },
    'ta500': {
        'plevel': '500',
        'cdi_name': 'temperature',
    },
    'tos': {
        'cdi_name': 'sea_surface_temperature',
    },
    # RSUS needs to be computed using net solar radiation and downwards radiation,
    # and need to convert from J/m^2 to W/m^2 by dividing by the number of seconds
    # in a day (60*60*25)
    'rsds': {
        'cdi_name': 'surface_solar_radiation_downwards',
    },
    'rsus': {
        'cdi_name': 'surface_net_solar_radiation',
    },
    'psl': {
        'cdi_name': 'mean_sea_level_pressure',
    },
    'zg500': {
        'plevel': '500',
        'cdi_name': 'geopotential',
    },
    'zg250': {
        'plevel': '250',
        'cdi_name': 'geopotential',
    },
    'ua10': {
        'plevel': '10',
        'cdi_name': 'u_component_of_wind',
    },
    # Note: the surface wind variables are not regridded here; a separate script
    #   is used to rotate and regrid them.
    'uas': {
        'cdi_name': '10m_u_component_of_wind',
    },
    'vas': {
        'cdi_name': '10m_v_component_of_wind',
    },
}
var_dict = variables[variable[0]]
var_names = []
for var in variable:
    var_names.append(variables[var]["cdi_name"])


def retrieve_CDS_data(var_cdi_name, plevel=None):

    cds_dict = {
        'product_type': 'monthly_averaged_reanalysis',
        'variable': var_cdi_name,
        'year': years,
        'month': months,
        'time': '00:00',
        'format': 'netcdf',
        'area': area
    }

    if plevel is not None:
        dataset = 'reanalysis-era5-pressure-levels-monthly-means'
        cds_dict['pressure_level'] = plevel
    else:
        dataset = 'reanalysis-era5-single-levels-monthly-means'

    return "c.retrieve({}, \n {}, \n 'download.nc')".format(dataset, cds_dict)


filename = '{}_request.txt'.format(variable[0])

if 'plevel' not in var_dict.keys():
    plevel = None
else:
    plevel = var_dict['plevel']


with open(filename, 'w') as f:

    f.write("import cdsapi\n\n")
    f.write("c = cdsapi.Client()\n\n")
    f.write(retrieve_CDS_data(var_names, plevel))
