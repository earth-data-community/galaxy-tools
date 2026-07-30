#!/usr/bin/env python

# This script is generated with nb2galaxy

# flake8: noqa

import json
import os
import shutil

# Galaxy tool parameters — Papermill convention with ODA semantic annotations.
# Defaults are placeholders; Galaxy injects real values at runtime.

features_train_npz = "features_train.npz"  # oda:POSIXPath; oda:label "Scattering features (balanced training set) — npz with arrays X (n_samples, n_features) and y (n_samples,) class labels"
features_val_npz = "features_val.npz"  # oda:POSIXPath; oda:label "Scattering features (validation) — npz with X, y, and paths"
features_test_npz = "features_test.npz"  # oda:POSIXPath; oda:label "Scattering features (test) — npz with X, y, and paths"
cnn_val_npz = "cnn_val.npz"  # oda:POSIXPath; oda:label "Deep-model softmax probabilities on val — npz with full_probs (n_samples, n_classes) and paths"
cnn_test_npz = "cnn_test.npz"  # oda:POSIXPath; oda:label "Deep-model softmax probabilities on test — npz with full_probs and paths"
classes_file = "classes.txt"  # oda:POSIXPath; oda:label "Class names, one per line, in label-index order"
train_split_file = "train.txt"  # oda:POSIXPath; oda:label "Training-split file with 'image_path label' lines, used to count per-class training sizes"

C = 1.0  # oda:Float;   oda:label "LogisticRegression regularisation strength (smaller = more regularisation)"
max_iter = (
    2000  # oda:Integer; oda:label "Maximum LogisticRegression iterations"
)
rare_class_threshold = 200  # oda:Integer; oda:label "Train-count threshold below which a class is considered rare (used for mean rare-class recall)"

_galaxy_wd = os.getcwd()

with open("inputs.json", "r") as fd:
    inp_dic = json.load(fd)
if "C_data_product_" in inp_dic.keys():
    inp_pdic = inp_dic["C_data_product_"]
else:
    inp_pdic = inp_dic
features_train_npz = str(inp_pdic["features_train_npz"])
features_val_npz = str(inp_pdic["features_val_npz"])
features_test_npz = str(inp_pdic["features_test_npz"])
cnn_val_npz = str(inp_pdic["cnn_val_npz"])
cnn_test_npz = str(inp_pdic["cnn_test_npz"])
classes_file = str(inp_pdic["classes_file"])
train_split_file = str(inp_pdic["train_split_file"])
C = float(inp_pdic["C"])
max_iter = int(inp_pdic["max_iter"])
rare_class_threshold = int(inp_pdic["rare_class_threshold"])

import json
from collections import defaultdict

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    top_k_accuracy_score,
)
from sklearn.preprocessing import StandardScaler

sc_train = np.load(features_train_npz, allow_pickle=True)
sc_val = np.load(features_val_npz, allow_pickle=True)
sc_test = np.load(features_test_npz, allow_pickle=True)

cnn_val = np.load(cnn_val_npz, allow_pickle=True)
cnn_test = np.load(cnn_test_npz, allow_pickle=True)

with open(classes_file) as f:
    class_names = [ln.strip() for ln in f if ln.strip()]
N_CLASSES = len(class_names)

train_counts = defaultdict(int)
with open(train_split_file) as f:
    for line in f:
        _, lab = line.strip().rsplit(" ", 1)
        train_counts[int(lab)] += 1
rare_idx = np.array(
    [
        i
        for i in range(N_CLASSES)
        if train_counts.get(i, 0) < rare_class_threshold
    ],
    dtype=np.int64,
)
print(f"Rare classes (train < {rare_class_threshold}): {len(rare_idx)}")

scaler = StandardScaler().fit(sc_train["X"])
clf_sc = LogisticRegression(
    max_iter=max(max_iter, 3000),
    C=C,
    solver="lbfgs",
    class_weight="balanced",
    n_jobs=-1,
).fit(scaler.transform(sc_train["X"]), sc_train["y"])

def scatter_probs(X):
    proba = np.zeros((len(X), N_CLASSES), dtype=np.float32)
    sp = clf_sc.predict_proba(scaler.transform(X))
    for j, c in enumerate(clf_sc.classes_):
        proba[:, c] = sp[:, j]
    return proba

proba_sc_val = scatter_probs(sc_val["X"])
proba_sc_test = scatter_probs(sc_test["X"])

def align(scat_paths, cnn_paths, cnn_probs):
    p2i = {p: i for i, p in enumerate(cnn_paths)}
    aligned = np.zeros((len(scat_paths), N_CLASSES), dtype=np.float32)
    hits = 0
    for i, p in enumerate(scat_paths):
        j = p2i.get(p)
        if j is not None:
            aligned[i] = cnn_probs[j]
            hits += 1
    return aligned, hits

val_key = "val_paths" if "val_paths" in cnn_val.files else "paths"
test_key = "test_paths" if "test_paths" in cnn_test.files else "paths"

proba_cnn_val, hv = align(
    sc_val["paths"], cnn_val[val_key], cnn_val["full_probs"].astype(np.float32)
)
proba_cnn_test, ht = align(
    sc_test["paths"],
    cnn_test[test_key],
    cnn_test["full_probs"].astype(np.float32),
)
print(
    f'Aligned CNN val: {hv}/{len(sc_val["paths"])}  test: {ht}/{len(sc_test["paths"])}'
)

y_val = sc_val["y"]
y_test = sc_test["y"]

