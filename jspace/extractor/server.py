"""J-space extraction service (E2-mini).

Loads HF Qwen/Qwen3.5-4B + the pre-fitted Jacobian lens (neuronpedia/jacobian-lens,
rev qwen-n1000) and serves one endpoint:

  POST /extract  {"messages": [...], "tools": [...]}   ->
      {"blurb": "<explained JSON readout, <=~3000 chars>", "meta": {...}}

Method (per the E2-mini spec):
  - The realized work-segment text of shift A = its stored transcript rendered
    through the SAME chat template vLLM serves (tools included), prefilled once
    (no generation) through the HF model.
  - At ONE layer (L12, inside the located workspace core L6-L18; j-think CKA),
    the lens readout at each position is  logits = W_U @ (J_12 @ h_12)   with
    h_12 = the output of decoder block 12 (matching j-think's hook convention and
    the README's "directions are rows of W_U @ J_l").
  - top-k=5 tokens per position; consecutive positions sharing a top-1 token are
    collapsed (keep the max-logit position of the run); positions whose whole
    top-k is punctuation/stop-tokens are dropped.
  - SILENT marking: a workspace token is starred iff its string never appears in
    A's own generated text (assistant turns incl. the hand-off note), lowercased
    substring test. Silent tokens are the payload.
  - Cap: entries are kept by (has-silent, top-1 logit) priority until the JSON is
    ~CAP_CHARS, then re-sorted by position.

GPU use is serialized with a lock (one prefill at a time); the model is 4B bf16
(~9GB) and shares the card with the vLLM server (which is capped at 55% mem).
"""
import json
import os
import re
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch

MODEL_ID = os.environ.get("JSPACE_MODEL", "Qwen/Qwen3.5-4B")
LAYER = int(os.environ.get("JSPACE_LAYER", "12"))
TOPK = int(os.environ.get("JSPACE_TOPK", "5"))
CAP_CHARS = int(os.environ.get("JSPACE_CAP_CHARS", "3000"))
# Prefill length guard: transcripts can approach the 64k serving context; keep the
# head (task) + tail (latest work) if over.
MAX_FWD_TOKENS = int(os.environ.get("JSPACE_MAX_FWD_TOKENS", "32000"))
HEAD_KEEP = 2048
PORT = int(os.environ.get("JSPACE_PORT", "8398"))

LENS_REPO = "neuronpedia/jacobian-lens"
LENS_REV = "qwen-n1000"
LENS_FILE = "qwen3.5-4b/jlens/Salesforce-wikitext/Qwen3.5-4B_jacobian_lens_n1000.pt"

DEV = os.environ.get("JSPACE_DEVICE", "cuda:0")

# --- stop/noise vocabulary for the noise filter ------------------------------
_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "at", "is", "are",
    "was", "were", "be", "been", "it", "its", "as", "by", "for", "with", "that",
    "this", "these", "those", "he", "she", "they", "we", "you", "i", "his",
    "her", "their", "our", "not", "no", "yes", "but", "if", "then", "so",
    "do", "does", "did", "have", "has", "had", "will", "would", "can", "could",
    "there", "here", "what", "which", "who", "when", "where", "how", "from",
    "s", "t", "n", "d", "m", "re", "ve", "ll", "am", "im", "also", "than",
    "into", "about", "over", "under", "up", "down", "out", "just", "very",
}


def _is_noise(tok_str):
    t = tok_str.strip().lower()
    if not t:
        return True
    if not re.search(r"[a-z0-9À-ɏ一-鿿]", t):
        return True          # pure punctuation / symbols / whitespace
    return t in _STOPWORDS


print(f"[jspace] loading {MODEL_ID} ...", flush=True)
from transformers import AutoTokenizer, AutoConfig  # noqa: E402

tok = AutoTokenizer.from_pretrained(MODEL_ID)
_cfg = AutoConfig.from_pretrained(MODEL_ID)


