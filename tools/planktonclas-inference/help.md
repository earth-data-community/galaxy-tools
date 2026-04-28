# planktonclas-inference

Galaxy tool that runs Keras image-classifier inference using the
[planktonclas](https://pypi.org/project/planktonclas/) pipeline. Originally
built around Decrop et al. 2025's pretrained EfficientNetV2-B0 phytoplankton
classifier, but applicable to any planktonclas-format model.

The tool runs 10-crop test-time augmentation (TTA) by default — the same
configuration used to produce Decrop's canonical results — and writes a
single NPZ output with full per-image softmax probabilities.

## Inputs

- **Model archive** (`.tar.gz`): planktonclas-format model directory
  containing `ckpts/final_model.h5`, `conf.json`, and
  `dataset_files/classes.txt`. Decrop's pretrained model on
  [Zenodo record 15269453](https://zenodo.org/records/15269453) follows
  this layout.
- **Image archive** (`.zip`): images referenced by relative path from the
  split file.
- **Split file**: plain text, one `image_path label` per line. Image paths
  are relative to the image archive root.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `top_K` | `0` (= full softmax) | Number of top predictions to keep. `0` means return the full `(N, num_classes)` softmax — matches the FIESTA-bio canonical output schema. |
| `crop_num` | `10` | Number of TTA crops. `10` matches Decrop's canonical pipeline; `1` disables TTA. Disabling TTA will diverge from Decrop's published numbers. |

## Output

NPZ file with:
- `y_true` (int64): labels from the split file
- `y_pred` (int64): top-1 predicted class index per image
- `full_probs` (float16): `(N, num_classes)` softmax matrix when `top_K=0`,
  or `(N, top_K)` sparse probabilities otherwise
- `paths` (str): absolute paths of resolved images, in the same row order as
  `full_probs`

The output schema is compatible with `cnn_predictions_*.npz` consumed by the
`scattering-stacking` Galaxy tool in the FIESTA-bio chain.

## Origin

Wraps the inference logic from
[fiesta-scattering-bio/02_cnn_predictions.py](https://github.com/annefou/fiesta-scattering-bio/blob/main/02_cnn_predictions.py).
The tool is honestly coupled to planktonclas — the 10-crop TTA, custom Keras
objects, and config schema are all inherited from that package.
