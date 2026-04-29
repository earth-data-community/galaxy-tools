#!/usr/bin/env python

# This script is generated with nb2galaxy and hand-corrected.

# flake8: noqa

import json
import os
import shutil

# Galaxy tool parameters — Papermill convention with ODA semantic annotations.
# Defaults are placeholders; Galaxy injects real values at runtime.

target_map = "target.npy"  # oda:POSIXPath; oda:label "Target reference map (.npy, 1D HEALPix array of length 12*nside^2). The synthesis will match this map's scattering statistics."
starting_map = ""  # oda:POSIXPath; oda:label "Optional starting map (.npy, same shape as target). Leave empty to generate random noise scaled to target's mean/std."
eval_mask = ""  # oda:POSIXPath; oda:label "Optional evaluation mask (.npy, same shape as target). Restricts where the scattering statistics are computed (e.g. ocean-only). Leave empty to use all pixels."
update_mask = ""  # oda:POSIXPath; oda:label "Optional update mask (.npy, same shape as target). Restricts which pixels the synthesis updates (e.g. cloudy regions only — for gap-filling). Leave empty to update all pixels."

norient = 4  # oda:Integer; oda:label "Number of orientations for the scattering transform (FOSCAT NORIENT)"
kernelsz = 3  # oda:Integer; oda:label "Kernel size for the scattering transform (FOSCAT KERNELSZ)"
nsteps = 300  # oda:Integer; oda:label "Number of synthesis iterations (NUM_EPOCHS in FOSCAT)"
seed = 1234  # oda:Integer; oda:label "Random seed for the starting noise (used only when starting_map is empty)"

_galaxy_wd = os.getcwd()

with open("inputs.json", "r") as fd:
    inp_dic = json.load(fd)
if "C_data_product_" in inp_dic.keys():
    inp_pdic = inp_dic["C_data_product_"]
else:
    inp_pdic = inp_dic
target_map = str(inp_pdic["target_map"])
starting_map = str(inp_pdic.get("starting_map", "") or "")
eval_mask = str(inp_pdic.get("eval_mask", "") or "")
update_mask = str(inp_pdic.get("update_mask", "") or "")
norient = int(inp_pdic["norient"])
kernelsz = int(inp_pdic["kernelsz"])
nsteps = int(inp_pdic["nsteps"])
seed = int(inp_pdic["seed"])

# Avoid macOS / Linux libomp duplicate-symbol issues seen with FOSCAT
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import time
from pathlib import Path

import numpy as np

work = Path.cwd()

# %% [markdown]
# ## 1. Load target map and optional inputs

# %%
target = np.load(target_map).astype(np.float32)
if target.ndim == 1:
    target = target.reshape(1, target.shape[0])
elif target.ndim != 2:
    raise ValueError(
        f"Expected 1D or 2D target array; got shape {target.shape}"
    )
print(
    f"Target: shape {target.shape}, range [{target.min():.4f}, {target.max():.4f}]"
)
print(f"  mean={target.mean():.4f}, std={target.std():.4f}")

if starting_map and Path(starting_map).is_file() and Path(starting_map).stat().st_size > 0:
    start = np.load(starting_map).astype(np.float32)
    if start.shape != target.shape:
        start = start.reshape(target.shape)
    print(f"Starting map (provided): shape {start.shape}")
else:
    rng = np.random.default_rng(seed)
    start = rng.standard_normal(size=target.shape).astype(np.float32)
    start = start * float(target.std()) + float(target.mean())
    print(
        f"Starting map (random, seed={seed}): "
        f"shape {start.shape}, mean={start.mean():.4f}, std={start.std():.4f}"
    )


def _load_mask_or_none(path_arg, target_shape):
    if not path_arg:
        return None
    p = Path(path_arg)
    if not p.is_file() or p.stat().st_size == 0:
        return None
    m = np.load(path_arg).astype(np.float32)
    if m.shape != target_shape:
        m = m.reshape(target_shape)
    return m


eval_mask_arr = _load_mask_or_none(eval_mask, target.shape)
update_mask_arr = _load_mask_or_none(update_mask, target.shape)

print(
    f"Eval mask: {'provided' if eval_mask_arr is not None else 'all pixels'}, "
    f"Update mask: {'provided' if update_mask_arr is not None else 'all pixels'}"
)

# %% [markdown]
# ## 2. Initialize FOSCAT

# %%
import foscat.scat_cov as sc
import foscat.Synthesis as synthe

scat = sc.funct(
    NORIENT=norient,
    KERNELSZ=kernelsz,
    all_type="float32",
    silent=True,
)
print(f"FOSCAT device: {scat.backend.device}")
print(f"Config: NORIENT={norient}, KERNELSZ={kernelsz}, NSTEPS={nsteps}")

