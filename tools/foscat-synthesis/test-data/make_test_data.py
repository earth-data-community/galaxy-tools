"""
Generate test fixtures for the foscat-synthesis Galaxy tool.

Produces minimal HEALPix arrays at NSIDE=4 (192 pixels):
  - target.npy        : Gaussian random field (the reference)
  - starting.npy      : a different random realization (optional starting map)
  - eval_mask.npy     : binary mask covering ~75% of pixels (optional)
  - update_mask.npy   : binary mask covering ~25% of pixels (optional)

The fixtures exercise both pure-synthesis (target only) and gap-filling
(target + starting + eval_mask + update_mask) modes of the tool.

Run inside any Python 3.11 venv with numpy available:
    /Users/annef/Documents/ScienceLive/foscat-venv/bin/python make_test_data.py
"""

from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent

NSIDE = 4
NPIX = 12 * NSIDE * NSIDE  # 192
SEED = 42

rng = np.random.default_rng(SEED)

# Target: Gaussian random field, mean 5 std 1.5
target = (rng.standard_normal(NPIX).astype(np.float32) * 1.5 + 5.0)
np.save(HERE / "target.npy", target)
print(f"Wrote target.npy: shape ({NPIX},) mean={target.mean():.3f} std={target.std():.3f}")

# Starting map: a different realization
starting = (rng.standard_normal(NPIX).astype(np.float32) * 1.5 + 5.0)
np.save(HERE / "starting.npy", starting)
print(f"Wrote starting.npy: shape ({NPIX},) mean={starting.mean():.3f} std={starting.std():.3f}")

# Eval mask: ~75% of pixels (for example, simulating an "ocean" mask)
eval_mask = (rng.random(NPIX) < 0.75).astype(np.float32)
np.save(HERE / "eval_mask.npy", eval_mask)
print(f"Wrote eval_mask.npy: {int(eval_mask.sum())}/{NPIX} pixels active")

# Update mask: ~25% of pixels (simulating "cloudy" pixels for gap-filling)
update_mask = (rng.random(NPIX) < 0.25).astype(np.float32)
np.save(HERE / "update_mask.npy", update_mask)
print(f"Wrote update_mask.npy: {int(update_mask.sum())}/{NPIX} pixels active")

print("Done.")
