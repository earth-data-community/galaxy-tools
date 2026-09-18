#!/usr/bin/env python3
"""
Galaxy tool for computing climate indices using icclim.
MNHN / PNDB — Geomatys — 2026

Usage (invoked by Galaxy via the XML template):
    python icclim_climate_indices.py
        --input tas.nc
        --output out.nc
        --index-name TG
        [options...]
"""

from __future__ import annotations

import argparse
import sys

import icclim


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    """Parse CLI arguments provided by the Galaxy XML template."""
    parser = argparse.ArgumentParser(
        description="Compute ECA&D/ETCCDI climate indices via icclim"
    )

    # -- Inputs / Outputs -----------------------------------------------------
    parser.add_argument(
        "--input",
        required=True,
        nargs="+",
        metavar="FILE",
        help="Input CF NetCDF file(s) (one or more)",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="FILE",
        help="Output NetCDF 4 file",
    )
    parser.add_argument(
        "--merge-outputs",
        action="store_true",
        default=False,
        help="Merge the files listed in --input into --output (tool-internal mode).",
    )

    # -- Main index -----------------------------------------------------------
    parser.add_argument(
        "--index-name",
        required=False,
        default=None,
        metavar="INDEX",
        help="Name of the icclim index to compute (e.g. TG, FD, SU, TX90p…). "
             "Required unless --merge-outputs is set.",
    )

    # -- Optional icclim.index() parameters ----------------------------------
    parser.add_argument(
        "--var-name",
        default=None,
        metavar="VAR",
        help="Name of the climate variable in the NetCDF (e.g. tasmax)",
    )
    parser.add_argument(
        "--slice-mode",
        default="year",
        choices=["year", "month", "DJF", "MAM", "JJA", "SON", "ONDJFM", "AMJJAS"],
        help="Computation frequency (default: year)",
    )
    parser.add_argument(
        "--time-range",
        default=None,
        nargs=2,
        metavar=("START", "END"),
        help="Time range e.g. 1990-01-01 2020-12-31",
    )
    parser.add_argument(
        "--base-period-time-range",
        default=None,
        nargs=2,
        metavar=("START", "END"),
        help="Reference period for percentile-based indices (e.g. TX90p)",
    )
    parser.add_argument(
        "--only-leap-years",
        action="store_true",
        default=False,
        help="Restrict computation to leap years",
    )
    parser.add_argument(
        "--ignore-Feb29th",
        action="store_true",
        default=False,
        help="Ignore February 29th in computations",
    )
    parser.add_argument(
        "--netcdf-version",
        default="NETCDF4",
        choices=["NETCDF4", "NETCDF4_CLASSIC", "NETCDF3_CLASSIC"],
        help="Output NetCDF format (default: NETCDF4)",
    )
    parser.add_argument(
        "--save-thresholds",
        action="store_true",
        default=False,
        help="Save percentile thresholds in the output file",
    )
    parser.add_argument(
        "--logs-verbosity",
        default="LOW",
        choices=["LOW", "HIGH"],
        help="icclim verbosity level (default: LOW)",
    )
    parser.add_argument(
        "--date-event",
        action="store_true",
        default=False,
        help="Store extreme event dates in the output",
    )
    parser.add_argument(
        "--min-spell-length",
        default=None,
        type=int,
        metavar="N",
        help="Minimum sequence length (for spell-type indices)",
    )
    parser.add_argument(
        "--rolling-window-width",
        default=None,
        type=int,
        metavar="N",
        help="Rolling window width for percentile computation",
    )
    parser.add_argument(
        "--sampling-method",
        default="resample",
        choices=["resample", "groupby", "groupby_ref_and_resample_study"],
        help="Temporal sampling method (default: resample)",
    )
    parser.add_argument(
        "--out-unit",
        default=None,
        metavar="UNIT",
        help="Output unit (e.g. 'days', 'percent'). Uses the icclim default unit if absent.",
    )
    parser.add_argument(
        "--threshold",
        default=None,
        metavar="THRESH",
        help="Threshold for threshold-based indices (SU, TR, WSDI, TX90p…). E.g. '30 degC'.",
    )
    parser.add_argument(
        "--doy-window-width",
        default=None,
        type=int,
        metavar="N",
        help="Window width (days) for day-of-year aggregation when computing percentiles (icclim default: 5).",
    )
    parser.add_argument(
        "--interpolation",
        default=None,
        choices=["linear", "median_unbiased"],
        help="Interpolation method for percentile computation (icclim default: median_unbiased).",
    )

    # -- Custom index (user_index) --------------------------------------------
    parser.add_argument(
        "--user-index",
        action="store_true",
        default=False,
        help="Enable custom index definition (user_index)",
    )
    parser.add_argument(
        "--ui-index-name",
        default=None,
        metavar="NAME",
        help="[user_index] Custom index name",
    )
    parser.add_argument(
        "--ui-calc-operation",
        default=None,
        choices=["mean", "sum", "max", "min", "nb_events",
                 "max_nb_consecutive_events", "run_mean", "run_sum", "anomaly"],
        help="[user_index] Computation operation",
    )
    parser.add_argument(
        "--ui-var-type",
        default=None,
        choices=["t", "p"],
        help="[user_index] Variable type: t=temperature, p=precipitation",
    )
    parser.add_argument(
        "--ui-thresh",
        default=None,
        metavar="THRESH",
        help="[user_index] Threshold (e.g. '25 degC', '10 mm/day')",
    )
    parser.add_argument(
        "--ui-logical-operation",
        default=None,
        choices=["gt", "lt", "get", "let", "e"],
        help="[user_index] Logical operator: gt(>), lt(<), get(>=), let(<=), e(==)",
    )
    parser.add_argument(
        "--ui-link-logical-operations",
        default=None,
        choices=["and", "or"],
        help="[user_index] Logical link between multiple thresholds",
    )
    parser.add_argument(
        "--ui-date-event",
        action="store_true",
        default=False,
        help="[user_index] Store the event date",
    )
    parser.add_argument(
        "--ui-coef",
        default=None,
        type=float,
        metavar="COEF",
        help="[user_index] Multiplicative coefficient applied to the result",
    )
    parser.add_argument(
        "--ui-extreme-mode",
        default=None,
        choices=["min", "max"],
        help="[user_index] Extreme mode: min or max",
    )
    parser.add_argument(
        "--ui-window-width",
        default=None,
        type=int,
        metavar="N",
        help="[user_index] Rolling window width",
    )
    parser.add_argument(
        "--ui-ref-time-range",
        default=None,
        nargs=2,
        metavar=("START", "END"),
        help="[user_index] Reference time range for the anomaly",
    )

    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Build icclim parameters
