For the full MAD (Multi-Agent systems failure Dataset) that is produced by using the MAST, please visit [https://huggingface.co/datasets/mcemri/MAD](https://huggingface.co/datasets/mcemri/MAD)

Or you can use it by following the steps below:

For LLM-as-a-Judge annotated traces:
```
from huggingface_hub import hf_hub_download
import pandas as pd
import json

REPO_ID = "mcemri/MAD"
FILENAME = "MAD_full_dataset.json"

file_path =  hf_hub_download(repo_id=REPO_ID, filename=FILENAME, repo_type="dataset")
with open(file_path, "r") as f:
    data = json.load(f)

print(f"Loaded {len(data)} records (full dataset).")
```

For human annotated traces:
```
FILENAME = "MAD_human_labelled_dataset.json"

file_path =  hf_hub_download(repo_id=REPO_ID, filename=FILENAME, repo_type="dataset")
with open(file_path, "r") as f:
    data = json.load(f)

print(f"Loaded {len(data)} records (human labelled).")
```
