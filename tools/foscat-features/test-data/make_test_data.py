"""
Generate test fixtures for the foscat-features Galaxy tool.

Produces:
  - images.zip : 6 synthetic heterogeneously-sized RGB jpg images, 2 per
                 class, exercising the resize-to-target_size path.
  - split.txt  : 6 lines of 'image_path label'.

Run inside the foscat-venv (or any venv with numpy and pillow):
    /Users/annef/Documents/ScienceLive/foscat-venv/bin/python make_test_data.py
"""

import shutil
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
WORK = HERE / "_build"
if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir()

CLASS_NAMES = ["alpha", "beta", "gamma"]
N_PER_CLASS = 2

# Heterogeneous source sizes (height, width) — verifies that the tool's
# resize-to-target_size path handles arbitrary input shapes.
SOURCE_SIZES = [
    (32, 32),    # alpha_0 — small square
    (96, 72),    # alpha_1 — non-square, larger
    (24, 40),    # beta_0  — non-square, smaller
    (128, 64),   # beta_1  — wide
    (80, 80),    # gamma_0 — larger square
    (48, 64),    # gamma_1 — non-square
]
assert len(SOURCE_SIZES) == len(CLASS_NAMES) * N_PER_CLASS

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
                [80, 40, 200],   # alpha
                [200, 80, 40],   # beta
                [40, 200, 80],   # gamma
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

IMAGES_ZIP = HERE / "images.zip"
with zipfile.ZipFile(IMAGES_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    for line in split_lines:
        rel_path = line.rsplit(" ", 1)[0]
        zf.write(IMG_DIR / rel_path, arcname=rel_path)
print(f"Wrote {IMAGES_ZIP} ({IMAGES_ZIP.stat().st_size} bytes)")

SPLIT_TXT = HERE / "split.txt"
SPLIT_TXT.write_text("\n".join(split_lines) + "\n")
print(f"Wrote {SPLIT_TXT} ({len(split_lines)} entries)")
print(f"  source sizes: {SOURCE_SIZES} (resized to target_size at inference)")

shutil.rmtree(WORK)
