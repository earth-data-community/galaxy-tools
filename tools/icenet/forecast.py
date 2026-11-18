"""
Code taken from https://github.com/tom-andersson/icenet-paper and slightly adjusted
to fit the galaxy interface.
"""
import argparse
import os
import re
import sys

import config
import numpy as np
import pandas as pd
import xarray as xr
from tensorflow.keras.models import load_model
from tqdm import tqdm
from utils import IceNetDataLoader
sys.path.insert(0, os.path.join(os.getcwd(), 'icenet'))


parser = argparse.ArgumentParser()
parser.add_argument("--config", type=str, help="config file")
parser.add_argument("--models", type=str, help="network models")
parser.add_argument("--siconca", type=str, help="siconca netcdf file")
parser.add_argument("--forecast_start", type=str, help="forecast start date")
parser.add_argument("--forecast_end", type=str, help="forecast end date")
args = parser.parse_args()

# Load dataloader
dataloader_ID = '2021_09_03_1300_icenet_demo'
dataloader_config_fpath = args.config

# Data loader
# print("\nSetting up the data loader with config file: {}\n\n".format(dataloader_ID))
dataloader = IceNetDataLoader(dataloader_config_fpath)
print('\n\nDone.\n')

# load networks
network_regex = re.compile('^network_tempscaled_([0-9]*).h5$')

network_fpaths = args.models.split(",")

# ensemble_seeds = [36, 42, 53]
ensemble_seeds = network_fpaths
print(ensemble_seeds)

networks = []
for network_fpath in network_fpaths:
    print('Loading model from {}... '.format(network_fpath), end='', flush=True)
    networks.append(load_model(network_fpath, compile=False))
    print('Done.')

model = 'IceNet'

forecast_start = pd.Timestamp(args.forecast_start)
forecast_end = pd.Timestamp(args.forecast_end)

n_forecast_months = dataloader.config['n_forecast_months']


forecast_folder = os.path.join(config.forecast_data_folder, 'icenet', dataloader_ID, model)

if not os.path.exists(forecast_folder):
    os.makedirs(forecast_folder)

# load ground truth
print('Loading ground truth SIC... ', end='', flush=True)
true_sic_fpath = args.siconca
true_sic_da = xr.open_dataarray(true_sic_fpath)
print('Done.')


# set up forecast folder

# define list of lead times
leadtimes = np.arange(1, n_forecast_months + 1)

# add ensemble to the list of models
ensemble_seeds_and_mean = ensemble_seeds.copy()
ensemble_seeds_and_mean.append('ensemble')

all_target_dates = pd.date_range(
    start=forecast_start,
    end=forecast_end,
    freq='MS'
)

all_start_dates = pd.date_range(
    start=forecast_start - pd.DateOffset(months=n_forecast_months - 1),
    end=forecast_end,
    freq='MS'
)

shape = (len(all_target_dates),
         *dataloader.config['raw_data_shape'],
         n_forecast_months)

coords = {
    'time': all_target_dates,  # To be sliced to target dates
    'yc': true_sic_da.coords['yc'],
    'xc': true_sic_da.coords['xc'],
    'lon': true_sic_da.isel(time=0).coords['lon'],
    'lat': true_sic_da.isel(time=0).coords['lat'],
    'leadtime': leadtimes,
    'seed': ensemble_seeds_and_mean,
    'ice_class': ['no_ice', 'marginal_ice', 'full_ice']
}

# Probabilistic SIC class forecasts
dims = ('seed', 'time', 'yc', 'xc', 'leadtime', 'ice_class')
shape = (len(ensemble_seeds_and_mean), *shape, 3)
print(dims)
print(shape)
model_forecast = xr.DataArray(
    data=np.zeros(shape, dtype=np.float32),
    coords=coords,
    dims=dims
)

for start_date in tqdm(all_start_dates):

    # Target forecast dates for the forecast beginning at this `start_date`
    target_dates = pd.date_range(
        start=start_date,
        end=start_date + pd.DateOffset(months=n_forecast_months - 1),
        freq='MS'
    )

    X, y, sample_weights = dataloader.data_generation([start_date])
    mask = sample_weights > 0
    pred = np.array([network.predict(X)[0] for network in networks])
    pred *= mask  # mask outside active grid cell region to zero
    # concat ensemble mean to the set of network predictions
    ensemble_mean_pred = pred.mean(axis=0, keepdims=True)
    pred = np.concatenate([pred, ensemble_mean_pred], axis=0)

    for i, (target_date, leadtime) in enumerate(zip(target_dates, leadtimes)):
        if target_date in all_target_dates:
            model_forecast.\
                loc[:, target_date, :, :, leadtime] = pred[..., i]

print('Saving forecast NetCDF for {}... '.format(model), end='', flush=True)

forecast_fpath = os.path.join(forecast_folder, f'{model.lower()}_forecasts.nc'.format(model.lower()))
model_forecast.to_netcdf(forecast_fpath)  # export file as Net

print('Done.')