def _load_model():
    import transformers
    for cls_name in ("AutoModelForCausalLM", "AutoModelForImageTextToText", "AutoModel"):
        cls = getattr(transformers, cls_name, None)
        if cls is None:
            continue
        try:
            m = cls.from_pretrained(MODEL_ID, dtype=torch.bfloat16, device_map={"": 0})
            print(f"[jspace] loaded via {cls_name}", flush=True)
            return m
        except Exception as e:
            print(f"[jspace] {cls_name} failed: {e}", flush=True)
    raise RuntimeError("could not load model with any Auto class")


model = _load_model()
model.eval()


def _find_text_tower(m):
    """The text decoder holding .layers (ModuleList of blocks) — Qwen3.5-4B is
    multimodal, so the text tower may sit under .language_model (possibly nested)."""
    cands = []
    for name, mod in m.named_modules():
        if hasattr(mod, "layers") and isinstance(getattr(mod, "layers"), torch.nn.ModuleList) \
                and hasattr(mod, "embed_tokens"):
            cands.append((name, mod))
    if not cands:
        raise RuntimeError("no text tower with .layers/.embed_tokens found")
    # prefer the one whose name mentions language_model, else the shortest path
    cands.sort(key=lambda nm: (("language_model" not in nm[0]), len(nm[0])))
    print(f"[jspace] text tower: {cands[0][0] or '<root>'} "
          f"({len(cands[0][1].layers)} layers)", flush=True)
    return cands[0][1]


text = _find_text_tower(model)
layers = text.layers
W_U = text.embed_tokens.weight            # [V, d] tied embeddings = unembedding
V, D = W_U.shape
print(f"[jspace] W_U {tuple(W_U.shape)}", flush=True)

from huggingface_hub import hf_hub_download  # noqa: E402

lens_path = hf_hub_download(LENS_REPO, filename=LENS_FILE, revision=LENS_REV)
blob = torch.load(lens_path, map_location="cpu", weights_only=False)
J12 = blob["J"][LAYER].to(DEV, torch.float32)          # [d, d]
print(f"[jspace] lens L{LAYER} loaded {tuple(J12.shape)} "
      f"(source layers {min(blob['J'])}..{max(blob['J'])})", flush=True)
W_U32 = W_U.detach().to(torch.float32)                  # [V, d] on GPU, ~2.5GB
_gpu_lock = threading.Lock()


def _dictify_tool_calls(messages):
    """Chat templates want tool_call arguments as objects, the OpenAI wire format
    carries them as JSON strings; also drop harness-only annotation keys."""
    out = []
    for m in messages:
        m = {k: v for k, v in m.items() if k != "reasoning_content"}
        if m.get("tool_calls"):
            tcs = []
            for tc in m["tool_calls"]:
                tc = json.loads(json.dumps(tc))
                fn = tc.get("function") or {}
                if isinstance(fn.get("arguments"), str):
                    try:
                        fn["arguments"] = json.loads(fn["arguments"] or "{}")
                    except Exception:
                        pass
                tcs.append(tc)
            m["tool_calls"] = tcs
        out.append(m)
    return out


def _render(messages, tools):
    msgs = _dictify_tool_calls(messages)
    for kw in ({"tools": tools}, {}):
        try:
            ids = tok.apply_chat_template(
                msgs, tokenize=True, add_generation_prompt=False,
                return_tensors="pt", **kw)
            return ids
        except Exception as e:
            err = e
    # last resort: plain concatenation (fidelity note logged in meta by caller)
    text_fallback = "\n\n".join(
        f"[{m.get('role')}]\n{m.get('content') or ''}" for m in msgs)
    print(f"[jspace] chat template failed ({err}); plain-text fallback", flush=True)
    return tok(text_fallback, return_tensors="pt").input_ids


