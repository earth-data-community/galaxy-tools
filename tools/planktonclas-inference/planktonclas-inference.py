#!/usr/bin/env python

# This script is generated with nb2galaxy and hand-corrected.

# flake8: noqa

import json
import os
import shutil

# Galaxy tool parameters — Papermill convention with ODA semantic annotations.
# Defaults are placeholders; Galaxy injects real values at runtime.

model_archive = "model.tar.gz"  # oda:POSIXPath; oda:label "planktonclas-format model archive (.tar.gz with ckpts/final_model.h5, conf.json, dataset_files/classes.txt)"
images_archive = "images.zip"  # oda:POSIXPath; oda:label "Image archive (.zip), images referenced by relative path in the split file"
split_file = "split.txt"  # oda:POSIXPath; oda:label "Split file with one 'image_path label' per line; image_path is relative to the image archive root"

top_K = 0  # oda:Integer; oda:label "Top-K predictions to keep in full_probs (0 = full softmax = num_classes; matches FIESTA-bio canonical NPZ schema)"
crop_num = 10  # oda:Integer; oda:label "Number of TTA crops (10 matches Decrop's canonical pipeline; set to 1 to disable TTA)"

_galaxy_wd = os.getcwd()

with open("inputs.json", "r") as fd:
    inp_dic = json.load(fd)
if "C_data_product_" in inp_dic.keys():
    inp_pdic = inp_dic["C_data_product_"]
else:
    inp_pdic = inp_dic
model_archive = str(inp_pdic["model_archive"])
images_archive = str(inp_pdic["images_archive"])
split_file = str(inp_pdic["split_file"])
top_K = int(inp_pdic["top_K"])
crop_num = int(inp_pdic["crop_num"])

import tarfile
import zipfile
from pathlib import Path

import numpy as np

work = Path.cwd()

model_root = work / "_model"
if model_root.exists():
    shutil.rmtree(model_root)
model_root.mkdir()
with tarfile.open(model_archive, "r:*") as tf:
    tf.extractall(model_root)

# planktonclas archives may have a single top-level directory; resolve it
candidates = [
    p for p in model_root.iterdir() if p.is_dir() and (p / "ckpts").exists()
]
if candidates:
    model_dir = candidates[0]
elif (model_root / "ckpts").exists():
    model_dir = model_root
else:
    raise FileNotFoundError(
        f"No 'ckpts/' directory found in model archive. Contents: "
        f"{[p.name for p in model_root.rglob('*')][:20]}"
    )

print(f"Model directory: {model_dir}")

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

with open(model_dir / "conf.json") as f:
    conf = json.load(f)
N_CLASSES = conf["model"]["num_classes"]
print(
    f"num_classes: {N_CLASSES}, image_size: {conf['model']['image_size']}, "
    f"preprocess_mode: {conf['model']['preprocess_mode']}"
)

with open(model_dir / "dataset_files" / "classes.txt") as f:
    class_names = [ln.strip() for ln in f if ln.strip()]
assert (
    len(class_names) == N_CLASSES
), f"classes.txt has {len(class_names)} entries but conf.json says num_classes={N_CLASSES}"

from planktonclas import utils
from planktonclas.test_utils import predict
from tensorflow.keras.models import load_model

ckpt = model_dir / "ckpts" / "final_model.h5"
model = load_model(str(ckpt), custom_objects=utils.get_custom_objects())
print(f"Model loaded: input {model.input_shape}, output {model.output_shape}")

split_paths_, split_labels_ = [], []
missing = 0
with open(split_file) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rel, lab = line.rsplit(" ", 1)
        full = images_root / rel
        if not full.exists():
            # second-chance: try as absolute path
            cand = Path(rel)
            if cand.is_absolute() and cand.exists():
                full = cand
            else:
                missing += 1
                continue
        split_paths_.append(str(full))
        split_labels_.append(int(lab))
split_labels = np.array(split_labels_, dtype=np.int64)
print(
    f"Resolved {len(split_paths_)} images from split file ({missing} missing)"
)
assert (
    len(split_paths_) > 0
), "No images resolved from split file — check the image archive layout."

top_K_actual = top_K if top_K > 0 else N_CLASSES
print(
    f"Inference: top_K={top_K_actual}, crop_num={crop_num}, N={len(split_paths_)}"
)

pred_lab, pred_prob = predict(
    model,
    split_paths_,
    conf,
    top_K=top_K_actual,
    crop_num=crop_num,
    filemode="local",
)

N = len(split_paths_)
if top_K_actual >= N_CLASSES:
    # Reconstruct dense (N, N_CLASSES) softmax — matches FIESTA-bio cnn_predictions_*.npz
    full_probs = np.zeros((N, N_CLASSES), dtype=np.float32)
    for i in range(N):
        full_probs[i, pred_lab[i]] = pred_prob[i]
else:
    # Top-K only — store sparse (lab, prob) arrays directly
    full_probs = pred_prob.astype(np.float32)

y_pred_top1 = pred_lab[:, 0].astype(np.int64)

predictions_npz = "predictions.npz"
np.savez_compressed(
    predictions_npz,
    y_true=split_labels,
    y_pred=y_pred_top1,
    full_probs=full_probs.astype(np.float16),
    paths=np.array(split_paths_),
)
print(
    f"Saved {predictions_npz} — shapes: full_probs {full_probs.shape}, paths {N}"
)

# Galaxy tool outputs — paths to files written above.
predictions = predictions_npz

# output gathering
_galaxy_meta_data = {}
_simple_outs = []
_simple_outs.append(
    (
        "out_planktonclas_inference_predictions",
        "predictions_galaxy.output",
        predictions,
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
