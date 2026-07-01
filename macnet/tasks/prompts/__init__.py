from .alfworld_prompt import alfworld_solver_system_prompt, alfworld_few_shots
from .sciworld_prompt import sciworld_solver_system_prompt, sciworld_few_shots
from .fever_prompt import fever_solver_system_prompt, fever_few_shots
from .pddl_prompt import pddl_prompts, pddl_output_format

INTERACTION_PROTOCOL = """\
## How to act (read this first)
This is an interactive, turn-based task: you take ONE step at a time and the environment replies with the real result of that step.

- Do ALL of your reasoning privately inside a <think>...</think> block. Anything inside <think> is for you alone and is never shown to the environment or to other agents, so reason there as much as you need.
- After the </think> tag, output EXACTLY ONE action, on a single line, and then STOP.
- Do NOT write an "Observation:" line yourself, do NOT make up the environment's reply, and do NOT emit more than one action or plan future steps in your visible output. After each action the environment sends back the real observation - only then do you choose your next action.
- The worked examples you are shown are COMPLETE multi-turn interactions for reference only: their Observation lines are the environment's replies (never something you write), and each Action line there is a separate turn.

"""



def get_dataset_system_prompt(task: str, task_config: dict) -> str:
    prompt_map: dict = {
        'alfworld': alfworld_solver_system_prompt,
        'sciworld': sciworld_solver_system_prompt,
        'fever': fever_solver_system_prompt,
        'pddl': pddl_prompts
    }

    if prompt_map.get(task) is None:
        raise ValueError(f'Unsupported task type: {task}')
    
    if task != 'pddl':
        return INTERACTION_PROTOCOL + prompt_map.get(task)
    else:
        task_type: str = task_config.get('game_name')
        return INTERACTION_PROTOCOL + pddl_prompts[task_type]['instruction'] + pddl_output_format
        


def get_task_few_shots(dataset: str, task_config: dict, few_shots_num: int) -> list[str]:
    
    if dataset == 'alfworld':
        task_type = task_config.get('task_type')
        if task_type is None:
            raise ValueError('The task config must have the `task_type` attribute.')
        return [alfworld_few_shots[f'react_{task_type}_2'], alfworld_few_shots[f'react_{task_type}_0']][:few_shots_num]
    
    elif dataset == 'sciworld':
        return sciworld_few_shots[:few_shots_num]
    
    elif dataset == 'fever':
        return fever_few_shots[:few_shots_num]
    
    elif dataset == 'pddl':
        task_type = task_config.get('game_name')
        if task_type is None:
            raise ValueError('The task config must have the `game_name` attribute.')
        return pddl_prompts[task_type]['examples'][:few_shots_num]
    
    else:
        raise ValueError(f'Unsupported dataset type: {dataset}')

