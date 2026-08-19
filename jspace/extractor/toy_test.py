"""Toy sanity test for the extraction service: the 'planned/considered words'
phenomenon. On a prompt where the model plainly knows an unspoken answer
(capital of France -> Paris), the L12 workspace readout at positions BEFORE the
answer would be said should surface Paris-ish tokens; since the assistant text
never says 'Paris', they must be starred (*) as SILENT.

Run against a live extractor:  python toy_test.py [url]
"""
import json
import sys
import urllib.request

url = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8398") + "/extract"

messages = [
    {"role": "user", "content": "What is the capital of France? Think about it "
                                "but do not say the city name yet."},
    {"role": "assistant", "content": "I know which city this is. It is a very "
                                     "famous European capital on the Seine, and I am "
                                     "confident about the answer to your question."},
]
req = urllib.request.Request(url, json.dumps({"messages": messages}).encode(),
                             {"Content-Type": "application/json"})
resp = json.load(urllib.request.urlopen(req, timeout=300))
print("META:", json.dumps(resp.get("meta", {}), indent=1))
entries = json.loads(resp["blurb"])
print(f"ENTRIES ({len(entries)}):")
for e in entries:
    print(f"  pos={e['pos']:>4}  ctx={e['context_token']!r:<14} ws={e['workspace']}")
hit = any("paris" in w.lower() for e in entries for w in e["workspace"])
silent_hit = any("paris" in w.lower() and w.endswith("*")
                 for e in entries for w in e["workspace"])
print(f"\nPARIS in workspace: {hit}   as SILENT: {silent_hit}")
print("TOY TEST", "PASS" if silent_hit else ("WEAK-PASS" if hit else "FAIL"))
