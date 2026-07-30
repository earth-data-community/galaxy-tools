import xarray as xr
import argparse
'''
Concatenates monthly averaged OSI-SAF SIC data from 1979-present. The data was downloaded from the following sites:
    - OSI-450 (1979-2016): https://thredds.met.no/thredds/dodsC/osisaf/met.no/reprocessed/ice/conc_v2p0_nh_agg.html
    - OSI-430-b (2016-present): https://thredds.met.no/thredds/dodsC/osisaf/met.no/reprocessed/ice/conc_crb_nh_agg.html
'''
parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input", type=str, nargs="+", help="input files")
args = parser.parse_args()

pathlist = args.input

concat_data = xr.open_mfdataset(pathlist, preprocess=lambda f: f["ice_conc"], data_vars=["ice_conc"])
concat_data = concat_data.resample(time="1MS").mean(dim="time")

concat_data.to_netcdf('siconca.nc')
