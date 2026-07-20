"""Latent handoff server — tigerfish side (one GPU, plain HF transformers).

Loads the AWQ Qwen3.6-35B-A3B checkpoint (qwen3_5_moe hybrid: 10 full-attention
layers with positional KV + 30 GatedDeltaNet linear-attention layers with a
fixed-size recurrent state) and exposes:

  POST /prefill_capture   deterministic prefill of a message list; caches the
                          live cache + optional residual-stream hidden states
                          server-side under a session id.
  POST /make_artifact     builds a latent artifact from a session:
                          kv_last / kv_positions / kv_rand / kv_attn (L-KV),
                          thought_coconut / thought_pool / thought_rand
                          (L-THOUGHT). Persists to LATENT_ART_DIR as .pt+.json
                          (slot + bit capacity ledgers in the .json).
  POST /generate          (also /v1/chat/completions) OpenAI-style chat
  POST /v1/chat/completions  completion with optional latent injection: KV
                          artifacts become a KV prefix (original RoPE rotations
                          kept, B's positions offset past A's context);
                          embedding artifacts are spliced at the marker
                          position via inputs_embeds. Plain text-only requests
                          work too (used for the HF-vs-vLLM parity check).
  POST /session_free      drop a session (GPU memory).
  GET  /health

The handoff artifact reference travels IN-BAND: a marker
    [[LATENT:kv:<artifact_id>]]  or  [[LATENT:embeds:<artifact_id>]]
anywhere in the request messages. The server strips it (whole line) and
injects the artifact. This lets the unmodified piranha proxy (think-strip +
XML tool-call parsing) sit in front, exactly as for the text arms.

Positions/RoPE (design note): sliced keys keep their ORIGINAL rotations and
absolute positions from A's prefill; B's tokens get position_ids starting at
A's total length T. RoPE is relative, so B sees correct distances to the
prefix and to itself, and non-contiguous selections need no re-rotation.
Linear-attention layers get NO prefix (fresh recurrent state) unless the
artifact was built with include_linear_state=True.

Run (tigerfish):
  CUDA_VISIBLE_DEVICES=1 HOME=/tmp/aij2115/fakehome \
  setsid nohup /tmp/aij2115/latentenv/bin/python -u server.py --port 8802 \
      > /tmp/aij2115/latent/server_8802.log 2>&1 < /dev/null &
"""
import argparse
import copy
import json
import os
import re
import threading
import time
import uuid

import torch
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from transformers import AutoTokenizer
from transformers.cache_utils import DynamicCache

MODEL_DIR = os.environ.get("LATENT_MODEL_DIR", "/tmp/aij2115/models/qwen36-awq")
ART_DIR = os.environ.get("LATENT_ART_DIR", "/tmp/aij2115/latent_artifacts")
MAX_SESSIONS = 2
PREFILL_CHUNK = 8192
MAX_NEW_DEFAULT = 28000          # match the text-arm proxy's TINKER_MAX_TOKENS
MARKER_RE = re.compile(r"\[\[LATENT:(kv|embeds):([A-Za-z0-9_\-\.]+)\]\]")

app = FastAPI()
GPU_LOCK = threading.Lock()      # one request touches the GPU at a time

tok = None
model = None
txt = None                       # the text decoder (Qwen3_5MoeTextModel)
lm_head = None
FULL_LAYERS = []                 # indices of full_attention layers
TEXT_CFG = None


# ------------------------------------------------------------- model load ----
def load_model():
    global tok, model, txt, lm_head, FULL_LAYERS, TEXT_CFG
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(MODEL_DIR)
    from awq_moe import load_model as awq_load
    model = awq_load(MODEL_DIR, device="cuda:0")
    txt = model.model
    lm_head = model.lm_head
    TEXT_CFG = txt.config
    FULL_LAYERS = [i for i, t in enumerate(TEXT_CFG.layer_types)
                   if t == "full_attention"]
    os.makedirs(ART_DIR, exist_ok=True)
    print(f"model loaded in {time.time()-t0:.0f}s; full-attn layers: {FULL_LAYERS}",
          flush=True)