meta_val = np.concatenate([proba_cnn_val, proba_sc_val], axis=1).astype(
    np.float32
)
meta_test = np.concatenate([proba_cnn_test, proba_sc_test], axis=1).astype(
    np.float32
)

print("Training stacking LR on val...")
meta_clf = LogisticRegression(
    max_iter=max_iter,
    C=C,
    solver="lbfgs",
    class_weight="balanced",
    n_jobs=-1,
).fit(meta_val, y_val)

proba_stack = np.zeros_like(proba_cnn_test)
sp = meta_clf.predict_proba(meta_test)
for j, c in enumerate(meta_clf.classes_):
    proba_stack[:, c] = sp[:, j]

def metrics(probs):
    pred = probs.argmax(axis=1)
    top1 = accuracy_score(y_test, pred)
    top5 = top_k_accuracy_score(
        y_test, probs, k=5, labels=np.arange(N_CLASSES)
    )
    _, rec, _, _ = precision_recall_fscore_support(
        y_test, pred, labels=np.arange(N_CLASSES), zero_division=0
    )
    return top1, top5, rec, pred

t1_cnn, t5_cnn, rec_cnn, _ = metrics(proba_cnn_test)
t1_sc, t5_sc, rec_sc, _ = metrics(proba_sc_test)
t1_e, t5_e, rec_e, _ = metrics(0.5 * proba_cnn_test + 0.5 * proba_sc_test)
t1_s, t5_s, rec_s, _ = metrics(proba_stack)

cnn_pred = proba_cnn_test.argmax(1)
sc_pred = proba_sc_test.argmax(1)
cnn_right = cnn_pred == y_test
sc_right = sc_pred == y_test
oracle = np.where(cnn_right, cnn_pred, np.where(sc_right, sc_pred, cnn_pred))
t1_o = accuracy_score(y_test, oracle)
_, rec_o, _, _ = precision_recall_fscore_support(
    y_test, oracle, labels=np.arange(N_CLASSES), zero_division=0
)

print("\n=== Final results on held-out test ===")
print(f'{"method":<35} {"top-1":>8} {"top-5":>8} {"rare recall":>13}')
for name, t1, t5, rec in [
    ("Deep model alone", t1_cnn, t5_cnn, rec_cnn),
    ("Scattering + LR alone", t1_sc, t5_sc, rec_sc),
    ("50/50 probability ensemble", t1_e, t5_e, rec_e),
    ("Stacked LR (val-trained)", t1_s, t5_s, rec_s),
]:
    print(f"  {name:<33} {t1:>8.4f} {t5:>8.4f} {rec[rare_idx].mean():>13.3f}")
print(
    f'  {"Oracle ceiling":<33} {t1_o:>8.4f}               {rec_o[rare_idx].mean():>13.3f}'
)

deltas = rec_s - rec_cnn
n_better = int((deltas > 0.01).sum())
n_worse = int((deltas < -0.01).sum())
print(
    f"\nStacked vs deep model across {N_CLASSES} classes: {n_better} better, {n_worse} worse"
)

out = {
    "cnn": {
        "top1": float(t1_cnn),
        "top5": float(t5_cnn),
        "rare_recall": float(rec_cnn[rare_idx].mean()),
    },
    "scattering": {
        "top1": float(t1_sc),
        "top5": float(t5_sc),
        "rare_recall": float(rec_sc[rare_idx].mean()),
    },
    "ens_50_50": {
        "top1": float(t1_e),
        "top5": float(t5_e),
        "rare_recall": float(rec_e[rare_idx].mean()),
    },
    "stacked_val": {
        "top1": float(t1_s),
        "top5": float(t5_s),
        "rare_recall": float(rec_s[rare_idx].mean()),
    },
    "oracle": {
        "top1": float(t1_o),
        "rare_recall": float(rec_o[rare_idx].mean()),
    },
    "per_rare_class": {
        class_names[i]: {
            "train_count": int(train_counts.get(i, 0)),
            "cnn": float(rec_cnn[i]),
            "ens_50_50": float(rec_e[i]),
            "stacked_val": float(rec_s[i]),
            "oracle": float(rec_o[i]),
        }
        for i in rare_idx
    },
    "all_classes_delta_stack_vs_cnn": {
        class_names[i]: {
            "cnn": float(rec_cnn[i]),
            "stacked_val": float(rec_s[i]),
            "delta": float(rec_s[i] - rec_cnn[i]),
        }
        for i in range(N_CLASSES)
    },
    "n_classes_better_stacked": n_better,
    "n_classes_worse_stacked": n_worse,
    "parameters": {
        "C": float(C),
        "max_iter": int(max_iter),
        "rare_class_threshold": int(rare_class_threshold),
    },
}

with open("stacking_results.json", "w") as f:
    json.dump(out, f, indent=2)

joblib.dump(
    {
        "scaler": scaler,
        "clf_sc": clf_sc,
        "meta_clf": meta_clf,
        "class_names": class_names,
        "rare_idx": rare_idx.tolist(),
    },
    "stacking_model.joblib",
)

print("Saved stacking_results.json and stacking_model.joblib")

# Galaxy tool outputs — paths to files written above.
results_json = "stacking_results.json"
stacking_model = "stacking_model.joblib"

# output gathering
_galaxy_meta_data = {}
_simple_outs = []
_simple_outs.append(
    (
        "out_scattering_stacking_results_json",
        "results_json_galaxy.output",
        results_json,
    )
)
_simple_outs.append(
    (
        "out_scattering_stacking_stacking_model",
        "stacking_model_galaxy.output",
        stacking_model,
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
