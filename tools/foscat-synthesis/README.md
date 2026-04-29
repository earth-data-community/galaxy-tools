# foscat-synthesis

Galaxy tool that synthesizes a HEALPix map **or a 2D image** (or fills
gaps in either) so that its multi-scale scattering-transform statistics
match a target reference, using
[FOSCAT](https://github.com/jmdelouis/FOSCAT)
([Delouis et al. 2022](https://doi.org/10.1051/0004-6361/202244566)).

The `domain` parameter selects between HEALPix (1D arrays of length
`12 * nside**2`) and 2D rectangular images (any `(H, W)`). Both modes
support pure synthesis and gap-filling.

## Two modes from one tool

The same algorithm covers two distinct use cases, controlled by which
optional masks are supplied:

### Pure synthesis (one input)

Generate a new realization whose scattering statistics match a target
map (e.g. a cosmological large-scale-structure map, an astrophysical
foreground). Provide only the **target_map**; the tool starts from
random Gaussian noise scaled to the target's mean and std and iterates
until the scattering statistics match. The output is visually distinct
from the target but has the same multi-scale texture.

### Gap-filling (target + starting + masks)

Replace masked regions of an observed map with values whose scattering
statistics match a gap-free reference. Supply:

- the gap-free reference as **target_map** (e.g. an SST L4 product)
- the gappy observation plus a baseline fill as **starting_map** (e.g.
  L3S with cloudy pixels filled by a spherical-harmonics fit)
- the **eval_mask** for where the reference statistics should be
  computed (e.g. ocean-only)
- the **update_mask** for which pixels the synthesis is allowed to
  modify (e.g. cloudy pixels only — observed pixels stay fixed)

The tool emits a synthesized map and a results JSON with config and
validation summary.

## Inputs

- **Target map** (`.npy`): 1D HEALPix array of length `12 * nside**2`,
  or a 2D `(1, n_pixels)` array.
- **Starting map** (`.npy`, optional): same shape as target.
- **Evaluation mask** (`.npy`, optional): same shape as target.
- **Update mask** (`.npy`, optional): same shape as target.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `domain` | `healpix` | `healpix` (1D HEALPix) or `image_2d` (2D rectangular image — sets FOSCAT's `use_2D=True` internally). |
| `norient` | `4` | FOSCAT `NORIENT` — orientations for the scattering transform. |
| `kernelsz` | `3` | FOSCAT `KERNELSZ` — kernel size. |
| `nsteps` | `300` | Synthesis iterations (`NUM_EPOCHS`). |
| `seed` | `1234` | Seed for the random starting noise (used only when no starting map is provided). |

### Advanced options (collapsed by default)

| Parameter | Default | Meaning |
|---|---|---|
| `do_lbfgs` | `true` | Use L-BFGS optimizer. Uncheck to use FOSCAT's first-order fallback. |
| `eval_frequency` | `0` (= `nsteps/10`) | How often, in iterations, the loss is printed during synthesis. |

## Outputs

- **Synthesized map** (`.npy`): same shape as the target.
- **Results JSON**: tool config, target/synth mean and std, scattering-
  coefficient error before and after synthesis, and an "improvement %"
  summary (drop in scattering-coefficient error vs. the starting point).

## Origin

Wraps the FOSCAT synthesis pattern shared across the FIESTA-OSCARS
chains:
- [fiesta-scattering-astro](https://github.com/annefou/fiesta-scattering-astro)
  — pure synthesis from a cosmological LSS map
- [fiesta-scattering-sst](https://github.com/annefou/fiesta-scattering-sst)
  — SST gap-filling with L4 reference, standard HEALPix
- [fiesta-scattering-sst-healpix-geo](https://github.com/annefou/fiesta-scattering-sst-healpix-geo)
  — SST gap-filling with L4 reference, WGS84-ellipsoid HEALPix

The chain-specific bits (data download, preprocessing, masking choices,
plotting) live at the WorkflowHub workflow level — this tool provides
only the generic FOSCAT optimization step.

## Implementation notes

`foscat>=2026.4.1` is pip-installed at runtime via the same
`--target=tool_pkgs` + `PYTHONPATH` pattern as `planktonclas-inference`
and `foscat-features`. `MPLBACKEND=Agg` is set as a tool environment
variable so matplotlib (an indirect FOSCAT dep) doesn't try to load a
GUI backend in the headless mulled Docker container.
`KMP_DUPLICATE_LIB_OK=TRUE` is set to silence the duplicate-libomp
warning the FOSCAT scripts trip on some platforms.

## Citations

- Delouis et al. (2022) — FOSCAT scattering transform method
  ([10.1051/0004-6361/202244566](https://doi.org/10.1051/0004-6361/202244566))
- FOSCAT package — [github.com/jmdelouis/FOSCAT](https://github.com/jmdelouis/FOSCAT)
