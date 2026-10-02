"""A hardened grader for the same toy task: solve(nums) returns the sum.

What it does differently from weak_grader.py:

* writes the reward once, at the end, atomically, and only to a path the
  harness passes in, outside the candidate's workspace, so nothing the candidate leaves behind can reach it
* refuses symlinks, oversized files and anything that is not UTF-8
* ignores everything in the workspace except the deliverable: the visible
  tests there are for the candidate, not for grading
* generates fresh held-out cases at grade time and compares by value
* runs the submission in a separate process with a timeout, collects its
  return values as data and checks them against answers it computed itself;
  stdout is discarded, so printed text never decides the score
"""

import json
import os
import random
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_BYTES = 64 * 1024
TIMEOUT = 5

RUNNER = r'''
import json, sys
req = json.loads(sys.stdin.readline())
ns = {"__name__": "solution"}
exec(open("solution.py", encoding="utf-8").read(), ns)
out = [ns["solve"](list(c)) for c in req["cases"]]
with open(req["out"], "w", encoding="utf-8") as f:
    json.dump(out, f)
'''

ws = Path(sys.argv[1])
reward_path = Path(sys.argv[2])


def write(value):
    """Write the reward once, atomically, never through a symlink."""
    tmp = reward_path.with_name(reward_path.name + ".tmp")
    for p in (reward_path, tmp):
        if p.is_symlink():
            p.unlink()
    tmp.write_text(json.dumps({"reward": value}))
    os.replace(tmp, reward_path)


def fail():
    write(0.0)
    sys.exit(0)


deliverable = ws / "solution.py"
if deliverable.is_symlink() or not deliverable.is_file():
    fail()
raw = deliverable.read_bytes()
if not raw or len(raw) > MAX_BYTES:
    fail()
try:
    raw.decode("utf-8")
except UnicodeDecodeError:
    fail()

rng = random.Random(secrets.randbits(64))
cases = [[rng.randint(-10**6, 10**6) for _ in range(rng.randint(0, 40))] for _ in range(25)]
expected = [sum(c) for c in cases]

box = Path(tempfile.mkdtemp(prefix="grade-"))
try:
    (box / "solution.py").write_bytes(raw)
    (box / "runner.py").write_text(RUNNER)
    out_path = box / ("out-" + secrets.token_hex(8) + ".json")
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "runner.py"],
            cwd=box,
            input=json.dumps({"cases": cases, "out": str(out_path)}) + "\n",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        fail()
    if proc.returncode != 0 or out_path.is_symlink() or not out_path.is_file():
        fail()
    try:
        got = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        fail()
finally:
    shutil.rmtree(box, ignore_errors=True)

if not isinstance(got, list) or len(got) != len(expected):
    fail()
correct = all(type(g) is int and g == e for g, e in zip(got, expected))
write(1.0 if correct else 0.0)
