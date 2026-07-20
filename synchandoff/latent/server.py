"""Latent handoff server v2 — tigerfish side (one GPU, plain HF transformers).

v2 (2026-07-20): model = Qwen/Qwen3-8B, dense bf16, STOCK from_pretrained (no
AWQ loader — awq_moe.py is the archived v1 path for the hybrid 35B). Every
layer is full-attention GQA+RoPE, so KV arms cover all 36 layers. Thinking is
disabled at the template (enable_thinking=False), matching the vLLM stack's
baked no-think template for byte parity.

Endpoints:
  POST /prefill_capture   deterministic prefill of a message list / raw text;
                          caches the live cache + optional residual-stream
                          hidden states server-side under a session id. Also
                          always captures the q-projection of the last QTAIL
                          positions per layer (cheap; powers kv_attn).
  POST /make_artifact     kv_last / kv_positions / kv_rand / kv_attn (L-KV),
                          thought_soft / thought_align / thought_coconut /
                          thought_pool / thought_rand (L-THOUGHT).
                          Persists to LATENT_ART_DIR as .pt+.json.
  POST /probe_score       score every position of a captured layer with a
                          linear probe (coef/mu/sd/intercept in the request),
                          NMS peak-pick, return peaks + decoded text windows.
                          Powers the L-PROBE v2 belief-strength pipeline.
  POST /generate          (also /v1/chat/completions) OpenAI-style chat
                          completion with optional latent injection.
  POST /session_free      drop a session (GPU memory).
  GET  /health

Marker protocol, RoPE/positions scheme (keys keep their ORIGINAL rotations
and absolute positions; B starts at T; non-contiguous selections need no
re-rotation) are unchanged from v1 — see git history of this file for the
hybrid-35B version and its design notes.
"""
import argparse
import copy
import json
import math
import os
import re
import threading
import time
import uuid

import torch
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.cache_utils import DynamicCache

MODEL_DIR = os.environ.get(
    "LATENT_MODEL_DIR",
    "/tmp/aij2115/cache/hf/hub/models--Qwen--Qwen3-8B/snapshots/"
    "b968826d9c46dd6066d109eabc6255188de91218")
ART_DIR = os.environ.get("LATENT_ART_DIR", "/tmp/aij2115/latent_artifacts")
MAX_SESSIONS = 2
PREFILL_CHUNK = 8192
QTAIL = 64                       # tail queries captured for kv_attn scoring
MAX_NEW_DEFAULT = 8000           # no-think: match the 8B text proxy cap
DTYPE = torch.bfloat16
MARKER_RE = re.compile(r"\[\[LATENT:(kv|embeds):([A-Za-z0-9_\-\.]+)\]\]")

app = FastAPI()
GPU_LOCK = threading.Lock()      # one request touches the GPU at a time

tok = None
model = None
txt = None                       # the decoder stack (model.model)
lm_head = None
FULL_LAYERS = []
TEXT_CFG = None


# ------------------------------------------------------------- model load ----
def load_model():
    global tok, model, txt, lm_head, FULL_LAYERS, TEXT_CFG
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR, dtype=DTYPE, device_map="cuda:0")
    model.eval()
    txt = model.model
    lm_head = model.lm_head
    TEXT_CFG = txt.config
    lt = getattr(TEXT_CFG, "layer_types", None)
    if lt:
        FULL_LAYERS = [i for i, t in enumerate(lt) if t == "full_attention"]
    else:
        FULL_LAYERS = list(range(TEXT_CFG.num_hidden_layers))
    os.makedirs(ART_DIR, exist_ok=True)
    print(f"model loaded in {time.time()-t0:.0f}s; {len(FULL_LAYERS)} "
          f"full-attn layers; dtype={DTYPE}", flush=True)


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
        add_generation_prompt=add_generation_prompt, enable_thinking=False)


def message_boundaries(messages, tools=None):
    """Token index of the END of each message in the templated sequence."""
    try:
        norm = normalize_messages(messages)
        full = tok.apply_chat_template(norm, tools=tools or None, tokenize=False,
                                       add_generation_prompt=False,
                                       enable_thinking=False)
        out = []
        for i in range(1, len(norm) + 1):
            pref = tok.apply_chat_template(norm[:i], tools=tools or None,
                                           tokenize=False,
                                           add_generation_prompt=False,
                                           enable_thinking=False)
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
    out = {}
    for i in FULL_LAYERS:
        lay = cache.layers[i]
        k, v = getattr(lay, "keys", None), getattr(lay, "values", None)
        if k is None:
            continue
        out[i] = (k, v)
    return out


