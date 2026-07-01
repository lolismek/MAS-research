import json
import jsonlines

from .base_env import BaseEnv, BaseRecorder

# NOTE: alfworld / scienceworld / pddlgym are heavy, optional backends. Import them (and build their
# task lists) lazily, per requested task, so a FEVER-only run needs none of them installed. FEVER's
# loader is pure JSON and stays cheap.

TASKS_PATH = {
    'alfworld': 'data/alfworld/alfworld_tasks_suffix.json',
    'fever': 'data/fever/fever_dev.jsonl',
    'pddl': 'data/pddl/test.jsonl',
    'sciworld': 'data/sciworld/test.jsonl',
}


def _load_alfworld_tasks() -> list[dict]:
    from .alfworld_env import get_env_name_from_gamefile, prefixes
    return [
        {
            'task': f'{row["goal"]}',
            'env_kwargs': {'config': 'alfworld', "gamefile": row["gamefile"]},
            'task_type': prefixes[get_env_name_from_gamefile(row["gamefile"])],
            'env_name': get_env_name_from_gamefile(row["gamefile"]),
        }
        for row in json.load(open(TASKS_PATH['alfworld'], "r"))
    ]


def _load_sciworld_tasks() -> list[dict]:
    from .sciworld_env import build_simplification_str
    tasks: list = []
    with open(TASKS_PATH['sciworld'], 'r+', encoding='utf-8') as f:
        for item in jsonlines.Reader(f):
            tasks.append({
                "id": item['id'],
                "task_name": item["additional_info"]["env_name"],
                "var": item["additional_info"]["var"],
                "modified_goal": item["goal"],
                "subgoals": item['subgoals'],
                "difficulty": item["difficulty"],
                "simplification_str": build_simplification_str(),
            })
    return tasks


def _load_fever_tasks() -> list[dict]:
    with open(TASKS_PATH['fever'], 'r') as f:
        return [
            {'task': row['claim'], 'answer': row['label'], 'env_name': 'fever'}
            for row in (json.loads(line) for line in f)
        ][:100]


def _load_pddl_tasks() -> list[dict]:
    from .pddl_env.pddl_env import get_all_environment_configs
    TASK_NAMES = ["barman", "blockworld", "gripper", "tyreworld"]
    return get_all_environment_configs(TASK_NAMES, TASKS_PATH['pddl'])


_TASK_LOADERS = {
    'alfworld': _load_alfworld_tasks,
    'sciworld': _load_sciworld_tasks,
    'fever': _load_fever_tasks,
    'pddl': _load_pddl_tasks,
}


def _get_env_cls(task: str):
    if task == 'alfworld':
        from .alfworld_env import AlfworldEnv
        return AlfworldEnv
    if task == 'sciworld':
        from .sciworld_env import SciworldEnv
        return SciworldEnv
    if task == 'fever':
        from .fever_env import FeverEnv
        return FeverEnv
    if task == 'pddl':
        from .pddl_env.pddl_env import PDDLEnv
        return PDDLEnv
    return None


def _get_recorder_cls(task: str):
    if task == 'alfworld':
        from .alfworld_env import AlfworldRecorder
        return AlfworldRecorder
    if task == 'sciworld':
        from .sciworld_env import SciworldRecorder
        return SciworldRecorder
    if task == 'fever':
        from .fever_env import FeverRecorder
        return FeverRecorder
    if task == 'pddl':
        from .pddl_env.pddl_env import PDDLRecorder
        return PDDLRecorder
    return None


def get_env(task: str, env_config: dict, max_trials: int) -> BaseEnv:
    cls = _get_env_cls(task)
    if cls is None:
        raise ValueError(f'Unsupported task type: {task}')
    return cls(env_config, max_trials)


def get_recorder(task: str, working_dir: str, namespace: str) -> BaseRecorder:
    cls = _get_recorder_cls(task)
    if cls is None:
        raise ValueError(f'Unsupported task type: {task}')
    return cls(working_dir=working_dir, namespace=namespace)


def get_task(task: str) -> list[dict]:
    loader = _TASK_LOADERS.get(task)
    if loader is None:
        raise ValueError(f'Unsupported task type: {task}')
    return loader()
