"""Latent-channel coherence smoke (run ON tigerfish, server on :8802).

  /tmp/aij2115/latentenv/bin/python smoke_latent.py

1. Prefill a synthetic A-transcript containing three PLANTED FACTS that only
   exist in that transcript, build KV artifacts (last-n / rand), and ask B —
   whose PROMPT never mentions the facts — to describe what its predecessor
   was doing. KV coherence bar: fluent text; KV signal bar: any planted fact
   surfaces with lkv but not with no-artifact control.
2. Same for m=8 coconut thoughts (+ collapse metrics from the aux) and the
   pooled-embedding variant.

Prints a PASS/INFO line per check; exits nonzero on server errors only
(informational failures are data, not bugs).
"""
import json

import requests

BASE = "http://localhost:8802"
FACTS = ["the bug is in the file warehouse/loader.py",
         "the function parse_manifest drops the last line of every manifest",
         "the failing test is tests/test_manifest.py::test_trailing_newline"]

A_MESSAGES = [
    {"role": "system", "content":
     "You are a software engineer fixing a failing test in a Python repository."},
    {"role": "user", "content":
     "The test suite fails. Investigate and fix it."},
    {"role": "assistant", "content":
     "I ran the tests and found that " + FACTS[2] + " fails. Let me look at the code."},
    {"role": "user", "content": "Continue."},
    {"role": "assistant", "content":
     "I found the cause: " + FACTS[0] + ", where " + FACTS[1] +
     ". I have not written the fix yet; the next step is to patch parse_manifest "
     "to keep trailing content."},
]

B_MESSAGES_TMPL = [
    {"role": "system", "content":
     "You are a software engineer taking over a task from a colleague.{marker}"},
    {"role": "user", "content":
     "Before you start: describe, as concretely as you can, what your "
     "predecessor was working on and what they had found. If you genuinely "
     "have no information, say so."},
]


def post(path, body):
    r = requests.post(BASE + path, json=body, timeout=3600)
    r.raise_for_status()
    return r.json()


def bmsgs(marker):
    m = ("\n\n--- HANDOFF NOTE ---\n" + marker +
         "\n(Attached to this note is your predecessor's working memory in a "
         "latent, non-textual form. You cannot read it as text, but it may "
         "prime what you recall about this task.)\n--- END NOTE ---") if marker else ""
    return [{"role": s["role"], "content": s["content"].format(marker=m)
             if "{marker}" in s["content"] else s["content"]}
            for s in B_MESSAGES_TMPL]


def gen(marker):
    r = post("/v1/chat/completions",
             {"messages": bmsgs(marker), "max_tokens": 1200, "temperature": 0.0})
    return r["choices"][0]["message"]["content"] or ""


def facts_hit(text):
    keys = ["loader.py", "parse_manifest", "test_trailing_newline",
            "manifest", "warehouse"]
    t = text.lower()
    return [k for k in keys if k.lower() in t]


def main():
    print("== prefill A transcript")
    s = post("/prefill_capture", {"messages": A_MESSAGES})
    sid, T = s["session_id"], s["n_tokens"]
    print(f"   session {sid}, {T} tokens")

    arts = {}
    n = min(120, T)
    arts["lkv"] = post("/make_artifact", {"arm": "kv_last", "session_id": sid,
                                          "params": {"n": n},
                                          "artifact_id": "smoke_lkv"})
    arts["lkv_rand"] = post("/make_artifact", {"arm": "kv_rand", "session_id": sid,
                                               "params": {"n": n, "seed": 7},
                                               "artifact_id": "smoke_lkv_rand"})
    arts["lkv_full"] = post("/make_artifact", {"arm": "kv_last", "session_id": sid,
                                               "params": {"n": T},
                                               "artifact_id": "smoke_lkv_full"})

    print("== prefill thought session (with summary request)")
    s2 = post("/prefill_capture", {
        "messages": A_MESSAGES + [{"role": "user", "content":
                                   "Time is up. Summarize everything useful you "
                                   "established for the worker taking over."}],
        "add_generation_prompt": True})
    arts["lthought"] = post("/make_artifact",
                            {"arm": "thought_coconut", "session_id": s2["session_id"],
                             "params": {"m": 8, "rescale": True},
                             "artifact_id": "smoke_lthought"})
    print("   coconut norms:", arts["lthought"].get("hidden_norms"))
    print("   consec cos sim:", arts["lthought"].get("consec_cos_sim"))
    arts["lthought_rand"] = post("/make_artifact",
                                 {"arm": "thought_rand",
                                  "params": {"ref_artifact_id": "smoke_lthought",
                                             "seed": 7},
                                  "artifact_id": "smoke_lthought_rand"})
    note = ("Predecessor's note: " + FACTS[2] + " fails because " + FACTS[0] +
            "; " + FACTS[1] + ". Fix parse_manifest to keep trailing content.")
    arts["lthought_pool"] = post("/make_artifact",
                                 {"arm": "thought_pool",
                                  "params": {"m": 8, "text": note},
                                  "artifact_id": "smoke_lthought_pool"})

    results = {}
    for name, marker in [
            ("control_none", None),
            ("lkv", "[[LATENT:kv:smoke_lkv]]"),
            ("lkv_full", "[[LATENT:kv:smoke_lkv_full]]"),
            ("lkv_rand", "[[LATENT:kv:smoke_lkv_rand]]"),
            ("lthought", "[[LATENT:embeds:smoke_lthought]]"),
            ("lthought_rand", "[[LATENT:embeds:smoke_lthought_rand]]"),
            ("lthought_pool", "[[LATENT:embeds:smoke_lthought_pool]]")]:
        text = gen(marker)
        hits = facts_hit(text)
        fluent = len(text.strip()) > 40
        results[name] = {"hits": hits, "chars": len(text)}
        print(f"== {name}: fluent={fluent} fact_hits={hits}")
        print("   " + text[-400:].replace("\n", "\n   "))
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
