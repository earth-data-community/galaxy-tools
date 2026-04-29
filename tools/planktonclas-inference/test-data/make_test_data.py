"""
Generate minimal test fixtures for the planktonclas-inference Galaxy tool.

Produces:
  - model.tar.gz : planktonclas-format archive (ckpts/final_model.h5,
                   conf/conf.json, dataset_files/classes.txt) for a tiny
                   3-class CNN on 32x32 RGB inputs.
  - images.zip   : 6 synthetic 32x32 RGB jpg images, 2 per class.
  - split.txt    : 6 lines of 'image_path label'.

The model is vanilla Keras (no planktonclas custom layers), but it is
saved + loaded via the planktonclas pipeline at test time, exercising
the tool wrapper end-to-end. crop_num=1 keeps the test fast.

Run inside the planktonclas-venv:
    /Users/annef/Documents/ScienceLive/planktonclas-venv/bin/python make_test_data.py
"""
import json
import shutil
import tarfile
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image
from tensorflow import keras
from tensorflow.keras import layers

HERE = Path(__file__).resolve().parent
WORK = HERE / "_build"
if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir()

IM_SIZE = 32  # model input size; images get resized to this regardless of source size
N_CLASSES = 3
CLASS_NAMES = ["alpha", "beta", "gamma"]
N_PER_CLASS = 2

# Heterogeneous source sizes (height, width) — verifies that planktonclas's
# pipeline resizes any input shape to IM_SIZE before model inference.
SOURCE_SIZES = [
    (32, 32),    # alpha_0 — equal to model input
    (96, 72),    # alpha_1 — larger, non-square
    (24, 40),    # beta_0  — smaller, non-square (upscaled)
    (128, 64),   # beta_1  — wide
    (80, 80),    # gamma_0 — larger square
    (48, 64),    # gamma_1 — non-square
]
assert len(SOURCE_SIZES) == N_CLASSES * N_PER_CLASS

# --- 1. Build tiny model -----------------------------------------------------

inp = keras.Input(shape=(IM_SIZE, IM_SIZE, 3), name="input")
x = layers.Conv2D(8, 3, padding="same", activation="relu")(inp)
x = layers.GlobalAveragePooling2D()(x)
out = layers.Dense(N_CLASSES, activation="softmax")(x)
model = keras.Model(inp, out)
model.compile(optimizer="adam", loss="sparse_categorical_crossentropy")
print("Model summary:")
model.summary()

# Save in planktonclas-expected layout (matching what the published
# Phytoplankton_EfficientNetV2B0 bundle on Zenodo 15269453 ships):
#   <model_dir>/
#     ckpts/final_model.h5
#     conf/conf.json
#     dataset_files/classes.txt
MODEL_DIR = WORK / "tiny_model"
(MODEL_DIR / "ckpts").mkdir(parents=True)
(MODEL_DIR / "conf").mkdir()
(MODEL_DIR / "dataset_files").mkdir()

model.save(str(MODEL_DIR / "ckpts" / "final_model.h5"))

# --- 2. conf.json ------------------------------------------------------------

conf = {
    "model": {
        "modelname": "tiny_test",
        "image_size": IM_SIZE,
        "num_classes": N_CLASSES,
        "preprocess_mode": "tf",
    },
    "dataset": {
        "mean_RGB": [127.5, 127.5, 127.5],
        "std_RGB": [64.0, 64.0, 64.0],
    },
    "augmentation": {
        "use_augmentation": False,
        "train_mode": None,
        "val_mode": None,
    },
    "general": {
        "base_directory": ".",
        "images_directory": ".",
    },
    "testing": {
        "ckpt_name": "final_model.h5",
        "output_directory": None,
        "timestamp": None,
    },
}
with open(MODEL_DIR / "conf" / "conf.json", "w") as f:
    json.dump(conf, f, indent=2)

# --- 3. classes.txt ----------------------------------------------------------

with open(MODEL_DIR / "dataset_files" / "classes.txt", "w") as f:
    for name in CLASS_NAMES:
        f.write(name + "\n")

# --- 4. Tar up the model -----------------------------------------------------

MODEL_TGZ = HERE / "model.tar.gz"
with tarfile.open(MODEL_TGZ, "w:gz") as tf_out:
    tf_out.add(MODEL_DIR, arcname="tiny_model")
print(f"Wrote {MODEL_TGZ} ({MODEL_TGZ.stat().st_size} bytes)")

# --- 5. Generate synthetic images -------------------------------------------

IMG_DIR = WORK / "images"
IMG_DIR.mkdir()
rng = np.random.default_rng(42)

split_lines = []
src_iter = iter(SOURCE_SIZES)
for cls_idx, cls_name in enumerate(CLASS_NAMES):
    cls_dir = IMG_DIR / cls_name
    cls_dir.mkdir()
    for i in range(N_PER_CLASS):
        # Distinct color per class so the synthetic data is at least separable
        base = np.array(
            [
                [80, 40, 200],   # alpha → blueish
                [200, 80, 40],   # beta  → reddish
                [40, 200, 80],   # gamma → greenish
            ][cls_idx],
            dtype=np.int16,
        )
        h, w = next(src_iter)
        noise = rng.integers(-20, 20, size=(h, w, 3))
        arr = np.clip(base[None, None, :] + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)
        rel_path = f"{cls_name}/{cls_name}_{i}_{h}x{w}.jpg"
        img.save(IMG_DIR / rel_path, "JPEG")
        split_lines.append(f"{rel_path} {cls_idx}")

# --- 6. Zip images -----------------------------------------------------------

IMAGES_ZIP = HERE / "images.zip"
with zipfile.ZipFile(IMAGES_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    for line in split_lines:
        rel_path = line.rsplit(" ", 1)[0]
        zf.write(IMG_DIR / rel_path, arcname=rel_path)
print(f"Wrote {IMAGES_ZIP} ({IMAGES_ZIP.stat().st_size} bytes)")
print(f"  source sizes: {SOURCE_SIZES} (all resized to {IM_SIZE}x{IM_SIZE} at inference)")

# --- 7. Split file -----------------------------------------------------------

SPLIT_TXT = HERE / "split.txt"
SPLIT_TXT.write_text("\n".join(split_lines) + "\n")
print(f"Wrote {SPLIT_TXT} ({len(split_lines)} entries)")

shutil.rmtree(WORK)
print("\nDone.")
