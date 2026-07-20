"""Train the L-PROBE logistic-regression probes.

Input: latent/probe/captures/*.npz (from capture.py, TRAINING instances only
— repos disjoint from the 30 pilot repos; enforced here against
pilot_candidates.json, non-negotiable per LITREVIEW).
Per label, per layer: standardized logistic regression, GroupKFold by repo
(the honest val number), then a final fit on all training data.

Output: latent/probe/probes.json
  {label: {layer, coef, intercept, mu, sd, cv_acc, cv_auc, base_rate, n}}
plus a "shuffled" twin (coef randomly permuted, fixed seed) for the
lprobe_shuffled control.

Run (piranha or laptop — pure sklearn/numpy):
  python -m latent.probe.train
"""
import argparse
import glob
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CAPTURES = os.path.join(HERE, "captures")
OUT = os.path.join(HERE, "probes.json")

# per-turn labels use every captured position; final labels use the last one
PER_TURN = ["located_file", "seen_func"]
FINAL = ["solved"]


def pilot_repos():
    with open(os.path.join(ROOT, "pilot_candidates.json")) as f:
        return {c["instance_id"].split("_callee")[0] for c in json.load(f)}


def load_captures():
    rows = []
    for f in sorted(glob.glob(os.path.join(CAPTURES, "*.npz"))):
        z = np.load(f, allow_pickle=True)
        meta = json.loads(str(z["meta"]))
        rows.append((meta, {k: z[k] for k in z.files if k.startswith("h_")}))
    return rows


def build_xy(rows, label, layer):
    X, y, groups = [], [], []
    key = f"h_{layer}"
    for meta, h in rows:
        if key not in h:
            continue
        H = h[key]
        if label in PER_TURN:
            for i, tl in enumerate(meta["turn_labels"][:len(H)]):
                X.append(H[i])
                y.append(bool(tl[label]))
                groups.append(meta["repo"])
        else:
            X.append(H[-1])
            y.append(bool(meta["final_labels"][label]))
            groups.append(meta["repo"])
    return np.array(X), np.array(y, dtype=int), np.array(groups)


def cv_probe(X, y, groups, C=0.05, seed=0):
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupKFold
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Xs = (X - mu) / sd
    n_groups = len(set(groups.tolist()))
    accs, aucs = [], []
    if n_groups >= 3 and len(set(y.tolist())) > 1:
        gkf = GroupKFold(n_splits=min(5, n_groups))
        for tr, te in gkf.split(Xs, y, groups):
            if len(set(y[tr].tolist())) < 2 or len(set(y[te].tolist())) < 2:
                continue
            clf = LogisticRegression(C=C, max_iter=2000, random_state=seed)
            clf.fit(Xs[tr], y[tr])
            p = clf.predict_proba(Xs[te])[:, 1]
            accs.append(float(((p > .5).astype(int) == y[te]).mean()))
            aucs.append(float(roc_auc_score(y[te], p)))
    clf = LogisticRegression(C=C, max_iter=2000, random_state=seed)
    clf.fit(Xs, y)
    return {
        "coef": clf.coef_[0].tolist(), "intercept": float(clf.intercept_[0]),
        "mu": mu.tolist(), "sd": sd.tolist(),
        "cv_acc": round(float(np.mean(accs)), 3) if accs else None,
        "cv_auc": round(float(np.mean(aucs)), 3) if aucs else None,
        "base_rate": round(float(y.mean()), 3), "n": int(len(y)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layers", default="20,26,32")
    ap.add_argument("--C", type=float, default=0.05)
    args = ap.parse_args()
    layers = [int(x) for x in args.layers.split(",")]

    rows = load_captures()
    if not rows:
        raise SystemExit("no captures found — run capture.py first")
    banned = pilot_repos()
    leak = [m["repo"] for m, _ in rows if m["repo"] in banned]
    if leak:
        raise SystemExit(f"TRAINING LEAK: pilot repos in captures: {sorted(set(leak))}")
    print(f"{len(rows)} training instances, repos: "
          f"{sorted({m['repo'] for m, _ in rows})}")

    probes = {}
    for label in PER_TURN + FINAL:
        best = None
        for layer in layers:
            X, y, g = build_xy(rows, label, layer)
            if len(X) == 0 or len(set(y.tolist())) < 2:
                print(f"  {label}@L{layer}: degenerate (n={len(X)}, "
                      f"rate={y.mean() if len(y) else 'na'})")
                continue
            r = cv_probe(X, y, g, C=args.C)
            print(f"  {label}@L{layer}: n={r['n']} base={r['base_rate']} "
                  f"cv_acc={r['cv_acc']} cv_auc={r['cv_auc']}")
            if best is None or (r["cv_auc"] or 0) > (best[1]["cv_auc"] or 0):
                best = (layer, r)
        if best:
            layer, r = best
            probes[label] = {"layer": layer, **r}
    # shuffled twin: permute each coef vector (destroys the direction, keeps
    # the norm/scale) — the lprobe_shuffled control
    rng = np.random.RandomState(0)
    shuffled = {}
    for label, p in probes.items():
        q = dict(p)
        q["coef"] = rng.permutation(np.array(p["coef"])).tolist()
        shuffled[label] = q
    with open(OUT, "w") as f:
        json.dump({"probes": probes, "shuffled": shuffled,
                   "layers_swept": layers}, f)
    print(f"wrote {OUT}: labels={list(probes)}")


if __name__ == "__main__":
    main()
