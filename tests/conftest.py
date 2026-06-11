import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

TASK_DIR = REPO_ROOT / "tasks" / "circle_packing"
GRADER_PATH = TASK_DIR / "eval" / "grader.py"
TASK_YAML = TASK_DIR / "task.yaml"


@pytest.fixture
def task_yaml() -> Path:
    return TASK_YAML


@pytest.fixture
def grader_path() -> Path:
    return GRADER_PATH


@pytest.fixture
def seed_dir() -> Path:
    return TASK_DIR / "seed"