# --------------------------------------------------------- message plumbing ----
def normalize_messages(messages):
    """Qwen's chat template wants tool_call arguments as dicts, not the OpenAI
    JSON-string form the proxy forwards. Also drop null-content fields the
    template chokes on."""
    out = []
    for msg in messages:
        msg = dict(msg)
        if msg.get("tool_calls"):
            tcs = []
            for tc in msg["tool_calls"]:
                tc = dict(tc)
                fn = dict(tc.get("function") or {})
                a = fn.get("arguments")
                if isinstance(a, str):
                    try:
                        fn["arguments"] = json.loads(a) if a.strip() else {}
                    except Exception:
                        fn["arguments"] = {"_raw": a}
                tc["function"] = fn
                tcs.append(tc)
            msg["tool_calls"] = tcs
        if msg.get("content") is None:
            msg["content"] = ""
        out.append(msg)
    return out


def find_marker(messages):
    """Return (arm_kind, artifact_id) of the first [[LATENT:...]] marker, or
    (None, None). The marker is NOT stripped here — stripping happens on the
    templated string so the embeds splice point is known."""
    for msg in messages:
        c = msg.get("content")
        if isinstance(c, str):
            match = MARKER_RE.search(c)
            if match:
                return match.group(1), match.group(2)
    return None, None


def template_text(messages, tools=None, add_generation_prompt=True):
    return tok.apply_chat_template(
        normalize_messages(messages), tools=tools or None, tokenize=False,
        add_generation_prompt=add_generation_prompt)


def message_boundaries(messages, tools=None):
    """Token index of the END of each message in the templated sequence,
    via incremental prefix templating (Qwen's template is prefix-stable for
    plain turns). Returns list of {'index','role','token_end'} or None."""
    try:
        norm = normalize_messages(messages)
        full = tok.apply_chat_template(norm, tools=tools or None, tokenize=False,
                                       add_generation_prompt=False)
        out = []
        for i in range(1, len(norm) + 1):
            pref = tok.apply_chat_template(norm[:i], tools=tools or None,
                                           tokenize=False,
                                           add_generation_prompt=False)
            if not full.startswith(pref):
                return None
            n = len(tok(pref, add_special_tokens=False).input_ids)
            out.append({"index": i - 1, "role": norm[i - 1].get("role"),
                        "token_end": n})
        return out
    except Exception:
        return None


# ----------------------------------------------------------- cache helpers ----
def new_cache():
    return DynamicCache(config=TEXT_CFG)


def cache_kv(cache):
    """{layer_idx: (K,V)} of the full-attention layers, tensors as stored."""
    out = {}
    for i in FULL_LAYERS:
        lay = cache.layers[i]
        k, v = getattr(lay, "keys", None), getattr(lay, "values", None)
        if k is None:
            continue
        out[i] = (k, v)
    return out


def cache_linear_states(cache):
    """{layer_idx: (conv_state, recurrent_state)} of linear-attention layers.
    Containers are dicts keyed by state_idx (transformers 5.x
    LinearAttentionCacheLayerMixin); we use state 0."""
    out = {}
    for i, t in enumerate(TEXT_CFG.layer_types):
        if t != "linear_attention":
            continue
        lay = cache.layers[i]
        cs = getattr(lay, "conv_states", None)
        rs = getattr(lay, "recurrent_states", None)
        if not cs or not rs or cs.get(0) is None or rs.get(0) is None:
            continue
        out[i] = (cs[0], rs[0])
    return out


def seed_cache_kv(cache, kv_dict, linear_dict=None):
    """Seed a fresh cache with a KV prefix (and optionally linear states)."""
    for i, (k, v) in kv_dict.items():
        cache.layers[i].update(k.to("cuda:0"), v.to("cuda:0"))
    if linear_dict:
        for i, (cs, rs) in linear_dict.items():
            lay = cache.layers[i]
            dev_cs = cs.to("cuda:0")
            dev_rs = rs.to("cuda:0")
            lay.conv_states[0] = dev_cs
            lay.recurrent_states[0] = dev_rs
            lay.is_conv_states_initialized[0] = True
            lay.is_recurrent_states_initialized[0] = True
            lay.has_previous_state[0] = True
            lay.conv_kernel_size[0] = dev_cs.shape[-1]
            lay.device, lay.dtype = dev_cs.device, dev_cs.dtype