# %% [markdown]
# ## 3. Compute reference scattering coefficients

# %%
if eval_mask_arr is not None:
    ref, sref = scat.eval(target, mask=eval_mask_arr, calc_var=True)
else:
    ref, sref = scat.eval(target, calc_var=True)
print("Reference scattering coefficients computed")

# %% [markdown]
# ## 4. Set up loss and synthesis

# %%
def the_loss(x, scat_operator, args):
    ref_a, mask_a, sref_a = args[0], args[1], args[2]
    if mask_a is None:
        learn = scat_operator.eval(x)
    else:
        learn = scat_operator.eval(x, mask=mask_a)
    diff = (ref_a - learn) / sref_a
    return scat_operator.reduce_mean(scat_operator.square(diff))


if eval_mask_arr is not None:
    mask_const = scat.backend.constant(scat.backend.bk_cast(eval_mask_arr))
else:
    mask_const = None

loss = synthe.Loss(the_loss, scat, ref, mask_const, sref)
sy = synthe.Synthesis([loss])

# %% [markdown]
# ## 5. Run synthesis

# %%
print(f"Running synthesis: {nsteps} steps...")
t0 = time.time()

run_kwargs = {
    "EVAL_FREQUENCY": max(nsteps // 10, 1),
    "NUM_EPOCHS": nsteps,
    "do_lbfgs": True,
}
if update_mask_arr is not None:
    run_kwargs["grd_mask"] = scat.backend.bk_cast(update_mask_arr)

omap = sy.run(scat.backend.bk_cast(start), **run_kwargs)
elapsed = time.time() - t0

omap_np = np.array(omap) if not hasattr(omap, "numpy") else omap.numpy()
print(f"Synthesis complete in {elapsed:.1f}s")

# %% [markdown]
# ## 6. Validation summary

# %%
out_scat = (
    scat.eval(omap_np, mask=eval_mask_arr)
    if eval_mask_arr is not None
    else scat.eval(omap_np)
)
ref_s1 = scat.backend.to_numpy(ref.S1)
out_s1 = scat.backend.to_numpy(out_scat.S1)
start_scat = (
    scat.eval(start, mask=eval_mask_arr)
    if eval_mask_arr is not None
    else scat.eval(start)
)
start_s1 = scat.backend.to_numpy(start_scat.S1)

scat_error_start = float(np.mean((ref_s1 - start_s1) ** 2))
scat_error_out = float(np.mean((ref_s1 - out_s1) ** 2))
improvement_pct = (
    (1.0 - scat_error_out / scat_error_start) * 100.0
    if scat_error_start > 0
    else 0.0
)

print("=== Validation ===")
print(f"  Target mean / std       : {target.mean():.4f} / {target.std():.4f}")
print(f"  Synth  mean / std       : {omap_np.mean():.4f} / {omap_np.std():.4f}")
print(f"  Scat coeff err (start)  : {scat_error_start:.6f}")
print(f"  Scat coeff err (synth)  : {scat_error_out:.6f}")
print(f"  Improvement             : {improvement_pct:.1f}%")

# %% [markdown]
# ## 7. Write outputs

# %%
synthesis_npy = "synthesis.npy"
np.save(synthesis_npy, omap_np)

results = {
    "norient": int(norient),
    "kernelsz": int(kernelsz),
    "nsteps": int(nsteps),
    "seed": int(seed),
    "target_shape": list(target.shape),
    "elapsed_s": float(elapsed),
    "device": str(scat.backend.device),
    "target_mean": float(target.mean()),
    "target_std": float(target.std()),
    "synth_mean": float(omap_np.mean()),
    "synth_std": float(omap_np.std()),
    "scat_error_start": scat_error_start,
    "scat_error_synth": scat_error_out,
    "scat_improvement_pct": float(improvement_pct),
    "used_eval_mask": eval_mask_arr is not None,
    "used_update_mask": update_mask_arr is not None,
    "used_provided_starting_map": bool(starting_map and Path(starting_map).is_file()),
}

results_json = "synthesis_results.json"
with open(results_json, "w") as f:
    json.dump(results, f, indent=2)

print(f"Saved {synthesis_npy} and {results_json}")

# Galaxy tool outputs — paths to files written above.
synthesis = synthesis_npy
results_out = results_json

# output gathering
_galaxy_meta_data = {}
_simple_outs = []
_simple_outs.append(
    (
        "out_foscat_synthesis_synthesis",
        "synthesis_galaxy.output",
        synthesis,
    )
)
_simple_outs.append(
    (
        "out_foscat_synthesis_results",
        "results_galaxy.output",
        results_out,
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