# ---------------------------------------------------------------------------

def build_icclim_params(args) -> dict:
    """
    Build the parameter dictionary for icclim.index()
    from parsed CLI arguments.

    Only explicitly provided parameters are included;
    icclim default values apply for the rest.
    """
    # Mandatory parameters
    params: dict = {
        "in_files": args.input[0] if len(args.input) == 1 else args.input,
        "out_file": args.output,
        "netcdf_version": args.netcdf_version,
        "logs_verbosity": args.logs_verbosity,
        "slice_mode": args.slice_mode,
    }

    # Optional parameters — included only if provided
    if args.var_name:
        names = [v.strip() for v in args.var_name.split(",") if v.strip()]
        params["var_name"] = names[0] if len(names) == 1 else names
    if args.time_range:
        params["time_range"] = args.time_range
    if args.base_period_time_range:
        params["base_period_time_range"] = args.base_period_time_range
    if args.only_leap_years:
        params["only_leap_years"] = True
    if args.ignore_Feb29th:
        params["ignore_Feb29th"] = True
    if args.save_thresholds:
        params["save_thresholds"] = True
    if args.date_event:
        params["date_event"] = True
    if args.min_spell_length is not None:
        params["min_spell_length"] = args.min_spell_length
    if args.rolling_window_width is not None:
        params["rolling_window_width"] = args.rolling_window_width
    if args.sampling_method != "resample":
        params["sampling_method"] = args.sampling_method
    if args.out_unit:
        params["out_unit"] = args.out_unit
    if args.threshold:
        params["threshold"] = args.threshold
    if args.doy_window_width is not None:
        params["doy_window_width"] = args.doy_window_width
    if args.interpolation:
        params["interpolation"] = args.interpolation

    return params


