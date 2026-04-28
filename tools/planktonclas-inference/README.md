# planktonclas-inference

Galaxy tool for Keras image-classifier inference using the
[planktonclas](https://pypi.org/project/planktonclas/) pipeline. Originally
built around [Decrop et al. 2025](https://doi.org/10.3389/fmars.2025.1699781)'s
pretrained EfficientNetV2-B0 phytoplankton classifier
([Zenodo record 15269453](https://zenodo.org/records/15269453)), but applicable
to any planktonclas-format model.

The tool runs 10-crop test-time augmentation (TTA) by default — the same
configuration used to produce Decrop's canonical results — and writes a
single NPZ output with full per-image softmax probabilities.

## Inputs

- **Model archive** (`.tar.gz`): planktonclas-format model directory with
  `ckpts/final_model.h5`, `conf.json`, `dataset_files/classes.txt`.
- **Image archive** (`.zip`): images referenced by relative path from the
  split file. Sizes can be heterogeneous — each image is resized to
  `conf.json`'s `model.image_size` before inference.
- **Split file**: plain text, one `image_path label` per line.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `top_K` | `0` (= full softmax) | Number of top predictions to keep. `0` returns the full `(N, num_classes)` softmax matrix — matches the FIESTA-bio canonical output schema. |
| `crop_num` | `10` | Number of TTA crops. `10` matches Decrop's canonical pipeline; `1` disables TTA. Disabling TTA will diverge from Decrop's published numbers. |

## Output

NPZ file with arrays:

- `y_true` (int64): labels from the split file
- `y_pred` (int64): top-1 predicted class index per image
- `full_probs` (float16): `(N, num_classes)` softmax matrix when `top_K=0`,
  or `(N, top_K)` sparse probabilities otherwise
- `paths` (str): absolute paths of resolved images, in the same row order
  as `full_probs`

The schema is compatible with `cnn_predictions_*.npz` consumed by the
`scattering-stacking` Galaxy tool in the FIESTA-bio chain.

## Reproducibility

The tool is parameterised and dataset-agnostic. Reproducing the canonical
FIESTA-bio CNN softmax NPZ files (matching Decrop et al. 2025's published
numbers) requires:

- Decrop's pretrained model archive (`Phytoplankton_EfficientNetV2B0.tar.gz`
  on [Zenodo record 15269453](https://zenodo.org/records/15269453))
- LifeWatch FlowCam dataset
  ([Zenodo record 10554845](https://zenodo.org/records/10554845))
- Decrop's split files (bundled inside the model tarball at
  `dataset_files/`)
- Default `crop_num=10` and `top_K=0`

Reproducibility validation is done at the workflow level on WorkflowHub,
not by the tool's planemo test (which only verifies the tool runs on
synthetic fixtures).

## Implementation notes

The tool wraps `planktonclas.test_utils.predict()` — the same function called
by step 02 of the FIESTA-bio chain
([fiesta-scattering-bio/02_cnn_predictions.py](https://github.com/annefou/fiesta-scattering-bio/blob/main/02_cnn_predictions.py)).
The 10-crop TTA, custom Keras objects, and config schema are all inherited
from planktonclas. The tool sidesteps planktonclas's stateful
`config.set_config_path()` setup by loading the model and `conf.json`
directly from the archive — `predict()` doesn't depend on that global
state.

`planktonclas==0.2.3` is pip-installed at tool runtime (no conda recipe
exists yet). First run of the tool in a fresh conda env takes ~5 min to
install TensorFlow 2.19 + OpenCV + albumentations + deepaas; subsequent
runs reuse the env.

## Citations

- Decrop et al. (2025) — phytoplankton EfficientNetV2-B0 baseline
  ([10.3389/fmars.2025.1699781](https://doi.org/10.3389/fmars.2025.1699781))
- planktonclas package — LifeWatch Belgium / VLIZ
  ([github.com/lifewatch/planktonclas](https://github.com/lifewatch/planktonclas))
