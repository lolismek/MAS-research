"""Offline test of the per-session cap in harness/llm.py (no API calls): only this session's calls count, the cap
raises BudgetExceeded and writes the STOP file, and the shared-log hard cap is ignored inside a session."""
import importlib, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = r"""
import sys; sys.path.insert(0, %r)
import llm
llm.SESSION_DIR = %r
llm._log(dict(tag="x", backend="tinker", cost_usd=0.6))
llm.check_cap("a")                                   # 0.6 (+ 5.0 from another session, ignored) < 1.0
llm._log(dict(tag="x", backend="tinker", cost_usd=0.6))
try:
    llm.check_cap("b"); print("NO_RAISE")
except llm.BudgetExceeded as e: print("RAISED", e)
try:
    llm.check_cap("c"); print("NO_RAISE")
except llm.BudgetExceeded as e: print("RAISED_STOPFILE" if "stopped" in str(e) else "RAISED_OTHER")
"""

def test_session_cap():
    d = tempfile.mkdtemp()
    log = os.path.join(d, "calls.jsonl")
    with open(log, "w") as f:
        f.write(json.dumps(dict(tag="old", cost_usd=5.0)) + "\n")                       # untagged: another session
        f.write(json.dumps(dict(tag="other", cost_usd=5.0, session="someone-else")) + "\n")
    env = dict(os.environ, LIP_CALL_LOG=log, LIP_SESSION="t1", LIP_SESSION_CAP="1.0", LIP_HARD_CAP="1.0")
    out = subprocess.run([sys.executable, "-c", CODE % (os.path.join(HERE, "..", "harness"), d)], env=env,
                         capture_output=True, text=True).stdout.split("\n")
    assert out[0].startswith("RAISED session cap"), out     # hard cap (shared total 11.2 >= 1.0) did not fire first
    assert out[1] == "RAISED_STOPFILE", out
    assert os.path.exists(os.path.join(d, "t1.STOP"))
    recs = [json.loads(l) for l in open(log)]
    assert sum(r.get("session") == "t1" for r in recs) == 2

if __name__ == "__main__":
    test_session_cap(); print("ok")