class HiddenTap:
    """Forward hooks capturing residual-stream outputs of chosen decoder
    layers (moved to CPU fp16 per chunk)."""

    def __init__(self, layer_idxs):
        self.data = {i: [] for i in layer_idxs}
        self.handles = []
        for i in layer_idxs:
            self.handles.append(txt.layers[i].register_forward_hook(
                self._make_hook(i)))

    def _make_hook(self, i):
        def hook(_mod, _inp, out):
            h = out[0] if isinstance(out, tuple) else out
            self.data[i].append(h.detach()[0].to("cpu", torch.float16))
        return hook

    def close(self):
        for h in self.handles:
            h.remove()
        return {i: torch.cat(chunks, dim=0) for i, chunks in self.data.items()
                if chunks}


@torch.inference_mode()
def chunked_prefill(input_ids, capture_layers=None):
    """Prefill input_ids [1,T] in chunks with a live cache. Returns
    (cache, hidden_dict, last_hidden_vec)."""
    cache = new_cache()
    tap = HiddenTap(capture_layers) if capture_layers else None
    T = input_ids.shape[1]
    last_hidden = None
    for s in range(0, T, PREFILL_CHUNK):
        chunk = input_ids[:, s:s + PREFILL_CHUNK].to("cuda:0")
        out = txt(input_ids=chunk, past_key_values=cache, use_cache=True)
        cache = out.past_key_values
        last_hidden = out.last_hidden_state[0, -1].clone()
    hidden = tap.close() if tap else {}
    return cache, hidden, last_hidden


# ------------------------------------------------------------ session store ----
SESSIONS = {}


def evict_sessions():
    while len(SESSIONS) > MAX_SESSIONS:
        oldest = min(SESSIONS, key=lambda s: SESSIONS[s]["created"])
        SESSIONS.pop(oldest, None)
    torch.cuda.empty_cache()


@app.post("/prefill_capture")
def prefill_capture(body: dict):
    """body: messages | raw_text, tools?, add_generation_prompt (default
    False), capture_layers [ints], session_id?, return_hidden?
    {positions: [ints] | 'turn_ends:<role>' | 'last', layers: [ints]}"""
    with GPU_LOCK:
        t0 = time.time()
        sid = body.get("session_id") or f"s_{uuid.uuid4().hex[:10]}"
        capture_layers = body.get("capture_layers") or []
        boundaries = None
        if body.get("raw_text") is not None:
            text = body["raw_text"]
        else:
            messages = body["messages"]
            text = template_text(messages, body.get("tools"),
                                 body.get("add_generation_prompt", False))
            boundaries = message_boundaries(messages, body.get("tools"))
        ids = tok(text, return_tensors="pt", add_special_tokens=False).input_ids
        T = ids.shape[1]
        cache, hidden, last_hidden = chunked_prefill(ids, capture_layers)
        emb = txt.embed_tokens(ids[:, -256:].to("cuda:0"))
        emb_norm = float(emb[0].norm(dim=-1).mean())
        SESSIONS[sid] = {"cache": cache, "n_tokens": T, "ids": ids,
                         "hidden": hidden, "last_hidden": last_hidden,
                         "boundaries": boundaries, "emb_norm": emb_norm,
                         "created": time.time()}
        evict_sessions()
        resp = {"session_id": sid, "n_tokens": T, "boundaries": boundaries,
                "emb_norm": emb_norm, "dur_s": round(time.time() - t0, 1)}
        rh = body.get("return_hidden")
        if rh:
            resp["hidden"] = _hidden_slice(SESSIONS[sid], rh)
        return resp


def _resolve_positions(sess, spec):
    if isinstance(spec, list):
        return [p for p in spec if 0 <= p < sess["n_tokens"]]
    if spec == "last":
        return [sess["n_tokens"] - 1]
    if isinstance(spec, str) and spec.startswith("turn_ends"):
        role = spec.split(":", 1)[1] if ":" in spec else "assistant"
        if not sess["boundaries"]:
            return [sess["n_tokens"] - 1]
        return [b["token_end"] - 1 for b in sess["boundaries"]
                if b["role"] == role and b["token_end"] - 1 < sess["n_tokens"]]
    return []


def _hidden_slice(sess, rh):
    layers = rh.get("layers") or list(sess["hidden"].keys())
    positions = _resolve_positions(sess, rh.get("positions", "last"))
    out = {"positions": positions, "layers": {}}
    for lay in layers:
        h = sess["hidden"].get(int(lay))
        if h is None:
            continue
        out["layers"][str(lay)] = [
            [round(float(x), 5) for x in h[p]] for p in positions]
    return out


@app.post("/session_free")
def session_free(body: dict):
    SESSIONS.pop(body.get("session_id"), None)
    torch.cuda.empty_cache()
    return {"ok": True}


