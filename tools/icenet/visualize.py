import os
import sys
import argparse
import utils
import pandas as pd
import xarray as xr
import numpy as np
import config
import calendar
import panel as pn
import matplotlib.pyplot as plt
import matplotlib.offsetbox as ob
sys.path.insert(0, os.path.join(os.getcwd(), 'icenet'))


parser = argparse.ArgumentParser()
parser.add_argument("--siconca", type=str, help="siconca netcdf file")
parser.add_argument("--forecast", type=str, help="forecast netcdf file")
parser.add_argument("--forecast_start", type=str, help="forecast start date")
parser.add_argument("--forecast_end", type=str, help="forecast end date")
parser.add_argument("--old_results", type=str, help="forecast end date")
args = parser.parse_args()


model = 'IceNet'

dataloader_ID = '2021_09_03_1300_icenet_demo'
forecast_folder = os.path.join(config.forecast_data_folder, 'icenet', dataloader_ID, model)

if not os.path.exists(forecast_folder):
    os.makedirs(forecast_folder)


# define list of lead times
leadtimes = np.arange(1, 7)

forecast_start = pd.Timestamp(args.forecast_start)
forecast_end = pd.Timestamp(args.forecast_end)

all_target_dates = pd.date_range(
    start=forecast_start,
    end=forecast_end,
    freq='MS'
)

metric_compute_list = ['Binary accuracy', 'SIE error']

forecast_fpath = args.forecast

chunks = {'seed': 1}
icenet_forecast_da = xr.open_dataarray(forecast_fpath, chunks=chunks)
icenet_seeds = icenet_forecast_da.seed.values

mask_fpath_format = os.path.join(config.mask_data_folder, 'active_grid_cell_mask_{}.npy')

month_mask_da = xr.DataArray(np.array(
    [np.load(mask_fpath_format.format('{:02d}'.format(month))) for
     month in np.arange(1, 12 + 1)],
))

now = pd.Timestamp.now()
new_results_df_fname = now.strftime('%Y_%m_%d_%H%M%S_forecast_results.csv')
new_results_df_fpath = os.path.join(config.forecast_results_folder, new_results_df_fname)

print('New results will be saved to {}\n\n'.format(new_results_df_fpath))


old_results_df_fpath = args.old_results
print('\n\nLoading previous results dataset from {}'.format(old_results_df_fpath))

# Load previous results, do not interpret 'NA' as NaN
results_df = pd.read_csv(old_results_df_fpath, keep_default_na=False, comment='#')

# Remove existing IceNet results
results_df = results_df[~results_df['Model'].str.startswith('IceNet')]

# Drop spurious index column if present
results_df = results_df.drop('Unnamed: 0', axis=1, errors='ignore')
results_df['Forecast date'] = [pd.Timestamp(date) for date in results_df['Forecast date']]

results_df = results_df.set_index(['Model', 'Ensemble member', 'Leadtime', 'Forecast date'])

# Add new models to the dataframe
multi_index = utils.create_results_dataset_index([model], leadtimes, all_target_dates, model, icenet_seeds)
results_df = results_df.append(pd.DataFrame(index=multi_index)).sort_index()

icenet_sip_da = icenet_forecast_da.sel(ice_class=['marginal_ice', 'full_ice']).sum('ice_class')

true_sic_fpath = args.siconca
true_sic_da = xr.open_dataarray(true_sic_fpath, chunks={})
true_sic_da = true_sic_da.load()
true_sic_da = true_sic_da.sel(time=all_target_dates)

if 'Binary accuracy' in metric_compute_list:
    binary_true_da = true_sic_da > 0.15

print(all_target_dates)
months = [pd.Timestamp(date).month - 1 for date in all_target_dates]
mask_da = xr.DataArray(
    [month_mask_da[month] for month in months],
    dims=('time', 'yc', 'xc'),
    coords={
        'time': true_sic_da.time.values,
        'yc': true_sic_da.yc.values,
        'xc': true_sic_da.xc.values,
    }
)

print('Analysing forecasts: \n\n')

print('Computing metrics:')
print(metric_compute_list)

binary_forecast_da = icenet_sip_da > 0.5

compute_ds = xr.Dataset()
for metric in metric_compute_list:

    if metric == 'Binary accuracy':
        binary_correct_da = (binary_forecast_da == binary_true_da).astype(np.float32)
        binary_correct_weighted_da = binary_correct_da.weighted(mask_da)

        # Mean percentage of correct classifications over the active
        #   grid cell area
        ds_binacc = (binary_correct_weighted_da.mean(dim=['yc', 'xc']) * 100)
        compute_ds[metric] = ds_binacc

    elif metric == 'SIE error':
        binary_forecast_weighted_da = binary_forecast_da.astype(int).weighted(mask_da)
        binary_true_weighted_da = binary_true_da.astype(int).weighted(mask_da)

        ds_sie_error = (
            binary_forecast_weighted_da.sum(['xc', 'yc']) - binary_true_weighted_da.sum(['xc', 'yc'])
        ) * 25**2

        compute_ds[metric] = ds_sie_error

print('Writing to results dataset...')
for compute_da in iter(compute_ds.data_vars.values()):
    metric = compute_da.name

    compute_df_index = results_df.loc[
        pd.IndexSlice[model, :, leadtimes, all_target_dates], metric].\
        droplevel(0).index

    # Ensure indexes are aligned for assigning to results_df
    compute_df = compute_da.to_dataframe().reset_index().\
        set_index(['seed', 'leadtime', 'time']).\
        reindex(index=compute_df_index)

    results_df.loc[pd.IndexSlice[model, :, leadtimes, all_target_dates], metric] = \
        compute_df.values

