#!/usr/bin/env python3

import argparse
import warnings

import geopandas
import matplotlib as mpl
import pandas as pd  # noqa: I202,E402
import xarray as xr  # noqa: I202,E402

mpl.use('Agg')

from matplotlib import pyplot  # noqa: I202,E402

from rasterstats import zonal_stats  # noqa: I202,E402


if __name__ == '__main__':
    warnings.filterwarnings("ignore")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'raster',
        help='input raster file with geographical coordinates (netCDF format)'
    )

    parser.add_argument(
        'shapefile', help='input shapefile name with polygons '
    )

    parser.add_argument(
        'variable', help='name of the variable in raster file'
    )
    parser.add_argument(
        'output', help='output filename to store resulting image (png format)'
    )
    parser.add_argument(
        '-s', '--stat', help='type of statistics [min, max, mean, count]'
    )
    parser.add_argument(
        '-t', '--title', help='title for the generated plot'
    )
    parser.add_argument("-v", "--verbose", help="switch on verbose mode",
                        action="store_true")

    args = parser.parse_args()
    if args.stat is None:
        stat_type = 'mean'
    else:
        stat_type = args.stat

    dset = xr.open_dataset(args.raster)
    dset[args.variable].to_netcdf(".tmp.nc")
    zs = zonal_stats(args.shapefile, ".tmp.nc", stats=stat_type)
    df_zonal_stats = pd.DataFrame(zs)
    world = geopandas.read_file(args.shapefile)
    df = pd.concat([world, df_zonal_stats], axis=1)
    ddf = df.dropna()
    f, ax = pyplot.subplots(1, figsize=(20, 10))

    visu = ddf.plot(column=stat_type, scheme='Quantiles', k=15, cmap='jet',
                    legend=True, ax=ax,
                    legend_kwds={'loc': 'lower left',
                                 'frameon': True,
                                 'title': args.variable,
                                 'bbox_to_anchor': (1, 0.05)
                                 }
                    )  # plot done
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    if args.title is None:
        f.suptitle(stat_type + " computed over areas")
    else:
        f.suptitle(args.title)
    if args.verbose:
        print("plot generated")

    pyplot.savefig(args.output, format='png')
