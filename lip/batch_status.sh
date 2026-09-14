#!/bin/zsh
# One status line: spend, per-arm progress and error counts, current stage.
cd /Users/alexjerpelea/MAS-memory-research
/Users/alexjerpelea/miniforge3/bin/python - <<'PY'
import json, glob, os, time
t=0.0; err=0; n=0; t10=time.time()-600; c10=0; e10=0
for l in open('lip/traces/calls.jsonl'):
    try: r=json.loads(l)
    except Exception: continue
    t+=r.get('cost_usd',0.0); n+=1
    if r.get('ts',0)>t10:
        c10+=1; e10+= (r.get('finish')=='error' or r.get('status')=='error')
def arm(a):
    fs=glob.glob(f'lip/traces/{a}/*/run_*/run.json'); ok=er=cor=0
    for p in fs:
        try: r=json.load(open(p))
        except Exception: continue
        if r.get('error'): er+=1
        else: ok+=1; cor+=bool(r.get('correct'))
    return f'{a} {ok}/465 done ({cor} correct, {er} errored)'
inj=len(glob.glob('lip/traces/inj/*/oracle.json')); injr=len(glob.glob('lip/traces/inj/*/*/run_*/run.json'))
st=[l.strip() for l in open('lip/traces/batch/batch.log')][-1] if os.path.exists('lip/traces/batch/batch.log') else '-'
print(f'spend ${t:.2f} | last10min {c10} calls, {e10} errors | {arm("relay")} | {arm("ceiling")} | inj {inj} oracles, {injr} runs | stage: {st[:90]}')
PY
