"""Build the thinking-disabled chat template for Qwen3-8B (v2 stack).

Qwen3's stock template checks `enable_thinking is defined and enable_thinking
is false` to prefill an empty <think></think> block (thinking off). vLLM's
server never passes that var, so we bake it in: prepend a Jinja `set` and
write the result to /tmp/aij2115/qwen3_nothink.jinja for `vllm serve
--chat-template`. The HF latent server passes enable_thinking=False to
apply_chat_template directly — same rendered string, keeping parity.
"""
import json
import sys

snap = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/aij2115/qwen3_nothink.jinja"
with open(snap + "/tokenizer_config.json") as f:
    tc = json.load(f)
tmpl = tc["chat_template"]
assert "enable_thinking" in tmpl, "template has no enable_thinking knob!"
with open(out, "w") as f:
    f.write("{%- set enable_thinking = false %}\n" + tmpl)
print(f"wrote {out} ({len(tmpl)} chars base template)")
