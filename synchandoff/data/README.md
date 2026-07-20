---
license: mit
---

# SyncBench

In tackling the challenge of *agent out-of-sync*, **SyncBench** is released as a part of our work [SyncMind: Measuring Agent Out-of-Sync Recovery In Collaborative Software Engineering](https://xhguo7.github.io/SyncMind/)

## Dataset Description
**SyncBench** for *agent out-of-sync* recovery:
- Task: Agent *out-of-sync*
- SyncBench
    - In our current version, we construct *SyncBench* based on 21 popular GitHub repositories, while our dataset construction approach allows adaptive upsampling and downsampling for custom needs
        - Expand to incorporate other repositories as data sources
        - Downsampled to smaller ealuation subsets
- Datasets: Caller and Callee
    - **Caller:** Testing code out-of-sync
    - **Callee:** Tested code out-of-sync


## Data Structure
- Format: JSON and CSV
- Fields:
    - **instance_id:**  SyncBench instance ID
    - **instance_type:**  data type (i.e., `caller` or `callee`)
    - **task_type:** task type (i.e., `fail-to-pass` or `pass-to-pass`)
    - **repo_url:**  URL link of the source GitHub repository
    - **commit:** Git commit ID
    - **fm_type:** Function type (i.e., `function` or `method`)
    - **fm_name:** Function name
    - **original_code:** Out-of-sync function code
    - **gold_code:** Up-to-date function code
    - **old_filtered_context:** Out-of-sync context code (filtered)
    - **old_complete_context:** Out-of-sync context code (complete)
    - **new_filtered_context:** Up-to-date context code (filtered)
    - **new_complete_context:** Up-to-date context code (complete)
    - **initial_error_log:** Initial execution error log
    - **original_summary:** Parsed execution output of the out-of-sync code
    - **gold_summary:** Parsed execution output of the up-to-date code
    - **pyfile_name:** Name of the Python file
    - **pyfile_path:** Path to the Python file
    - **unittest_path:** Path to the unit test

- Dataset Versions
    - SyncBench
        - Data: syncbench_24k.csv
        - Size: 24,332
    - Evaluation Dataset
        - Data: syncbench_300.csv
            - Callee: syncbench_callee_150.csv
            - Caller: syncbench_caller_150.csv
        - Size: 300

## Usage
```python
from datasets import load_dataset
dataset = load_dataset("xuehang/SyncBench")
