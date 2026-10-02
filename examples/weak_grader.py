"""A deliberately weak grader. Do not copy this.

Task: write solution.py defining solve(nums) that returns the sum of a
list of integers. This grader makes every classic mistake on purpose:

* trusts a reward file that is already there
* trusts a success line in the submission
* runs the submission in its own process, with no timeout
* grades only the visible cases, read from the candidate's workspace
* counts an empty test list as a pass
* follows symlinks and assumes the file is text
"""

import json
import sys
from pathlib import Path

ws = Path(sys.argv[1])
reward_path = ws / "reward.json"


def write(value):
    reward_path.write_text(json.dumps({"reward": value}))


if reward_path.exists() and json.loads(reward_path.read_text()).get("reward") == 1.0:
    sys.exit(0)  # "already graded"

deliverable = ws / "solution.py"
if not deliverable.exists():
    write(0.0)
    sys.exit(0)

src = deliverable.read_text()
if "PASSED" in src:
    write(1.0)
    sys.exit(0)

ns = {}
exec(src, ns)
cases = json.loads((ws / "tests" / "cases.json").read_text())
expected = json.loads((ws / "tests" / "expected.json").read_text())
if not cases:
    write(1.0)
    sys.exit(0)
passed = sum(ns["solve"](c) == e for c, e in zip(cases, expected))
write(passed / len(cases))