def build_user_index(args) -> dict:
    """
    Build the user_index dictionary for icclim.index()
    from the --ui-* CLI arguments.

    Structure expected by icclim 7.x (UserIndexDict):
        index_name, calc_operation, var_type, thresh,
        logical_operation, link_logical_operations,
        date_event, coef, extreme_mode, window_width,
        ref_time_range
    """
    if not args.ui_index_name:
        raise ValueError(
            "--ui-index-name is required when --user-index is enabled"
        )
    if not args.ui_calc_operation:
        raise ValueError(
            "--ui-calc-operation is required when --user-index is enabled"
        )

    user_index: dict = {
        "index_name": args.ui_index_name,
        "calc_operation": args.ui_calc_operation,
    }

    if args.ui_var_type:
        user_index["var_type"] = args.ui_var_type
    if args.ui_thresh:
        user_index["thresh"] = args.ui_thresh
    if args.ui_logical_operation:
        user_index["logical_operation"] = args.ui_logical_operation
    if args.ui_link_logical_operations:
        user_index["link_logical_operations"] = args.ui_link_logical_operations
    if args.ui_date_event:
        user_index["date_event"] = True
    if args.ui_coef is not None:
        user_index["coef"] = args.ui_coef
    if args.ui_extreme_mode:
        user_index["extreme_mode"] = args.ui_extreme_mode
    if args.ui_window_width is not None:
        user_index["window_width"] = args.ui_window_width
    if args.ui_ref_time_range:
        user_index["ref_time_range"] = args.ui_ref_time_range

    return user_index


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------

def run(args) -> None:
    """
    Orchestrate the icclim computation:
    1. Build parameters from CLI arguments
    2. Add the standard or custom index
    3. Call icclim.index() which handles lazy processing (xarray + dask)
    """
    params = build_icclim_params(args)

    if args.user_index:
        # Custom index mode (user_index)
        ui = build_user_index(args)
        params["user_index"] = ui
        print(f"[icclim] Computing custom index: {ui['index_name']}", flush=True)
        print(f"[icclim]   operation  : {ui['calc_operation']}", flush=True)
        if "thresh" in ui:
            print(f"[icclim]   threshold  : {ui['thresh']}", flush=True)
    else:
        # Predefined ECA&D / ETCCDI index mode
        params["index_name"] = args.index_name
        print(f"[icclim] Computing predefined index: {args.index_name}", flush=True)

    print(f"[icclim]   input(s)   : {args.input}", flush=True)
    print(f"[icclim]   output     : {args.output}", flush=True)
    print(f"[icclim]   frequency  : {args.slice_mode}", flush=True)

    icclim.index(**params)

    print(f"[icclim] Result written to: {args.output}", flush=True)


# ---------------------------------------------------------------------------
# Merge helper (used when --merge-outputs is set)
# ---------------------------------------------------------------------------

def merge_outputs_files(input_files: list, output_path: str) -> None:
    """Merge multiple icclim partial outputs into a single NetCDF file."""
    import shutil
    import xarray as xr

    sorted_files = sorted(input_files)
    if len(sorted_files) == 1:
        shutil.copy(sorted_files[0], output_path)
        return

    datasets = []
    try:
        datasets = [xr.open_dataset(f) for f in sorted_files]
        # Detect same-variable-name with different time dimensions before merging —
        # xr.merge(join="outer") would silently produce a mixed-frequency variable.
        var_time_len: dict = {}
        for ds in datasets:
            if "time" not in ds.coords:
                continue
            tlen = len(ds["time"])
            for var in ds.data_vars:
                if var in var_time_len and var_time_len[var] != tlen:
                    raise ValueError(
                        f"Variable '{var}' appears in multiple datasets with different "
                        f"time dimensions ({var_time_len[var]} vs {tlen} time steps). "
                        "This typically happens when the same index is computed with "
                        "different 'Computation frequency' values (e.g. Annual + Monthly)."
                    )
                var_time_len[var] = tlen
        xr.merge(datasets, compat="override", join="outer").to_netcdf(output_path)
    except (TypeError, ValueError) as exc:
        print(
            "\nERROR: Cannot merge indices — incompatible time coordinates.\n"
            "This typically happens when indices in the same group use different\n"
            "'Computation frequency' values (e.g. Monthly + Annual).\n"
            "Fix: either\n"
            "  (a) use the same frequency for all indices in the group, OR\n"
            "  (b) enable 'One output file per index' to keep them separate.\n"
            f"Technical detail: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
    finally:
        for ds in datasets:
            try:
                ds.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    try:
        if args.merge_outputs:
            merge_outputs_files(args.input, args.output)
        else:
            if not args.index_name:
                print("[ERROR parameter] --index-name is required when not using --merge-outputs",
                      file=sys.stderr)
                sys.exit(2)
            run(args)
    except (ValueError, KeyError) as exc:
        print(f"[ERROR parameter] {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
