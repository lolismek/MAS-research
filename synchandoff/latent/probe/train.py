"""Train the v2 belief-STRENGTH probe (single task-agnostic conviction probe).

v2 (PLAN_V2 + 2026-07-20 simplification directive): ONE logistic-regression
probe on residual-stream activations answering "does the author currently
hold a strong belief about what is happening?", trained on the diverse
synthetic pool (gen_data.py -> capture_synth.py). The v1 content-probes
(located_file/seen_func/solved) are dropped; see git history.

Validation: GroupKFold with DOMAIN as the group (held-out-domain accuracy —
the honest generalization number; gate >= 0.75 per PLAN_V2). Layer picked by
val accuracy. Also reported, never trained on: pearson correlation of probe
score with next-token entropy at the snippet's last position.

Output: latent/probe/probes.json
  {"belief_strength": {layer, coef, intercept, mu, sd, val_acc, val_auc,
                       val_acc_by_domain, entropy_corr, base_rate, n},
   "shuffled": {...same with permuted coef...}}

Run (piranha): /tmp/aij2115/pyenv/bin/python -m latent.probe.train
"""
import argparse
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.join(HERE, "synth_captures.npz")
OUT = os.path.join(HERE, "probes.json")


def fit_layer(X, y, groups, ent, C=0.05, seed=0):
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupKFold
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Xs = (X - mu) / sd
    doms = sorted(set(groups.tolist()))
    accs, aucs, by_dom = [], [], {}
    gkf = GroupKFold(n_splits=min(5, len(doms)))
    for tr, te in gkf.split(Xs, y, groups):
        clf = LogisticRegression(C=C, max_iter=2000, random_state=seed)
        clf.fit(Xs[tr], y[tr])
        p = clf.predict_proba(Xs[te])[:, 1]
        acc = float(((p > .5).astype(int) == y[te]).mean())
        accs.append(acc)
        aucs.append(float(roc_auc_score(y[te], p)))
        for d in sorted(set(groups[te].tolist())):
            m = groups[te] == d
            by_dom[str(d)] = round(float(
                ((p[m] > .5).astype(int) == y[te][m]).mean()), 3)
    clf = LogisticRegression(C=C, max_iter=2000, random_state=seed)
    clf.fit(Xs, y)
    score = clf.predict_proba(Xs)[:, 1]
    ok = ent > 0
    ecorr = float(np.corrcoef(score[ok], ent[ok])[0, 1]) if ok.sum() > 10 else None
    return {
        "coef": clf.coef_[0].tolist(), "intercept": float(clf.intercept_[0]),
        "mu": mu.tolist(), "sd": sd.tolist(),
        "val_acc": round(float(np.mean(accs)), 3),
        "val_auc": round(float(np.mean(aucs)), 3),
        "val_acc_by_domain": by_dom,
        "entropy_corr": round(ecorr, 3) if ecorr is not None else None,
        "base_rate": round(float(y.mean()), 3), "n": int(len(y)), "C": C,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--C", type=float, default=0.05)
    args = ap.parse_args()

    z = np.load(CAP, allow_pickle=True)
    y = z["y"].astype(int)
    groups = z["domain"].astype(str)
    ent = z["entropy"].astype(np.float32)
    layers = sorted(int(k.split("_")[1]) for k in z.files if k.startswith("X_"))
    print(f"{len(y)} samples, base_rate={y.mean():.3f}, "
          f"domains={sorted(set(groups.tolist()))}, layers={layers}")

    best = None
    results = {}
    for lay in layers:
        X = z[f"X_{lay}"].astype(np.float32)
        r = fit_layer(X, y, groups, ent, C=args.C)
        results[lay] = r
        print(f"  L{lay}: val_acc={r['val_acc']} val_auc={r['val_auc']} "
              f"entropy_corr={r['entropy_corr']} by_domain={r['val_acc_by_domain']}")
        if best is None or r["val_acc"] > results[best]["val_acc"]:
            best = lay

    probe = {"layer": best, **results[best]}
    rng = np.random.RandomState(0)
    shuffled = dict(probe)
    shuffled["coef"] = rng.permutation(np.array(probe["coef"])).tolist()
    with open(OUT, "w") as f:
        json.dump({"belief_strength": probe, "shuffled": shuffled,
                   "layers_swept": {str(k): {"val_acc": v["val_acc"],
                                             "val_auc": v["val_auc"]}
                                    for k, v in results.items()}}, f)
    gate = "PASS" if probe["val_acc"] >= 0.75 else "FAIL"
    print(f"picked layer {best}: val_acc={probe['val_acc']} "
          f"(gate>=0.75: {gate}); wrote {OUT}")


if __name__ == "__main__":
    main()