def seed_cache_kv(cache, kv_dict, linear_dict=None):
    for i, (k, v) in kv_dict.items():
        cache.layers[i].update(k.to("cuda:0", DTYPE), v.to("cuda:0", DTYPE))
    # linear_dict: v1 hybrid-only, ignored on the dense model


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


class QTailTap:
    """Hooks on every layer's q_proj keeping the LAST `tail` rows seen —
    the pre-norm pre-RoPE queries of the final positions, for kv_attn."""

    def __init__(self, tail=QTAIL):
        self.tail = tail
        self.data = {}
        self.handles = []
        for i in FULL_LAYERS:
            self.handles.append(
                txt.layers[i].self_attn.q_proj.register_forward_hook(
                    self._make_hook(i)))

    def _make_hook(self, i):
        def hook(_mod, _inp, out):
            q = out.detach()[0].to("cpu")          # [chunk, n_heads*hd]
            prev = self.data.get(i)
            q = q if prev is None else torch.cat([prev, q], dim=0)
            self.data[i] = q[-self.tail:]
        return hook

    def close(self):
        for h in self.handles:
            h.remove()
        return self.data


@torch.inference_mode()
def chunked_prefill(input_ids, capture_layers=None):
    """Prefill input_ids [1,T] in chunks with a live cache. Returns
    (cache, hidden_dict, last_hidden_vec, qtail_dict)."""
    cache = new_cache()
    tap = HiddenTap(capture_layers) if capture_layers else None
    qtap = QTailTap()
    T = input_ids.shape[1]
    last_hidden = None
    for s in range(0, T, PREFILL_CHUNK):
        chunk = input_ids[:, s:s + PREFILL_CHUNK].to("cuda:0")
        out = txt(input_ids=chunk, past_key_values=cache, use_cache=True)
        cache = out.past_key_values
        last_hidden = out.last_hidden_state[0, -1].clone()
    hidden = tap.close() if tap else {}
    qtail = qtap.close()
    return cache, hidden, last_hidden, qtail


# ------------------------------------------------------------ session store ----
SESSIONS = {}


def evict_sessions():
    while len(SESSIONS) > MAX_SESSIONS:
        oldest = min(SESSIONS, key=lambda s: SESSIONS[s]["created"])
        SESSIONS.pop(oldest, None)
    torch.cuda.empty_cache()


@torch.inference_mode()
def _entropy_of(h):
    logits = lm_head(h.to("cuda:0", DTYPE)).float()
    p = torch.softmax(logits, dim=-1)
    return float(-(p * torch.log(p + 1e-12)).sum())


