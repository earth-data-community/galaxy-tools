"""
Generate test fixtures for the foscat-synthesis Galaxy tool.

HEALPix fixtures (NSIDE=4 → 192 pixels):
  - target.npy        : Gaussian random field (the HEALPix reference)
  - starting.npy      : a different random realization
  - eval_mask.npy     : binary mask covering ~75% of pixels
  - update_mask.npy   : binary mask covering ~25% of pixels

2D image fixtures (32 x 32):
  - target_2d.npy        : 2D Gaussian random field (the image reference)
  - starting_2d.npy      : a different 2D random realization
  - eval_mask_2d.npy     : 2D binary mask covering ~75% of pixels
  - update_mask_2d.npy   : 2D binary mask covering ~25% of pixels

Each fixture set exercises both pure-synthesis (target only) and gap-
filling (target + starting + eval_mask + update_mask) modes of the
tool. The two domains exercise the FOSCAT HEALPix path and the
2D-image (use_2D=True) path.

Run inside any Python 3.11 venv with numpy available:
    /Users/annef/Documents/ScienceLive/foscat-venv/bin/python make_test_data.py
"""

from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SEED = 42
rng = np.random.default_rng(SEED)


def _gaussian(shape, mean=5.0, std=1.5):
    return rng.standard_normal(shape).astype(np.float32) * std + mean


# ---------- HEALPix fixtures (NSIDE=4) -----------------------------------

NSIDE = 4
NPIX = 12 * NSIDE * NSIDE  # 192

target = _gaussian(NPIX)
np.save(HERE / "target.npy", target)
print(
    f"Wrote target.npy: shape ({NPIX},) mean={target.mean():.3f} std={target.std():.3f}"
)

starting = _gaussian(NPIX)
np.save(HERE / "starting.npy", starting)
print(
    f"Wrote starting.npy: shape ({NPIX},) mean={starting.mean():.3f} std={starting.std():.3f}"
)

eval_mask = (rng.random(NPIX) < 0.75).astype(np.float32)
np.save(HERE / "eval_mask.npy", eval_mask)
print(f"Wrote eval_mask.npy: {int(eval_mask.sum())}/{NPIX} pixels active")

update_mask = (rng.random(NPIX) < 0.25).astype(np.float32)
np.save(HERE / "update_mask.npy", update_mask)
print(f"Wrote update_mask.npy: {int(update_mask.sum())}/{NPIX} pixels active")

# ---------- 2D image fixtures (32 x 32) ---------------------------------

H, W = 32, 32
n_pix_2d = H * W

target_2d = _gaussian((H, W))
np.save(HERE / "target_2d.npy", target_2d)
print(
    f"Wrote target_2d.npy: shape ({H}, {W}) mean={target_2d.mean():.3f} "
    f"std={target_2d.std():.3f}"
)

starting_2d = _gaussian((H, W))
np.save(HERE / "starting_2d.npy", starting_2d)
print(
    f"Wrote starting_2d.npy: shape ({H}, {W}) mean={starting_2d.mean():.3f} "
    f"std={starting_2d.std():.3f}"
)

eval_mask_2d = (rng.random((H, W)) < 0.75).astype(np.float32)
np.save(HERE / "eval_mask_2d.npy", eval_mask_2d)
print(
    f"Wrote eval_mask_2d.npy: {int(eval_mask_2d.sum())}/{n_pix_2d} pixels active"
)

update_mask_2d = (rng.random((H, W)) < 0.25).astype(np.float32)
np.save(HERE / "update_mask_2d.npy", update_mask_2d)
print(
    f"Wrote update_mask_2d.npy: {int(update_mask_2d.sum())}/{n_pix_2d} pixels active"
)

print("Done.")