print('\nCheckpointing results dataset... ', end='', flush=True)
results_df.to_csv(new_results_df_fpath)
print('Done.')


settings_lineplots = dict(padding=0.1, height=400, width=700, fontsize={'title': '120%', 'labels': '120%', 'ticks': '100%'})

# Reset index to preprocess results dataset
results_df = results_df.reset_index()

results_df['Forecast date'] = pd.to_datetime(results_df['Forecast date'])

month_names = np.array(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                        'Jul', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'])
forecast_month_names = month_names[results_df['Forecast date'].dt.month.values - 1]
results_df['Calendar month'] = forecast_month_names

results_df = results_df.set_index(['Model', 'Ensemble member', 'Leadtime', 'Forecast date'])

# subset target period
results_df = results_df.loc(axis=0)[pd.IndexSlice[:, :, :, slice(forecast_start, forecast_end)]]

results_df = results_df.sort_index()

# set target years
year = pd.Timestamp(all_target_dates[0]).year

# set sliders
month_name = [f'{calendar.month_name[m]} {year}' for m in list(range(1, 13))]

month_slider = pn.widgets.DiscreteSlider(name="Month", options=month_name[months[0]:months[len(months) - 1] + 1], value=month_name[months[0]], width=200)

lead_slider = pn.widgets.IntSlider(name="Lead time (months)", start=1, end=4, step=1, value=1, direction='rtl', width=200)

# set boundaries
mask = np.load(os.path.join(config.mask_data_folder,
                            'active_grid_cell_mask_{}.npy'.format('03')))

min_0 = np.min(np.argwhere(mask)[:, 0])
max_0 = np.max(np.argwhere(mask)[:, 0])
mid_0 = np.mean((min_0, max_0)).astype(int)
min_1 = np.min(np.argwhere(mask)[:, 1])
max_1 = np.max(np.argwhere(mask)[:, 1])
mid_1 = np.mean((min_1, max_1)).astype(int)
max_diff = np.max([mid_0 - min_0, mid_1 - min_1])
max_diff *= .85  # Zoom in
max_diff = int(max_diff)
top = mid_0 - max_diff + 10
bot = mid_0 + max_diff + 10
left = mid_1 - max_diff
right = mid_1 + max_diff

# land and region masks
land_mask = np.load(os.path.join(config.mask_data_folder, 'land_mask.npy'))
region_mask = np.load(os.path.join(config.mask_data_folder, 'region_mask.npy'))

# define coastline and land layers
arr = region_mask == 13
coastline_rgba_arr = np.zeros((*arr.shape, 4))
coastline_rgba_arr[:, :, 3] = arr  # alpha channel
coastline_rgba_arr[:, :, :3] = .5  # black coastline
land_mask_rgba_arr = np.zeros((*arr.shape, 4))
land_mask_rgba_arr[:, :, 3] = land_mask  # alpha channel
land_mask_rgba_arr[:, :, :3] = .5  # gray land

# line colours
pred_ice_edge_rgb = 'green'
true_ice_edge_rgb = 'black'


# define plot function
@pn.depends(month_slider.param.value, lead_slider.param.value)
def plot_forecast(month, leadtime):
    print(month)
    print(months)
    print(leadtime)
    print(forecast_month_names)
    tdate = pd.Timestamp(year, month_name.index(month) + 1, 1)

    fig0 = plt.Figure(figsize=(8, 8))
    ax0 = fig0.subplots()
    # FigureCanvas(fig0)  not needed for mpl >= 3.1

    ax0.imshow(coastline_rgba_arr[top:bot, left:right, :], zorder=20)
    ax0.imshow(land_mask_rgba_arr[top:bot, left:right, :], zorder=1)

    icenet_sip = icenet_sip_da.sel(time=tdate, leadtime=leadtime, seed='ensemble').data
    ax0.contour(
        icenet_sip[top:bot, left:right],
        levels=[0.5],
        colors=[pred_ice_edge_rgb],
        zorder=1,
        linewidths=1.5,
    )

    groundtruth_sic = true_sic_da.sel(time=tdate)
    gt_img = (groundtruth_sic > 0.15).data

    ax0.contour(
        gt_img[top:bot, left:right],
        levels=[0.5],
        colors=[true_ice_edge_rgb],
        zorder=1,
        linewidths=1.5
    )
    ax0.tick_params(which='both', bottom=False, left=False, labelbottom=False, labelleft=False)

    proxy = [plt.Line2D([0], [1], color=true_ice_edge_rgb),
             plt.Line2D([0], [1], color=pred_ice_edge_rgb)]

    ax0.legend(proxy, ['Observed', 'Predicted'], loc='upper left', fontsize=11)

    ax0.set_title(f'Date = {month} & Lead time = {leadtime} months')

    acc = results_df.loc['IceNet', 'ensemble', leadtime, tdate]['Binary accuracy']
    sie_err = results_df.loc['IceNet', 'ensemble', leadtime, tdate]['SIE error']

    Afont = {
        'backgroundcolor': 'lightgray',
        'color': 'black',
        'weight': 'normal',
        'size': 11, }

    t = ob.AnchoredText('Binary acc: {:.1f}% \nSIE error: {:+.3f} mil km$^2$'.format(acc, sie_err / 1e6), prop=Afont, loc='lower right', pad=0.5, borderpad=0.4, frameon=False)
    t = ax0.add_artist(t)
    t.zorder = 21

    return pn.pane.Matplotlib(fig0, tight=True, dpi=150)


plot_ie = pn.Row(
    plot_forecast,
    pn.Column(pn.Spacer(height=5), month_slider, pn.Spacer(height=15), lead_slider, background='#f0f0f0', sizing_mode="fixed"),
    width_policy='max', height_policy='max',
)

plot_ie.save('forecast_visualization.html', embed=True)
