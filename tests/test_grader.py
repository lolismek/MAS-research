"""M0 gate: circle-packing grader + GraderRunner (accept / reject @1e-6 / timeout)."""

import json
import shutil
import textwrap

import pytest

from minicoral.grader import GraderRunner


def write_program(code_dir, circles=None, body=None):
    code_dir.mkdir(parents=True, exist_ok=True)
    if body is None:
        body = f"import json; print(json.dumps({json.dumps(circles)}))"
    (code_dir / "initial_program.py").write_text(body)


def runner(grader_path, timeout=30.0, **args):
    base = {"program_file": "initial_program.py", "program_timeout": 10,
            "n_circles": 26, "sota": 2.6359}
    base.update(args)
    return GraderRunner(grader_path, timeout=timeout, args=base)


def grid_circles(n=26, cols=6, rows=5, r=1 / 12):
    out = []
    for j in range(rows):
        for i in range(cols):
            if len(out) == n:
                return out
            out.append([(2 * i + 1) / (2 * cols), (2 * j + 1) / (2 * rows), r])
    return out


async def test_seed_is_valid(grader_path, seed_dir, tmp_path):
    code_dir = tmp_path / "code"
    shutil.copytree(seed_dir, code_dir)
    res = await runner(grader_path).grade(code_dir)
    assert not res.crashed and not res.timed_out
    assert res.score == pytest.approx(26 / 12)
    assert "gap" in res.feedback


async def test_valid_packing_scores_sum_of_radii(grader_path, tmp_path):
    circles = grid_circles()
    write_program(tmp_path / "c", circles)
    res = await runner(grader_path).grade(tmp_path / "c")
    assert res.score == pytest.approx(sum(c[2] for c in circles))


async def test_boundary_violation_rejected(grader_path, tmp_path):
    circles = grid_circles()
    circles[0] = [0.05, 0.5, 0.05 + 5e-6]  # pokes 5e-6 outside x=0 (> 1e-6 tol)
    write_program(tmp_path / "c", circles)
    res = await runner(grader_path).grade(tmp_path / "c")
    assert res.score is None and res.crashed
    assert "outside unit square" in res.feedback


async def test_boundary_within_tolerance_accepted(grader_path, tmp_path):
    circles = grid_circles()
    circles[0] = [1 / 12 - 5e-7, circles[0][1], 1 / 12]  # 5e-7 outside: within tol
    write_program(tmp_path / "c", circles)
    res = await runner(grader_path).grade(tmp_path / "c")
    assert res.score is not None


async def test_overlap_rejected_at_tolerance(grader_path, tmp_path):
    # Two circles whose gap deficit is 5e-6 (> 1e-6 tol) overlap; 5e-7 passes.
    def with_pair(deficit):
        circles = grid_circles(n=24)
        for c in circles:
            c[2] = 0.04  # shrink the grid so our pair dominates the geometry
        circles.append([0.25, 0.95, 0.04])
        circles.append([0.25 + 0.08 - deficit, 0.95, 0.04])
        return circles

    write_program(tmp_path / "bad", with_pair(5e-6))
    res = await runner(grader_path).grade(tmp_path / "bad")
    assert res.score is None and "overlap" in res.feedback

    write_program(tmp_path / "ok", with_pair(5e-7))
    res = await runner(grader_path).grade(tmp_path / "ok")
    assert res.score is not None


async def test_wrong_count_rejected(grader_path, tmp_path):
    write_program(tmp_path / "c", grid_circles(n=25))
    res = await runner(grader_path).grade(tmp_path / "c")
    assert res.score is None and "26" in res.feedback


async def test_program_crash_reported(grader_path, tmp_path):
    write_program(tmp_path / "c", body="raise RuntimeError('boom')")
    res = await runner(grader_path).grade(tmp_path / "c")
    assert res.score is None and res.crashed
    assert "boom" in res.feedback


async def test_program_timeout(grader_path, tmp_path):
    write_program(tmp_path / "c", body="import time; time.sleep(60)")
    res = await runner(grader_path, program_timeout=1).grade(tmp_path / "c")
    assert res.score is None and res.crashed
    assert "time limit" in res.feedback


async def test_grader_hard_timeout_kills_sleeper(tmp_path):
    # A grader that hangs must be SIGKILLed by GraderRunner's hard timeout.
    sleeper = tmp_path / "sleeper_grader.py"
    sleeper.write_text(textwrap.dedent("""
        import time
        time.sleep(60)
    """))
    res = await GraderRunner(sleeper, timeout=1.0).grade(tmp_path)
    assert res.timed_out and res.score is None


async def test_garbage_grader_output_is_crash(tmp_path):
    bad = tmp_path / "bad_grader.py"
    bad.write_text("print('not json')")
    res = await GraderRunner(bad, timeout=5.0).grade(tmp_path)
    assert res.crashed and res.score is None
