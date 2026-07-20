"""Post-rescale-fix focused recheck of L-THOUGHT transmission (see
smoke_latent.py for the full battery). Run on tigerfish."""
import time

from smoke_latent import A_MESSAGES, facts_hit, gen, post


def main():
    s2 = post("/prefill_capture", {
        "messages": A_MESSAGES + [{"role": "user", "content":
                                   "Time is up. Summarize everything useful you "
                                   "established for the worker taking over."}],
        "add_generation_prompt": True})
    aux = post("/make_artifact",
               {"arm": "thought_coconut", "session_id": s2["session_id"],
                "params": {"m": 8, "rescale": True},
                "artifact_id": "smoke_lthought_v2"})
    print("norms:", aux.get("hidden_norms"))
    print("cos:", aux.get("consec_cos_sim"))
    t0 = time.time()
    text = gen("[[LATENT:embeds:smoke_lthought_v2]]")
    print(f"gen {time.time()-t0:.0f}s, {len(text)} chars")
    print("fact_hits:", facts_hit(text))
    print(text[-500:])


if __name__ == "__main__":
    main()