@torch.no_grad()
def _lens_topk(ids):
    """Prefill ids [1,T]; return (top vals [T,k] fp32 cpu, top idx [T,k] cpu)."""
    cap = {}
    h = layers[LAYER].register_forward_hook(
        lambda m, i, o: cap.__setitem__("h", (o[0] if isinstance(o, tuple) else o).detach()))
    try:
        text(input_ids=ids.to(DEV), use_cache=False)
    finally:
        h.remove()
    H = cap["h"][0].to(torch.float32)                   # [T, d]
    proj = H @ J12.T                                    # [T, d]
    vals_l, idx_l = [], []
    CH = 4096
    for i in range(0, proj.shape[0], CH):
        logits = proj[i:i + CH] @ W_U32.T               # [c, V]
        v, ix = torch.topk(logits, TOPK, dim=-1)
        vals_l.append(v.cpu())
        idx_l.append(ix.cpu())
    return torch.cat(vals_l), torch.cat(idx_l)


def extract(messages, tools):
    gen_text = "\n".join(
        (m.get("content") or "") for m in messages if m.get("role") == "assistant")
    gen_lower = gen_text.lower()

    ids = _render(messages, tools)
    T_full = ids.shape[1]
    clipped = False
    if T_full > MAX_FWD_TOKENS:
        ids = torch.cat([ids[:, :HEAD_KEEP], ids[:, -(MAX_FWD_TOKENS - HEAD_KEEP):]], dim=1)
        clipped = True

    with _gpu_lock:
        vals, idx = _lens_topk(ids)
        torch.cuda.empty_cache()

    ctx_toks = tok.convert_ids_to_tokens(ids[0].tolist())

    def _clean(t):
        return tok.convert_tokens_to_string([t]).strip()

    # per-position entries -> collapse runs of identical top-1 (keep max-logit pos)
    entries = []
    run_top1, run_best = None, None
    for p in range(len(ctx_toks)):
        top1 = int(idx[p, 0])
        if top1 == run_top1:
            if float(vals[p, 0]) > run_best[0]:
                run_best = (float(vals[p, 0]), p)
            continue
        if run_best is not None:
            entries.append(run_best[1])
        run_top1, run_best = top1, (float(vals[p, 0]), p)
    if run_best is not None:
        entries.append(run_best[1])

    kept = []
    for p in entries:
        toks = [_clean(tok.convert_ids_to_tokens(int(idx[p, j]))) for j in range(TOPK)]
        if all(_is_noise(t) for t in toks):
            continue          # pure-noise position
        ws, n_silent = [], 0
        seen = set()
        for j, t in enumerate(toks):
            if _is_noise(t) or t.lower() in seen:
                continue
            seen.add(t.lower())
            silent = len(t) >= 3 and t.lower() not in gen_lower
            n_silent += int(silent)
            ws.append(t + "*" if silent else t)
        if not ws:
            continue
        kept.append(dict(pos=p, context_token=_clean(ctx_toks[p]) or ctx_toks[p],
                         workspace=ws, _logit=float(vals[p, 0]),
                         _silent=n_silent))

    # priority: entries with silent tokens first, then by top-1 logit
    ranked = sorted(kept, key=lambda e: (-(e["_silent"] > 0), -e["_logit"]))
    sel, size = [], 2
    for e in ranked:
        s = len(json.dumps({k: e[k] for k in ("pos", "context_token", "workspace")},
                           ensure_ascii=False)) + 2
        if size + s > CAP_CHARS:
            continue
        sel.append(e)
        size += s
    sel.sort(key=lambda e: e["pos"])
    blurb = json.dumps([{k: e[k] for k in ("pos", "context_token", "workspace")}
                        for e in sel], ensure_ascii=False)

    n_ws = sum(len(e["workspace"]) for e in sel)
    n_sil = sum(e["_silent"] for e in sel)
    meta = dict(forward_tokens=int(ids.shape[1]), full_tokens=int(T_full),
                clipped=clipped, entries_after_collapse=len(entries),
                entries_nonnoise=len(kept), entries_kept=len(sel),
                workspace_tokens=n_ws, silent_tokens=n_sil,
                silent_frac=round(n_sil / n_ws, 3) if n_ws else None,
                blurb_chars=len(blurb), gen_chars=len(gen_text))
    return blurb, meta


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, {"ok": True, "model": MODEL_ID, "layer": LAYER})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n))
            blurb, meta = extract(req["messages"], req.get("tools"))
            self._send(200, {"blurb": blurb, "meta": meta})
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    print(f"[jspace] serving on :{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
