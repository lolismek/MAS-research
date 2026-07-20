"""SyncBench instance loading.

An instance = one out-of-sync episode in a real repo. The env is NOT built by
checking out `commit` (that field is provenance of the stale code): the Docker
image `xuehang/<prefix>:3.11` already contains /workspace/test_repo at the
up-to-date state plus /workspace/test_venv with all deps installed. The only
mutation that creates the task is writing `pyfile_path` as new_complete_context
with the target function replaced by original_code (see splice.py) — after
which the unit test at `unittest_path` fails exactly as `initial_error_log`
records. Restoring new_complete_context makes it pass (`gold_summary`).
"""
import ast
import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

WORKDIR = "/workspace/test_repo"
VENV = "/workspace/test_venv"


def load_instances(split="callee"):
    """Return list of instance dicts from syncbench_300_{callee,caller}.csv."""
    df = pd.read_csv(os.path.join(DATA, f"syncbench_300_{split}.csv"))
    return df.to_dict(orient="records")


def load_repo_dict():
    with open(os.path.join(DATA, "repo_dict.json")) as f:
        return json.load(f)


def repo_meta(instance):
    """Per-repo test config (extra pytest flags etc.) from SyncMind's repo dict."""
    repo_id = int(instance["instance_id"].split("_")[0])
    return load_repo_dict()[repo_id - 1]


def image_for(instance):
    """xuehang/<instance_id prefix>:3.11 — verified present on Docker Hub for
    all 42 (repo x callee/caller) prefixes in syncbench_300."""
    prefix = instance["instance_id"].split("__")[0]
    return f"xuehang/{prefix}:3.11"


def container_pyfile_path(instance):
    """Path of the out-of-sync file inside the container."""
    return WORKDIR + instance["pyfile_path"].split("test_repo")[1]


def unittest_rel_path(instance):
    """Unit-test path relative to the repo root (pytest is run from there)."""
    return instance["unittest_path"].split("test_repo/")[1]


def parse_summary(s):
    """CSV stores pytest summaries as python-dict strings."""
    return ast.literal_eval(s) if isinstance(s, str) else s
