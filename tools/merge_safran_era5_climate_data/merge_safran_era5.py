#!/usr/bin/env python3
"""
merge_safran_era5.py
---------------------
Join a SAFRAN climate data file and an ERA5 / ERA5-Land climate data file on
a site identifier and a date, so that variables available only in one of the
two sources (e.g. ERA5 depth-resolved soil moisture/temperature) can be
combined with the other source (e.g. SAFRAN atmospheric variables) for the
same site and date.

Both input files are expected to be CSV files with a header row. The two
files do not need to share column names, column order, or the same set of
sites: the caller selects, by 1-based column index, which column plays the
site/date/variable role in each file.
"""

import argparse
import logging
import sys

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

JOIN_TYPES = ("inner", "left", "right", "outer")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--safran-file", required=True)
    parser.add_argument("--safran-site-column", required=True, type=int)
    parser.add_argument("--safran-date-column", required=True, type=int)
    parser.add_argument("--safran-value-columns", default=None)
    parser.add_argument("--era5-file", required=True)
    parser.add_argument("--era5-site-column", required=True, type=int)
    parser.add_argument("--era5-date-column", required=True, type=int)
    parser.add_argument("--era5-value-columns", default=None)
    parser.add_argument("--join-type", required=True, choices=JOIN_TYPES)
    parser.add_argument("--round-decimals", required=True, type=int)
    parser.add_argument("--date-start", default=None)
    parser.add_argument("--date-end", default=None)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def parse_column_indices(raw):
    if not raw:
        return None
    return [int(token) for token in raw.split(",") if token.strip()]


def load_source(label, filepath, site_idx, date_idx, value_idx):
    """Load one input file and reduce it to site_name, date, and the
    requested variable columns, with the key columns validated and
    normalised."""
    if site_idx == date_idx:
        raise ValueError(
            f"{label}: the site column and the date column cannot be the same column."
        )

    df = pd.read_csv(filepath)
    ncols = len(df.columns)
    for col_name, idx in (("site", site_idx), ("date", date_idx)):
        if idx < 1 or idx > ncols:
            raise ValueError(
                f"{label}: {col_name} column index {idx} is out of range "
                f"(file has {ncols} column(s))."
            )

    site_col = df.columns[site_idx - 1]
    date_col = df.columns[date_idx - 1]

    if value_idx is None:
        value_cols = [c for c in df.columns if c not in (site_col, date_col)]
    else:
        value_cols = []
        for idx in value_idx:
            if idx < 1 or idx > ncols:
                raise ValueError(
                    f"{label}: variable column index {idx} is out of range "
                    f"(file has {ncols} column(s))."
                )
            col = df.columns[idx - 1]
            if col in (site_col, date_col):
                continue
            if col not in value_cols:
                value_cols.append(col)

    # the selected key columns are renamed to "site_name" / "date"; a variable
    # column already carrying one of those names would create duplicate labels
    clashing = [c for c in value_cols if c in ("site_name", "date")]
    if clashing:
        raise ValueError(
            f"{label}: the file has a column named {clashing[0]!r} that is not the "
            f"column selected as {'site' if clashing[0] == 'site_name' else 'date'} "
            f"(selected: site='{site_col}', date='{date_col}'). Check the column "
            "indices (1-based) chosen for the site and date columns."
        )

    out = df[[site_col, date_col] + value_cols].copy()
    out = out.rename(columns={site_col: "site_name", date_col: "date"})

    parsed_dates = pd.to_datetime(out["date"], errors="coerce")
    unparseable = int(parsed_dates.isna().sum())
    if unparseable:
        raise ValueError(
            f"{label}: {unparseable} row(s) have a date (column '{date_col}') "
            "that could not be parsed."
        )
    out["date"] = parsed_dates.dt.strftime("%Y-%m-%d")

    duplicates = int(out.duplicated(subset=["site_name", "date"]).sum())
    if duplicates:
        raise ValueError(
            f"{label}: {duplicates} row(s) share the same site and date; "
            "each site/date combination must be unique within a file."
        )

    log.info(
        "%s: %d row(s), %d site(s), variable column(s): %s",
        label, len(out), out["site_name"].nunique(), ", ".join(value_cols) or "(none)",
    )
    return out


def filter_dates(df, start, end):
    if start:
        df = df[df["date"] >= start]
    if end:
        df = df[df["date"] <= end]
    return df


def collapse_coordinates(df):
    """Merge latitude/longitude columns present in both sources into a single
    column. SAFRAN values take precedence; ERA5 values fill the rows where
    SAFRAN is missing (right/outer joins)."""
    for coord in ("longitude", "latitude"):
        col_s, col_e = f"{coord}_safran", f"{coord}_era5"
        if col_s not in df.columns or col_e not in df.columns:
            continue
        both = df[col_s].notna() & df[col_e].notna()
        differing = int((both & ((df[col_s] - df[col_e]).abs() > 1e-6)).sum())
        if differing:
            log.warning(
                "%s differs between SAFRAN and ERA5 on %d row(s); SAFRAN value kept.",
                coord, differing,
            )
        pos = df.columns.get_loc(col_s)
        df.insert(pos, coord, df[col_s].combine_first(df[col_e]))
        df = df.drop(columns=[col_s, col_e])
    return df


def main(argv=None):
    args = parse_args(argv)

    safran = load_source(
        "SAFRAN file", args.safran_file,
        args.safran_site_column, args.safran_date_column,
        parse_column_indices(args.safran_value_columns),
    )
    era5 = load_source(
        "ERA5 file", args.era5_file,
        args.era5_site_column, args.era5_date_column,
        parse_column_indices(args.era5_value_columns),
    )

    safran = filter_dates(safran, args.date_start, args.date_end)
    era5 = filter_dates(era5, args.date_start, args.date_end)

    merged = pd.merge(
        safran, era5,
        on=["site_name", "date"],
        how=args.join_type,
        suffixes=("_safran", "_era5"),
    )
    merged = collapse_coordinates(merged)
    merged = merged.sort_values(by=["site_name", "date"]).reset_index(drop=True)

    numeric_cols = merged.select_dtypes(include="float").columns
    merged[numeric_cols] = merged[numeric_cols].round(args.round_decimals)

    if merged.empty:
        log.warning("The merged output has no rows. Check the join type and the selected date range.")

    log.info(
        "Merged output (%s join): %d row(s), %d site(s).",
        args.join_type, len(merged), merged["site_name"].nunique() if not merged.empty else 0,
    )
    merged.to_csv(args.output, index=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - surfaced to the user via stderr/exit code
        log.error(str(exc))
        sys.exit(1)
