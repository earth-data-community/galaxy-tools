# foscat-features

Extract multi-scale scattering features from a set of RGB images using
[FOSCAT](https://github.com/jmdelouis/FOSCAT) (Delouis et al. 2022). For
each image, the tool runs the scattering transform per RGB channel and
concatenates the resulting statistics (`S0, S1, S2, P00, P11, P01` where
available) into a single feature vector. Output is a single NPZ holding
the feature matrix, labels from the split file, and the resolved image
paths.

## Inputs

- **Image archive** (`.zip`): images referenced by relative path from the
  split file. Sizes can be heterogeneous — each image is resized to
  `target_size` × `target_size` before scattering.
- **Split file**: plain text, one `image_path label` per line. Image
  paths are relative to the image archive root.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `target_size` | `64` | Target image size in pixels (square). All images are resized before scattering. |
| `norient` | `8` | Number of orientations for the scattering transform (FOSCAT `NORIENT`). |
| `kernelsz` | `3` | Kernel size for the scattering transform (FOSCAT `KERNELSZ`). |

With the default `NORIENT=8`, `KERNELSZ=3`, `target_size=64`, the per-image
feature dimension is **246** (3 channels × 82 statistics) — matching the
FIESTA-bio chain configuration.

## Output

NPZ file with arrays:

- `X` (float32): `(n_kept, n_features)` feature matrix
- `y` (int64): labels from the split file, aligned to `X` rows
- `paths` (str): absolute paths of resolved images, in the same row order
  as `X`

The output schema is compatible with `features_*.npz` consumed by the
`scattering-stacking` Galaxy tool in the FIESTA-bio chain.

## Origin

Wraps the scattering-feature extraction logic from
[fiesta-scattering-bio/01_scattering_features.py](https://github.com/annefou/fiesta-scattering-bio/blob/main/01_scattering_features.py).
The tool is dataset-agnostic — any RGB image classification problem
can use this feature representation. Dataset download, split-file
generation, and class-balanced sub-sampling all live at the workflow
level (WorkflowHub), not in this tool.