# ------------------------------------------------------------ artifacts ----
def _bit_ledger_kv(n, linear_dict=None):
    kv_heads = TEXT_CFG.num_key_value_heads
    hd = TEXT_CFG.head_dim
    b = n * len(FULL_LAYERS) * 2 * kv_heads * hd * 2
    lin = 0
    if linear_dict:
        for cs, rs in linear_dict.values():
            lin += (cs.numel() + rs.numel()) * 2
    return {"kv_bytes": b, "linear_state_bytes": lin, "total_bytes": b + lin}


def _save_artifact(aid, kind, tensors, aux):
    torch.save({"kind": kind, **tensors}, os.path.join(ART_DIR, aid + ".pt"))
    aux = {"artifact_id": aid, "kind": kind, "created": time.time(), **aux}
    with open(os.path.join(ART_DIR, aid + ".json"), "w") as f:
        json.dump(aux, f, indent=1)
    return aux


def _load_artifact(aid):
    return torch.load(os.path.join(ART_DIR, aid + ".pt"),
                      map_location="cpu", weights_only=False)


def _kv_artifact(sess, positions, aid, include_linear_state=False, note=""):
    cache = sess["cache"]
    T = sess["n_tokens"]
    pos = torch.tensor(sorted(positions), dtype=torch.long)
    kv = {}
    for i, (k, v) in cache_kv(cache).items():
        kv[i] = (k[:, :, pos, :].to("cpu", torch.float16).clone(),
                 v[:, :, pos, :].to("cpu", torch.float16).clone())
    lin = None
    if include_linear_state:
        lin = {i: (cs.to("cpu").clone(), rs.to("cpu").clone())
               for i, (cs, rs) in cache_linear_states(cache).items()}
    tensors = {"kv": kv, "linear": lin, "positions": pos, "orig_len": T}
    aux = {"n_slots": len(pos), "slot_unit": "kv_position",
           "orig_ctx_len": T, "positions_head": pos[:8].tolist(),
           "contiguous": bool((pos[1:] - pos[:-1] == 1).all()) if len(pos) > 1 else True,
           "include_linear_state": include_linear_state,
           "bit_ledger": _bit_ledger_kv(len(pos), lin), "note": note}
    return _save_artifact(aid, "kv", tensors, aux)


@torch.inference_mode()
def _coconut_thoughts(sess, m, rescale=True):
    """Training-free Coconut/LatentMAS loop: last-layer (post-norm) hidden ->
    next input embedding, m steps, continuing from the session's live cache
    (on a COPY so the session stays reusable)."""
    cache = copy.deepcopy(sess["cache"])
    h = sess["last_hidden"].clone()
    emb_norm = sess["emb_norm"]
    vecs, norms, sims = [], [], []
    prev = None
    for _ in range(m):
        vecs.append(h.to("cpu", torch.float16).clone())
        norms.append(float(h.norm()))
        if prev is not None:
            sims.append(float(torch.nn.functional.cosine_similarity(
                h, prev, dim=0)))
        prev = h.clone()
        feed = h * (emb_norm / h.norm()) if rescale else h
        out = txt(inputs_embeds=feed[None, None, :].to("cuda:0", torch.float16),
                  past_key_values=cache, use_cache=True)
        cache = out.past_key_values
        h = out.last_hidden_state[0, -1].clone()
    del cache
    torch.cuda.empty_cache()
    return torch.stack(vecs), norms, sims


