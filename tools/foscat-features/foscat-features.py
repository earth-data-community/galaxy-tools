#!/usr/bin/env python

# This script is generated with nb2galaxy and hand-corrected.

# flake8: noqa

import json
import os
import shutil

# Galaxy tool parameters — Papermill convention with ODA semantic annotations.
# Defaults are placeholders; Galaxy injects real values at runtime.

images_archive = "images.zip"  # oda:POSIXPath; oda:label "Image archive (.zip), images referenced by relative path in the split file"
split_file = "split.txt"  # oda:POSIXPath; oda:label "Split file with one 'image_path label' per line; image_path is relative to the image archive root"

target_size = 64  # oda:Integer; oda:label "Target image size in pixels (square; images are resized to target_size x target_size before scattering)"
norient = 8  # oda:Integer; oda:label "Number of orientations for the scattering transform (FOSCAT NORIENT)"
kernelsz = 3  # oda:Integer; oda:label "Kernel size for the scattering transform (FOSCAT KERNELSZ)"

_galaxy_wd = os.getcwd()

with open("inputs.json", "r") as fd:
    inp_dic = json.load(fd)
if "C_data_product_" in inp_dic.keys():
    inp_pdic = inp_dic["C_data_product_"]
else:
    inp_pdic = inp_dic
images_archive = str(inp_pdic["images_archive"])
split_file = str(inp_pdic["split_file"])
target_size = int(inp_pdic["target_size"])
norient = int(inp_pdic["norient"])
kernelsz = int(inp_pdic["kernelsz"])

import time
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

work = Path.cwd()

# %% [markdown]
# ## 1. Extract image archive

# %%
images_dir = work / "_images"
if images_dir.exists():
    shutil.rmtree(images_dir)
images_dir.mkdir()
with zipfile.ZipFile(images_archive) as zf:
    zf.extractall(images_dir)

# If the zip contained a single top-level directory, use that as the image root
img_top = [p for p in images_dir.iterdir() if p.is_dir()]
if len(img_top) == 1 and not any(p.is_file() for p in images_dir.iterdir()):
    images_root = img_top[0]
else:
    images_root = images_dir
print(f"Images root: {images_root}")

# %% [markdown]
# ## 2. Parse split file

# %%
split_paths_, split_rel_paths_, split_labels_ = [], [], []
missing = 0
with open(split_file) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rel, lab = line.rsplit(" ", 1)
        full = images_root / rel
        if not full.exists():
            cand = Path(rel)
            if cand.is_absolute() and cand.exists():
                full = cand
            else:
                missing += 1
                continue
        # split_paths_ holds the absolute path (used to OPEN the image
        # in extract()). split_rel_paths_ holds the path relative to the
        # image archive root (saved in the output NPZ for downstream
        # alignment with other tools' outputs — the absolute paths
        # differ between Galaxy job tmp dirs).
        split_paths_.append(str(full))
        split_rel_paths_.append(rel)
        split_labels_.append(int(lab))
split_labels = np.array(split_labels_, dtype=np.int64)
print(f"Resolved {len(split_paths_)} images from split file ({missing} missing)")
assert (
    len(split_paths_) > 0
), "No images resolved from split file — check the image archive layout."

# %% [markdown]
# ## 3. Initialize FOSCAT scattering transform

# %%
import foscat.scat_cov as sc

scat = sc.funct(
    NORIENT=norient,
    KERNELSZ=kernelsz,
    all_type="float32",
    silent=True,
    use_2D=True,
)
print(f"FOSCAT device: {scat.backend.device}")
print(f"Config: NORIENT={norient}, KERNELSZ={kernelsz}, target_size={target_size}")

# %% [markdown]
# ## 4. Extract scattering features (per-channel RGB)

# %%
def extract(paths):
    out, kept = [], []
    t0 = time.time()
    for i, p in enumerate(paths):
        try:
            im = (
                Image.open(p)
                .convert("RGB")
                .resize((target_size, target_size))
            )
            arr = np.array(im, dtype=np.float32) / 255.0
        except Exception as e:
            print(f"  skip {p}: {e}")
            continue
        ch_feats = []
        for c in range(3):
            # FOSCAT requires a C-contiguous input; arr[..., c] is a strided
            # view, so force a contiguous copy before eval.
            ch = np.ascontiguousarray(arr[..., c]).reshape(1, target_size, target_size)
            f = scat.eval(ch)
            parts = []
            for attr in ("S0", "S1", "S2", "P00", "P11", "P01"):
                if hasattr(f, attr):
                    parts.append(scat.backend.to_numpy(getattr(f, attr)).ravel())
            ch_feats.append(np.concatenate(parts))
        out.append(np.concatenate(ch_feats))
        kept.append(i)
        if (i + 1) % 100 == 0 or i + 1 == len(paths):
            rate = (i + 1) / max(time.time() - t0, 1e-6)
            eta = (len(paths) - i - 1) / max(rate, 1e-6)
            print(
                f"  {i + 1}/{len(paths)}  {rate:.1f} img/s  ETA {eta / 60:.1f} min"
            )
    return np.array(out), np.array(kept)


X, keep = extract(split_paths_)
y = split_labels[keep] if len(keep) > 0 else split_labels
# Save RELATIVE paths (relative to the image archive root) so downstream
# tools can align outputs across separate Galaxy jobs (each job extracts
# the archive into its own tmp directory, so absolute paths would never
# match across foscat-features and planktonclas-inference).
kept_paths = np.array([split_rel_paths_[i] for i in keep])

print(f"\nFeature matrix: X {X.shape}, y {y.shape}, paths {kept_paths.shape}")

# %% [markdown]
# ## 5. Write output

# %%
features_npz = "features.npz"
np.savez_compressed(features_npz, X=X, y=y, paths=kept_paths)
print(f"Saved {features_npz}")

# Galaxy tool outputs — paths to files written above.
features = features_npz

# output gathering
_galaxy_meta_data = {}
_simple_outs = []
_simple_outs.append(
    (
        "out_foscat_features_features",
        "features_galaxy.output",
        features,
    )
)
_numpy_available = True

for _outn, _outfn, _outv in _simple_outs:
    _galaxy_outfile_name = os.path.join(_galaxy_wd, _outfn)
    if isinstance(_outv, str) and os.path.isfile(_outv):
        shutil.move(_outv, _galaxy_outfile_name)
        _galaxy_meta_data[_outn] = {"ext": "_sniff_"}
    elif _numpy_available and isinstance(_outv, np.ndarray):
        with open(_galaxy_outfile_name, "wb") as fd:
            np.savez(fd, _outv)
        _galaxy_meta_data[_outn] = {"ext": "npz"}
    else:
        with open(_galaxy_outfile_name, "w") as fd:
            json.dump(_outv, fd)
        _galaxy_meta_data[_outn] = {"ext": "expression.json"}

with open(os.path.join(_galaxy_wd, "galaxy.json"), "w") as fd:
    json.dump(_galaxy_meta_data, fd)
print("*** Job finished successfully ***")