@app.post("/prefill_capture")
def prefill_capture(body: dict):
    """body: messages | raw_text, tools?, add_generation_prompt (default
    False), capture_layers [ints], session_id?, return_entropy?, return_hidden?
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
        cache, hidden, last_hidden, qtail = chunked_prefill(ids, capture_layers)
        emb = txt.embed_tokens(ids[:, -256:].to("cuda:0"))
        emb_norm = float(emb[0].norm(dim=-1).mean())
        SESSIONS[sid] = {"cache": cache, "n_tokens": T, "ids": ids,
                         "hidden": hidden, "last_hidden": last_hidden,
                         "qtail": qtail, "boundaries": boundaries,
                         "emb_norm": emb_norm, "created": time.time()}
        evict_sessions()
        resp = {"session_id": sid, "n_tokens": T, "boundaries": boundaries,
                "emb_norm": emb_norm, "dur_s": round(time.time() - t0, 1)}
        if body.get("return_entropy"):
            resp["last_entropy"] = round(_entropy_of(last_hidden), 4)
        rh = body.get("return_hidden")
        if rh:
            resp["hidden"] = _hidden_slice(SESSIONS[sid], rh)
        return resp


def _resolve_positions(sess, spec):
    if isinstance(spec, list):
        return [p if p >= 0 else sess["n_tokens"] + p
                for p in spec if -sess["n_tokens"] <= p < sess["n_tokens"]]
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
def _bit_ledger_kv(n):
    kv_heads = TEXT_CFG.num_key_value_heads
    hd = getattr(TEXT_CFG, "head_dim", TEXT_CFG.hidden_size // TEXT_CFG.num_attention_heads)
    b = n * len(FULL_LAYERS) * 2 * kv_heads * hd * 2
    return {"kv_bytes": b, "linear_state_bytes": 0, "total_bytes": b}


def _save_artifact(aid, kind, tensors, aux):
    torch.save({"kind": kind, **tensors}, os.path.join(ART_DIR, aid + ".pt"))
    aux = {"artifact_id": aid, "kind": kind, "created": time.time(), **aux}
    with open(os.path.join(ART_DIR, aid + ".json"), "w") as f:
        json.dump(aux, f, indent=1)
    return aux


def _load_artifact(aid):
    return torch.load(os.path.join(ART_DIR, aid + ".pt"),
                      map_location="cpu", weights_only=False)


def _kv_artifact(sess, positions, aid, note="", extra_aux=None):
    cache = sess["cache"]
    T = sess["n_tokens"]
    pos = torch.tensor(sorted(set(int(p) for p in positions)), dtype=torch.long)
    kv = {}
    for i, (k, v) in cache_kv(cache).items():
        kv[i] = (k[:, :, pos, :].to("cpu", DTYPE).clone(),
                 v[:, :, pos, :].to("cpu", DTYPE).clone())
    tensors = {"kv": kv, "linear": None, "positions": pos, "orig_len": T}
    aux = {"n_slots": len(pos), "slot_unit": "kv_position",
           "orig_ctx_len": T, "positions_head": pos[:8].tolist(),
           "contiguous": bool((pos[1:] - pos[:-1] == 1).all()) if len(pos) > 1 else True,
           "bit_ledger": _bit_ledger_kv(len(pos)), "note": note}
    if extra_aux:
        aux.update(extra_aux)
    return _save_artifact(aid, "kv", tensors, aux)


# ---- kv_attn: attention-mass position scoring (training-free, KVComm-ish) ----
def _rotate_half(x):
    x1 = x[..., : x.shape[-1] // 2]
    x2 = x[..., x.shape[-1] // 2:]
    return torch.cat((-x2, x1), dim=-1)


@torch.inference_mode()
def attn_scores(sess):
    """Score every position of the session by accumulated attention mass from
    the last QTAIL queries, averaged over layers and heads. Returns a float32
    CPU tensor [T]. Queries are rebuilt from the captured q_proj outputs
    (q_norm + RoPE applied here, matching Qwen3Attention)."""
    T = sess["n_tokens"]
    qtail = sess["qtail"]
    cache = sess["cache"]
    n_heads = TEXT_CFG.num_attention_heads
    kv_heads = TEXT_CFG.num_key_value_heads
    hd = getattr(TEXT_CFG, "head_dim", TEXT_CFG.hidden_size // n_heads)
    rep = n_heads // kv_heads
    any_q = next(iter(qtail.values()))
    t_tail = any_q.shape[0]
    pos_ids = torch.arange(T - t_tail, T, device="cuda:0")[None]
    # rotary_emb signature: (x, position_ids) -> cos, sin  [1, t, hd]
    dummy = torch.zeros(1, t_tail, hd, device="cuda:0", dtype=DTYPE)
    cos, sin = txt.rotary_emb(dummy, pos_ids)
    cos = cos[0].float()                                    # [t, hd]
    sin = sin[0].float()
    # causal mask: query row j has absolute position T - t_tail + j
    qpos = torch.arange(T - t_tail, T, device="cuda:0")
    kpos = torch.arange(T, device="cuda:0")
    causal = (kpos[None, :] <= qpos[:, None])               # [t, T]
    total = torch.zeros(T, device="cuda:0")
    n_terms = 0
    for i in FULL_LAYERS:
        lay = cache.layers[i]
        k = getattr(lay, "keys", None)
        if k is None:
            continue
        attn_mod = txt.layers[i].self_attn
        q = qtail[i].to("cuda:0").view(t_tail, n_heads, hd)
        q = attn_mod.q_norm(q).float()                      # RMSNorm per head
        q = (q * cos[:, None, :]) + (_rotate_half(q) * sin[:, None, :])
        q = q.transpose(0, 1)                               # [H, t, hd]
        kk = k[0, :, :T, :].float()                          # [KVH, T, hd]
        kk = kk.repeat_interleave(rep, dim=0)                # [H, T, hd]
        s = torch.einsum("htd,hTd->htT", q, kk) / math.sqrt(hd)
        s = s.masked_fill(~causal[None], float("-inf"))
        a = torch.softmax(s, dim=-1)                         # [H, t, T]
        total += a.sum(dim=(0, 1))
        n_terms += n_heads * t_tail
        del s, a, kk, q
    torch.cuda.empty_cache()
    return (total / max(n_terms, 1)).to("cpu")


@torch.inference_mode()
def _latent_thought_loop(sess, m, mode, top_p=0.95, entropy_stop=1.0,
                         min_steps=4, temperature=1.0):
    """v2 latent-thought rollouts, continuing from the session's live cache
    (on a COPY). mode='soft': Soft-Thinking — feed the probability-weighted
    mixture of INPUT embeddings under the (top-p truncated) next-token
    distribution; entropy cold-stop after min_steps. mode='align':
    LatentMAS-style — full-softmax expected embedding, fixed m, no stop.
    mode='coconut': v1 raw-hidden recycling (kept for reference)."""
    cache = copy.deepcopy(sess["cache"])
    h = sess["last_hidden"].clone()
    emb_norm = sess["emb_norm"]
    emb_w = txt.embed_tokens.weight                          # [V, d]
    vecs, norms, sims, ents = [], [], [], []
    stop_reason = "cap"
    prev = None
    for step in range(m):
        if mode == "coconut":
            feed = (h * (emb_norm / h.norm())).to(DTYPE)
        else:
            logits = lm_head(h.to("cuda:0", DTYPE))[0] if h.dim() > 1 else \
                lm_head(h.to("cuda:0", DTYPE))
            logits = logits.float()
            p = torch.softmax(logits / temperature, dim=-1)
            ent = float(-(p * torch.log(p + 1e-12)).sum())
            ents.append(round(ent, 3))
            if mode == "soft" and step >= min_steps and ent < entropy_stop:
                stop_reason = "cold_stop"
                break
            if mode == "soft":
                sp, si = torch.sort(p, descending=True)
                keep = torch.cumsum(sp, 0) - sp < top_p      # keep until mass
                keep[0] = True
                idx = si[keep]
                w = p[idx] / p[idx].sum()
            else:                                            # align: full softmax
                idx = None
                w = p
            if idx is not None:
                feed = (w[:, None] * emb_w[idx].float()).sum(0).to(DTYPE)
            else:
                # full-softmax expectation without a fp32 copy of the whole
                # embedding table: accumulate in fp32 over row chunks
                acc = torch.zeros(emb_w.shape[1], device="cuda:0",
                                  dtype=torch.float32)
                for s0 in range(0, emb_w.shape[0], 16384):
                    blk = emb_w[s0:s0 + 16384].float()
                    acc += (w[s0:s0 + 16384, None] * blk).sum(0)
                feed = acc.to(DTYPE)
        vecs.append(feed.to("cpu").clone())
        norms.append(float(feed.float().norm()))
        if prev is not None:
            sims.append(float(torch.nn.functional.cosine_similarity(
                feed.float(), prev, dim=0)))
        prev = feed.float().clone()
        out = txt(inputs_embeds=feed[None, None, :].to("cuda:0", DTYPE),
                  past_key_values=cache, use_cache=True)
        cache = out.past_key_values
        h = out.last_hidden_state[0, -1].clone()
    del cache
    torch.cuda.empty_cache()
    return (torch.stack(vecs) if vecs else torch.zeros(0, TEXT_CFG.hidden_size)), \
        norms, sims, ents, stop_reason


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
                extra = None
                if arm == "kv_last":
                    positions = list(range(T - n, T))
                elif arm == "kv_positions":
                    positions = p["positions"]
                elif arm == "kv_rand":
                    g = torch.Generator().manual_seed(int(p.get("seed", 0)))
                    positions = torch.randperm(T, generator=g)[:n].tolist()
                else:                                        # kv_attn
                    scores = attn_scores(sess)
                    positions = torch.topk(scores, n).indices.tolist()
                    ssort = torch.sort(scores, descending=True).values
                    extra = {"selection": "attn_mass_tail%d" % QTAIL,
                             "score_mass_selected": round(float(
                                 ssort[:n].sum() / scores.sum()), 4),
                             "score_top8": [round(float(x), 6)
                                            for x in ssort[:8]]}
                aux = _kv_artifact(sess, positions, aid, note=p.get("note", ""),
                                   extra_aux=extra)
                return aux
            if arm in ("thought_soft", "thought_align", "thought_coconut"):
                if sess is None:
                    return JSONResponse(status_code=400,
                                        content={"error": "unknown session"})
                mode = arm.split("_", 1)[1]
                m = int(p.get("m", 32))
                vecs, norms, sims, ents, stop = _latent_thought_loop(
                    sess, m, mode, top_p=float(p.get("top_p", 0.95)),
                    entropy_stop=float(p.get("entropy_stop", 1.0)),
                    min_steps=int(p.get("min_steps", 4)))
                aux = {"n_slots": int(vecs.shape[0]),
                       "slot_unit": "latent_vector",
                       "bit_ledger": {"total_bytes": vecs.numel() * 2},
                       "mode": mode, "stop_reason": stop,
                       "vec_norms": [round(x, 1) for x in norms],
                       "consec_cos_sim": [round(x, 3) for x in sims],
                       "step_entropies": ents,
                       "emb_norm": sess["emb_norm"],
                       "orig_ctx_len": sess["n_tokens"]}
                return _save_artifact(aid, "embeds",
                                      {"vectors": vecs.to(torch.float16)}, aux)
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


# ------------------------------------------------------- probe scoring ----
@app.post("/probe_score")
def probe_score(body: dict):
    """Score all captured positions of one layer with a linear probe and
    return NMS peaks + decoded ±window text. body:
      {session_id, layer, coef, mu, sd, intercept,
       n_peaks (6), min_sep (300), window (150),
       positions? (explicit peak override, e.g. lprobe_randsel),
       return_curve? (bool, stride-subsampled)}"""
    with GPU_LOCK:
        try:
            import numpy as np
            sess = SESSIONS.get(body.get("session_id") or "")
            if sess is None:
                return JSONResponse(status_code=400,
                                    content={"error": "unknown session"})
            layer = int(body["layer"])
            h = sess["hidden"].get(layer)
            if h is None:
                return JSONResponse(status_code=400,
                                    content={"error": f"layer {layer} not captured"})
            X = h.float().numpy()
            mu = np.asarray(body["mu"], dtype=np.float32)
            sd = np.asarray(body["sd"], dtype=np.float32)
            coef = np.asarray(body["coef"], dtype=np.float32)
            z = ((X - mu) / sd) @ coef + float(body.get("intercept", 0.0))
            s = 1.0 / (1.0 + np.exp(-z))                    # [T]
            T = len(s)
            n_peaks = int(body.get("n_peaks", 6))
            min_sep = int(body.get("min_sep", 300))
            window = int(body.get("window", 150))
            if body.get("positions"):
                peaks = [int(p) for p in body["positions"] if 0 <= p < T]
            else:
                order = np.argsort(-s)
                peaks = []
                for p in order:
                    if len(peaks) >= n_peaks:
                        break
                    if all(abs(int(p) - q) >= min_sep for q in peaks):
                        peaks.append(int(p))
                peaks.sort()
            ids = sess["ids"][0]
            windows = []
            for p in peaks:
                lo, hi = max(0, p - window), min(T, p + window)
                windows.append({
                    "pos": p, "score": round(float(s[p]), 4),
                    "text": tok.decode(ids[lo:hi], skip_special_tokens=False)})
            resp = {"n_tokens": T, "layer": layer,
                    "curve_mean": round(float(s.mean()), 4),
                    "curve_std": round(float(s.std()), 4),
                    "curve_q90": round(float(np.quantile(s, 0.9)), 4),
                    "peaks": [{"pos": w["pos"], "score": w["score"]}
                              for w in windows],
                    "windows": windows}
            if body.get("return_curve"):
                stride = max(1, T // 4000)
                resp["curve"] = [round(float(x), 4) for x in s[::stride]]
                resp["curve_stride"] = stride
            return resp
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
    right) prompt halves for embeds splice."""
    cache = new_cache()
    pos0 = 0          # rotary position of the first prompt token
    cache_len = 0     # physical slots already in the cache
    if artifact and artifact["kind"] == "kv":
        kv = {i: (k, v) for i, (k, v) in artifact["kv"].items()}
        seed_cache_kv(cache, kv)
        n_prefix = artifact["positions"].shape[0]
        pos0 = int(artifact["orig_len"])
        cache_len = n_prefix

    if artifact and artifact["kind"] == "embeds":
        left, right = marker_split if marker_split else ("", prompt_text)
        el = txt.embed_tokens(tok(left, return_tensors="pt",
                                  add_special_tokens=False).input_ids.to("cuda:0"))
        er = txt.embed_tokens(tok(right, return_tensors="pt",
                                  add_special_tokens=False).input_ids.to("cuda:0"))
        lat = artifact["vectors"].to("cuda:0", DTYPE)[None]
        embeds = torch.cat([el, lat, er], dim=1)
        n_prompt = embeds.shape[1]
        feed = {"inputs_embeds": embeds}
    else:
        ids = tok(prompt_text, return_tensors="pt",
                  add_special_tokens=False).input_ids.to("cuda:0")
        n_prompt = ids.shape[1]
        feed = {"input_ids": ids}

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
            "model": MODEL_DIR.rsplit("/", 3)[-3] if model else None,
            "gpu_mem_gb": round(torch.cuda.memory_allocated() / 1e9, 1),
            "sessions": list(SESSIONS.keys()),
            "n_full_layers": len(FULL_LAYERS)}


if __name__ == "__main__":
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8802)
    args = ap.parse_args()
    load_model()
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")
