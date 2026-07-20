"""Step 0: custom AWQ-MoE loader smoke — load, inspect cache structure,
greedy-generate. Run on tigerfish:
  CUDA_VISIBLE_DEVICES=1 /tmp/aij2115/latentenv/bin/python -u load_test.py
"""
import sys
import time

import torch
from transformers import AutoTokenizer

from awq_moe import load_model

MODEL = "/tmp/aij2115/models/qwen36-awq"


def main():
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = load_model(MODEL)
    print(f"model up ({time.time()-t0:.0f}s), mem "
          f"{torch.cuda.memory_allocated()/1e9:.1f} GB", flush=True)

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "In one short sentence, what does the pytest -k flag do?"},
    ]
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    ids = tok(text, return_tensors="pt", add_special_tokens=False).input_ids.to("cuda:0")

    with torch.inference_mode():
        out = model.model(input_ids=ids, use_cache=True)
        cache = out.past_key_values
        print("cache:", type(cache).__name__, "layers:", len(cache.layers))
        for i in (0, 3):
            lay = cache.layers[i]
            print(f"  layer {i}: {type(lay).__name__}", flush=True)
            for attr in ("keys", "values", "conv_states", "recurrent_states"):
                v = getattr(lay, attr, None)
                if isinstance(v, (list, tuple)) and v:
                    print(f"    {attr}: list[{len(v)}]", tuple(v[0].shape))
                elif torch.is_tensor(v):
                    print(f"    {attr}: {tuple(v.shape)} {v.dtype}")

        eos = model.generation_config.eos_token_id
        eos = set(eos if isinstance(eos, (list, tuple)) else [eos])
        h = out.last_hidden_state[:, -1]
        toks = []
        t1 = time.time()
        for _ in range(150):
            nxt = int(torch.argmax(model.lm_head(h)[0].float()))
            if nxt in eos:
                break
            toks.append(nxt)
            out = model.model(input_ids=torch.tensor([[nxt]], device="cuda:0"),
                              past_key_values=cache, use_cache=True)
            cache = out.past_key_values
            h = out.last_hidden_state[:, -1]
        dt = time.time() - t1
    print(f"=== generation ({len(toks)} tokens, {len(toks)/dt:.1f} tok/s) ===")
    print(tok.decode(toks, skip_special_tokens=True))
    print("PASS")


if __name__ == "__main__":
    sys.exit(main())