@app.post("/make_artifact")
def make_artifact(body: dict):
    """body: {arm, session_id?, params{...}, artifact_id?}"""
    with GPU_LOCK:
        arm = body["arm"]
        p = body.get("params") or {}
        aid = body.get("artifact_id") or f"{arm}_{uuid.uuid4().hex[:8]}"
        sess = SESSIONS.get(body.get("session_id") or "")
        try:
            if arm in ("kv_last", "kv_positions", "kv_rand", "kv_attn"):
                if sess is None:
                    return JSONResponse(status_code=400,
                                        content={"error": "unknown session"})
                T = sess["n_tokens"]
                n = min(int(p.get("n", 300)), T)
                if arm == "kv_last":
                    positions = list(range(T - n, T))
                elif arm == "kv_positions":
                    positions = p["positions"]
                elif arm == "kv_rand":
                    g = torch.Generator().manual_seed(int(p.get("seed", 0)))
                    positions = torch.randperm(T, generator=g)[:n].tolist()
                else:
                    return JSONResponse(status_code=400, content={
                        "error": "kv_attn not implemented in v1"})
                aux = _kv_artifact(sess, positions, aid,
                                   include_linear_state=bool(
                                       p.get("include_linear_state")),
                                   note=p.get("note", ""))
                return aux
            if arm == "thought_coconut":
                if sess is None:
                    return JSONResponse(status_code=400,
                                        content={"error": "unknown session"})
                m = int(p.get("m", 32))
                vecs, norms, sims = _coconut_thoughts(
                    sess, m, rescale=bool(p.get("rescale", True)))
                aux = {"n_slots": m, "slot_unit": "latent_vector",
                       "bit_ledger": {"total_bytes": vecs.numel() * 2},
                       "hidden_norms": [round(x, 1) for x in norms],
                       "consec_cos_sim": [round(x, 3) for x in sims],
                       "rescale": bool(p.get("rescale", True)),
                       "emb_norm": sess["emb_norm"],
                       "orig_ctx_len": sess["n_tokens"]}
                return _save_artifact(aid, "embeds", {"vectors": vecs}, aux)
            if arm == "thought_pool":
                text = p["text"]
                m = int(p.get("m", 32))
                ids = tok(text, return_tensors="pt",
                          add_special_tokens=False).input_ids.to("cuda:0")
                emb = txt.embed_tokens(ids)[0].to(torch.float32)  # [L, d]
                L = emb.shape[0]
                m = min(m, L)
                chunks = torch.chunk(emb, m, dim=0)
                vecs = torch.stack([c.mean(0) for c in chunks]).to(torch.float16).cpu()
                aux = {"n_slots": vecs.shape[0], "slot_unit": "latent_vector",
                       "bit_ledger": {"total_bytes": vecs.numel() * 2},
                       "src_text_tokens": L}
                return _save_artifact(aid, "embeds", {"vectors": vecs}, aux)
            if arm == "thought_rand":
                ref = _load_artifact(p["ref_artifact_id"])
                rv = ref["vectors"].to(torch.float32)
                g = torch.Generator().manual_seed(int(p.get("seed", 0)))
                r = torch.randn(rv.shape, generator=g)
                r = r / r.norm(dim=-1, keepdim=True) * rv.norm(dim=-1, keepdim=True)
                vecs = r.to(torch.float16)
                aux = {"n_slots": vecs.shape[0], "slot_unit": "latent_vector",
                       "bit_ledger": {"total_bytes": vecs.numel() * 2},
                       "matched_to": p["ref_artifact_id"]}
                return _save_artifact(aid, "embeds", {"vectors": vecs}, aux)
            return JSONResponse(status_code=400,
                                content={"error": f"unknown arm {arm}"})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JSONResponse(status_code=500, content={"error": str(e)})


# ------------------------------------------------------------- generation ----
def _eos_ids():
    gc = model.generation_config
    e = gc.eos_token_id
    if e is None:
        e = tok.eos_token_id
    return set(e if isinstance(e, (list, tuple)) else [e])


