"""Circle-packing grader (n=26, unit square, maximize sum of radii).

Task and scoring follow the circle-packing benchmark used in the CORAL paper's
math-optimization suite (arXiv 2604.01658, after AlphaEvolve / SkyDiscover;
best known sum of radii 2.6359). Grader implementation written for mini-CORAL.

Contract (mini-CORAL GraderRunner):
    python grader.py --code-dir <dir> [--args '<json>']
Runs the agent's program (args.program_file, default initial_program.py) in a
subprocess inside <dir> with its own timeout. The program must print to stdout
a JSON list of n_circles [x, y, r] triples for circles inside the unit square.

Prints exactly one JSON object to stdout: {"score": float|null, "feedback": str}.
score is null when the program crashed, timed out, or produced an invalid
packing (boundary or pairwise-overlap violation beyond 1e-6).
"""

import argparse
import json
import math
import subprocess
import sys

TOL = 1e-6


def parse_circles(stdout: str, n: int):
    """Parse program stdout into n (x, y, r) triples. Raises ValueError."""
    data = None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        for line in reversed(stdout.strip().splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    if data is None:
        raise ValueError("no JSON found in program output")
    if isinstance(data, dict) and "circles" in data:
        data = data["circles"]
    if not isinstance(data, list) or len(data) != n:
        got = len(data) if isinstance(data, list) else type(data).__name__
        raise ValueError(f"expected a JSON list of {n} [x, y, r] triples, got {got}")
    circles = []
    for i, row in enumerate(data):
        if not isinstance(row, (list, tuple)) or len(row) != 3:
            raise ValueError(f"circle {i} is not an [x, y, r] triple")
        x, y, r = (float(v) for v in row)
        if not all(math.isfinite(v) for v in (x, y, r)):
            raise ValueError(f"circle {i} has non-finite values")
        circles.append((x, y, r))
    return circles


def validate(circles):
    """Return a list of violation strings (empty if the packing is valid)."""
    violations = []
    for i, (x, y, r) in enumerate(circles):
        if r <= 0:
            violations.append(f"circle {i}: non-positive radius r={r:.6g}")
        if x - r < -TOL or x + r > 1 + TOL or y - r < -TOL or y + r > 1 + TOL:
            violations.append(
                f"circle {i}: outside unit square (x={x:.6g}, y={y:.6g}, r={r:.6g})"
            )
    for i in range(len(circles)):
        xi, yi, ri = circles[i]
        for j in range(i + 1, len(circles)):
            xj, yj, rj = circles[j]
            dist = math.hypot(xi - xj, yi - yj)
            if dist < ri + rj - TOL:
                violations.append(
                    f"circles {i},{j}: overlap (dist={dist:.6g} < r{i}+r{j}={ri + rj:.6g})"
                )
    return violations


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code-dir", required=True)
    ap.add_argument("--args", default="{}")
    ns = ap.parse_args()
    args = json.loads(ns.args)

    program_file = args.get("program_file", "initial_program.py")
    program_timeout = float(args.get("program_timeout", 120))
    n = int(args.get("n_circles", 26))
    sota = float(args.get("sota", 2.6359))

    def emit(score, feedback):
        print(json.dumps({"score": score, "feedback": feedback}))
        sys.exit(0)

    try:
        proc = subprocess.run(
            [sys.executable, program_file],
            cwd=ns.code_dir,
            capture_output=True,
            text=True,
            timeout=program_timeout,
        )
    except subprocess.TimeoutExpired:
        emit(None, f"program exceeded its {program_timeout:.0f}s time limit")
    if proc.returncode != 0:
        tail = proc.stderr.strip().splitlines()[-10:]
        emit(None, "program exited with code "
             f"{proc.returncode}:\n" + "\n".join(tail))

    try:
        circles = parse_circles(proc.stdout, n)
    except ValueError as e:
        emit(None, f"invalid output: {e}")

    violations = validate(circles)
    if violations:
        shown = violations[:10]
        more = f" (+{len(violations) - 10} more)" if len(violations) > 10 else ""
        emit(None, f"invalid packing ({len(violations)} violations):\n"
             + "\n".join(shown) + more)

    score = sum(r for _, _, r in circles)
    emit(score, f"valid packing of {n} circles | sum of radii = {score:.6f} | "
         f"best known = {sota:.4f} | gap = {sota - score:+.6f}")


if __name__ == "__main__":
    main()
