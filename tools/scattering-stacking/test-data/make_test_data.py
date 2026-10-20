"""Generate small synthetic test fixtures for the scattering-stacking Galaxy tool.

Produces:
  features_train.npz       (X, y)        — 65 samples × 4 features
  features_val.npz         (X, y, paths) — 16 samples × 4 features
  features_test.npz        (X, y, paths) — 16 samples × 4 features
  cnn_val.npz              (full_probs, paths) — 16 × 4
  cnn_test.npz             (full_probs, paths) — 16 × 4
  classes.txt              — 4 class names
  train.txt                — 65 'path label' lines (one rare class with 5 samples,
                              three abundant classes with 20 each)

Numbers are arbitrary — this is a *runtime* test, not a reproducibility test.
The tool is verified to run end-to-end and produce well-formed outputs.
Reproducibility of the FIESTA bio chain's canonical numbers happens at the
workflow level, not here.
"""

from pathlib import Path

import numpy as np

OUT = Path(__file__).parent
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(42)

CLASSES = ["RareTaxon", "CommonA", "CommonB", "CommonC"]
# class 0 is rare (< default threshold 200; the test passes threshold=10)
TRAIN_PER_CLASS = [5, 20, 20, 20]
VAL_PER_CLASS = [4, 4, 4, 4]
TEST_PER_CLASS = [4, 4, 4, 4]
N_FEAT = 4
N_CLASS = len(CLASSES)


def make_split(per_class, prefix):
    X, y, paths = [], [], []
    for cls_idx, n in enumerate(per_class):
        # add per-class mean shift so a linear classifier can learn signal
        mean = np.eye(N_FEAT)[cls_idx % N_FEAT] * 2.0
        for k in range(n):
            X.append(rng.normal(loc=mean, scale=1.0, size=N_FEAT).astype(np.float32))
            y.append(cls_idx)
            paths.append(f"{prefix}/{CLASSES[cls_idx]}/img_{k:03d}.jpg")
    return np.stack(X), np.array(y, dtype=np.int64), np.array(paths)


X_tr, y_tr, _ = make_split(TRAIN_PER_CLASS, "train")
X_val, y_val, p_val = make_split(VAL_PER_CLASS, "val")
X_test, y_test, p_test = make_split(TEST_PER_CLASS, "test")

np.savez(OUT / "features_train.npz", X=X_tr, y=y_tr)
np.savez(OUT / "features_val.npz", X=X_val, y=y_val, paths=p_val)
np.savez(OUT / "features_test.npz", X=X_test, y=y_test, paths=p_test)


def make_cnn_probs(y, paths):
    """Synthetic CNN softmax — peaked on the true class with noise."""
    n = len(y)
    logits = rng.normal(size=(n, N_CLASS)).astype(np.float32)
    logits[np.arange(n), y] += 3.0   # boost the true-class logit
    e = np.exp(logits - logits.max(axis=1, keepdims=True))
    probs = e / e.sum(axis=1, keepdims=True)
    return probs.astype(np.float32), np.array(paths)


cnn_val_probs, cnn_val_paths = make_cnn_probs(y_val, p_val)
cnn_test_probs, cnn_test_paths = make_cnn_probs(y_test, p_test)

np.savez(OUT / "cnn_val.npz", full_probs=cnn_val_probs, paths=cnn_val_paths)
np.savez(OUT / "cnn_test.npz", full_probs=cnn_test_probs, paths=cnn_test_paths)

(OUT / "classes.txt").write_text("\n".join(CLASSES) + "\n")

train_lines = []
for cls_idx, n in enumerate(TRAIN_PER_CLASS):
    for k in range(n):
        train_lines.append(f"train/{CLASSES[cls_idx]}/img_{k:03d}.jpg {cls_idx}")
(OUT / "train.txt").write_text("\n".join(train_lines) + "\n")

print(f"Wrote synthetic test fixtures to {OUT}")
