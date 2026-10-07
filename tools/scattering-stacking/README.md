# Scattering Stacking — class-weighted meta-classifier

A Galaxy tool that stacks a deep classifier's softmax probabilities with
multi-scale scattering features through a class-weighted logistic-regression
meta-classifier. The stacking is trained on a validation split and evaluated
on a held-out test split.

## Inputs

- **Scattering features** (training-balanced, validation, test): NPZ files
  containing arrays `X` (n_samples, n_features) and `y` (n_samples,) class
  labels. Validation and test files must also contain a `paths` array with
  one image identifier per row, used to align with the deep-model
  predictions.
- **Deep-model softmax probabilities** (validation, test): NPZ files
  containing arrays `full_probs` (n_samples, n_classes) and `paths` (or
  `val_paths` / `test_paths`) for alignment.
- **Class names file**: plain text, one class name per line, in label-index
  order.
- **Training split file**: plain text with one `image_path label` per line
  (the standard `planktonclas` train/val/test format), used to count
  per-class training-set sizes for the rare-class definition.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `C` | `1.0` | Logistic-regression regularisation strength (smaller = more regularisation). |
| `max_iter` | `2000` | Maximum logistic-regression iterations. |
| `rare_class_threshold` | `200` | Train-count threshold below which a class is considered rare (used for mean rare-class recall). |

## Outputs

- **Results JSON** — top-1, top-5, mean rare-class recall, and per-class
  comparison for the deep model alone, scattering alone, a 50/50
  probability ensemble, the stacked meta-classifier, and a hard-switch
  oracle ceiling.
- **Trained model** — `joblib` pickle of the fitted `StandardScaler`, the
  scattering-LR classifier, and the stacking meta-classifier.

## Origin

Originally developed for the FIESTA-OSCARS plankton-classification chain
([fiesta-scattering-bio](https://github.com/annefou/fiesta-scattering-bio)),
which extends the EfficientNetV2-B0 phytoplankton classifier of
Decrop et al. 2025 with multi-scale scattering features computed via FOSCAT
([Delouis et al. 2022](https://doi.org/10.1051/0004-6361/202244566)). The
tool itself is dataset-agnostic — any classification problem with paired
deep-model softmax probabilities and an independent feature representation
can be stacked this way.

## Reproducibility

The Galaxy tool is parameterised and dataset-agnostic. Reproducing the
canonical FIESTA-OSCARS plankton numbers (+8.4 percentage points rare-class
recall vs. the CNN baseline) is done at the workflow level, on
WorkflowHub, by chaining `foscat-features` → `scattering-stacking` with
the FIESTA inputs and parameters.

## Citations

- Decrop et al. (2025) — phytoplankton classifier baseline
  ([10.3389/fmars.2025.1699781](https://doi.org/10.3389/fmars.2025.1699781))
- Delouis et al. (2022) — FOSCAT scattering features
  ([10.1051/0004-6361/202244566](https://doi.org/10.1051/0004-6361/202244566))
