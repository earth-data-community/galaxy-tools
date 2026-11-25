---
title: "Climate stripes"
date: 2026-08-26
draft: false
weight: 1
---
# Climate stripes

This tools creates an image (png format) corresponding to the visualization of a timeseries as
climate stripes (see https://www.climate-lab-book.ac.uk/2018/warming-stripes/).
Additional parameters can be used to customize the plot.
For instance, the colormap can be changed to accomodate different variable (temperature, humidity, etc.).

This tool generate stripes from timeseries and is often used to generate warming stripes.

The wrappers aims at creating stripes from a timeseries.
The input file must be in tabular format and must contain at least one column that is used
for creating stripes. By default, no title and no axis are plotted. An additional column
can be specified for date/time and its date and time format must then be specified
with an additional options.

**What it does**
----------------

This tools creates an image (png format) corresponding to the visualization of a timeseries as
stripes (see https://www.climate-lab-book.ac.uk/2018/warming-stripes/).
By default, the colormap is ``RdBu_r`` and no axis nor title are plotted. These settings can be
changed in *Advanced settings*.
