# foscat-synthesis

Synthesize a map (or fill gaps in a map) so that its multi-scale
scattering-transform statistics match a target reference, using
[FOSCAT](https://github.com/jmdelouis/FOSCAT) (Delouis et al. 2022).

The same algorithm covers two distinct use cases, controlled by which
optional masks are supplied:

- **Pure synthesis** — generate a new realization with the same
  scattering statistics as a target map (e.g. a cosmological large-scale
  structure map, an astrophysical foreground). Provide only the target;
  the tool starts from random noise scaled to the target's mean/std.
- **Gap-filling** — replace masked regions of an observed map with
  values whose scattering statistics match those of a gap-free
  reference (e.g. cloudy SST pixels filled to match an L4 product).
  Supply the L4 reference as `target_map`, the gappy observed-plus-baseline
  map as `starting_map`, an evaluation mask (where the reference
  statistics are computed, e.g. ocean-only), and an update mask (which
  pixels the synthesis is allowed to modify, e.g. cloudy pixels only).

## Inputs

- **Target map** (`.npy`): 1D HEALPix array of length `12 * nside**2`,
  or a 2D `(1, n_pixels)` array. The synthesis matches this map's
  scattering statistics.
- **Starting map** (`.npy`, optional): same shape as target. If absent,
  the tool generates random Gaussian noise scaled to the target's mean
  and std.
- **Evaluation mask** (`.npy`, optional): same shape as target.
  Restricts where the scattering statistics are computed (e.g. ocean-
  only). If absent, all pixels contribute.
- **Update mask** (`.npy`, optional): same shape as target. Restricts
  which pixels the synthesis updates (FOSCAT's `grd_mask`). Use this
  for gap-filling — only cloudy pixels are updated, observed pixels
  stay fixed.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `norient` | `4` | Number of orientations for the scattering transform (FOSCAT `NORIENT`). |
| `kernelsz` | `3` | Kernel size for the scattering transform (FOSCAT `KERNELSZ`). |
| `nsteps` | `300` | Number of synthesis iterations (`NUM_EPOCHS`). |
| `seed` | `1234` | Random seed for the starting noise (used only when no starting map is provided). |

## Outputs

- **Synthesized map** (`.npy`): same shape as the target.
- **Results JSON**: tool config, validation statistics (target/synth
  mean and std), and the scattering-coefficient error before and after
  synthesis with an "improvement %" summary.

## Origin

Wraps the FOSCAT synthesis pattern shared across the FIESTA-OSCARS
chains [astro](https://github.com/annefou/fiesta-scattering-astro),
[sst](https://github.com/annefou/fiesta-scattering-sst), and
[sst-healpix-geo](https://github.com/annefou/fiesta-scattering-sst-healpix-geo).
The chain-specific parts (data ingest, preprocessing, masking choices,
plot generation) live at the workflow level on WorkflowHub; this tool
provides only the generic FOSCAT optimization step.