@torch.inference_mode()
def generate_text(prompt_text, artifact=None, marker_split=None,
                  max_new=MAX_NEW_DEFAULT, temperature=0.0):
    """Core loop. artifact: loaded .pt dict or None. marker_split: (left,
    right) prompt halves for embeds splice. Returns (text, n_prompt, n_gen,
    finish)."""
    cache = new_cache()
    pos0 = 0          # rotary position of the first prompt token
    cache_len = 0     # physical slots already in the cache
    if artifact and artifact["kind"] == "kv":
        kv = {i: (k, v) for i, (k, v) in artifact["kv"].items()}
        seed_cache_kv(cache, kv, artifact.get("linear"))
        n_prefix = artifact["positions"].shape[0]
        pos0 = int(artifact["orig_len"])
        cache_len = n_prefix

    if artifact and artifact["kind"] == "embeds":
        left, right = marker_split if marker_split else ("", prompt_text)
        el = txt.embed_tokens(tok(left, return_tensors="pt",
                                  add_special_tokens=False).input_ids.to("cuda:0"))
        er = txt.embed_tokens(tok(right, return_tensors="pt",
                                  add_special_tokens=False).input_ids.to("cuda:0"))
        lat = artifact["vectors"].to("cuda:0", torch.float16)[None]
        embeds = torch.cat([el, lat, er], dim=1)
        n_prompt = embeds.shape[1]
        feed = {"inputs_embeds": embeds}
    else:
        ids = tok(prompt_text, return_tensors="pt",
                  add_special_tokens=False).input_ids.to("cuda:0")
        n_prompt = ids.shape[1]
        feed = {"input_ids": ids}

    # prefill the prompt (with explicit positions when a KV prefix is present)
    position_ids = torch.arange(pos0, pos0 + n_prompt, device="cuda:0")[None]
    cache_position = torch.arange(cache_len, cache_len + n_prompt,
                                  device="cuda:0")
    attention_mask = torch.ones(1, cache_len + n_prompt, dtype=torch.long,
                                device="cuda:0")
    out = txt(**feed, past_key_values=cache, use_cache=True,
              position_ids=position_ids, cache_position=cache_position,
              attention_mask=attention_mask)
    cache = out.past_key_values

    eos = _eos_ids()
    generated = []
    finish = "length"
    h = out.last_hidden_state[:, -1]
    cur_pos = pos0 + n_prompt
    cur_cache = cache_len + n_prompt
    for _ in range(max_new):
        logits = lm_head(h)[0].float()
        if temperature and temperature > 0:
            probs = torch.softmax(logits / temperature, dim=-1)
            nxt = int(torch.multinomial(probs, 1))
        else:
            nxt = int(torch.argmax(logits))
        if nxt in eos:
            finish = "stop"
            break
        generated.append(nxt)
        step = torch.tensor([[nxt]], device="cuda:0")
        out = txt(input_ids=step, past_key_values=cache, use_cache=True,
                  position_ids=torch.tensor([[cur_pos]], device="cuda:0"),
                  cache_position=torch.tensor([cur_cache], device="cuda:0"),
                  attention_mask=torch.ones(1, cur_cache + 1, dtype=torch.long,
                                            device="cuda:0"))
        cache = out.past_key_values
        h = out.last_hidden_state[:, -1]
        cur_pos += 1
        cur_cache += 1
    del cache
    torch.cuda.empty_cache()
    text = tok.decode(generated, skip_special_tokens=True)
    return text, n_prompt, len(generated), finish


@app.post("/generate")
@app.post("/v1/chat/completions")
@app.post("/chat/completions")
def chat_completions(body: dict):
    with GPU_LOCK:
        t0 = time.time()
        try:
            messages = body.get("messages") or []
            tools = body.get("tools")
            kind, aid = find_marker(messages)
            if body.get("latent_artifact_id"):
                aid = body["latent_artifact_id"]
                kind = body.get("latent_kind", "kv")
            prompt = template_text(messages, tools, add_generation_prompt=True)
            artifact = None
            marker_split = None
            if aid:
                artifact = _load_artifact(aid)
                kind = artifact["kind"]
                match = MARKER_RE.search(prompt)
                if match and kind == "embeds":
                    marker_split = (prompt[:match.start()], prompt[match.end():])
                prompt = MARKER_RE.sub("", prompt)
            max_new = int(body.get("max_tokens") or MAX_NEW_DEFAULT)
            temperature = float(body.get("temperature") or 0.0)
            text, n_in, n_out, finish = generate_text(
                prompt, artifact, marker_split, max_new, temperature)
            print(f"[gen] artifact={aid} in={n_in} out={n_out} finish={finish} "
                  f"{time.time()-t0:.1f}s", flush=True)
            return {
                "id": "chatcmpl-latent-" + uuid.uuid4().hex[:8],
                "object": "chat.completion", "created": int(time.time()),
                "model": body.get("model", "latent-qwen"),
                "choices": [{"index": 0, "finish_reason": finish,
                             "logprobs": None,
                             "message": {"role": "assistant", "content": text}}],
                "usage": {"prompt_tokens": n_in, "completion_tokens": n_out,
                          "total_tokens": n_in + n_out},
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JSONResponse(status_code=500,
                                content={"error": {"message": str(e),
                                                   "type": "latent_server"}})


@app.get("/health")
def health():
    return {"ok": model is not None,
            "gpu_mem_gb": round(torch.cuda.memory_allocated() / 1e9, 1),
            "sessions": list(SESSIONS.keys()),
            "full_layers": FULL_LAYERS}


if __name__ == "__main__":
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8802)
    args = ap.parse_args()
    load_model()
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")
