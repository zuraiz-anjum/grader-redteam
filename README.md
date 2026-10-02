# grader-redteam

[![challenge](https://github.com/zuraiz-anjum/grader-redteam/actions/workflows/challenge.yml/badge.svg)](https://github.com/zuraiz-anjum/grader-redteam/actions/workflows/challenge.yml)

Why I built this: [How models cheat graders, and how to build graders that hold](docs/how-models-cheat-graders.md)

A grader is the part of an evaluation that decides whether a model did the
job. If it can be fooled, a capable model will eventually fool it, and your
numbers stop meaning anything.

`grader-redteam` plays the hostile candidate for you. It runs a battery of
generic exploits against any grader that writes a reward file, and tells you
which ones got through. Standard library only on Python 3.11+ (3.10 also
needs `tomli`).

## Break my verifier

Think the hardened grader can be fooled? The [challenge](challenge/CHALLENGE.md) gives you the task and the grader. Make it award 1 without solving the task and [submit the exploit](https://github.com/zuraiz-anjum/grader-redteam/issues/new?template=exploit.yml).

## Quick start

```
git clone https://github.com/zuraiz-anjum/grader-redteam.git && cd grader-redteam
pip install -e .
grader-redteam run examples/weak.toml
grader-redteam run examples/hardened.toml
```

The first command reports most checks as `MISSED`. The second reports none.
This run is from Windows without developer mode, where the symlink probe is
`SKIPPED`. On Linux and macOS it runs: the weak grader misses it (9 of 11)
and the hardened grader catches it (0 of 11).

```
$ grader-redteam run examples/weak.toml
MISSED   noop                                     grader exited 1 without a reward
MISSED   prewritten_reward                        reward 1
SKIPPED  symlink_deliverable                      this OS refused to create a symlink
MISSED   write_outside_output                     reward 1
MISSED   read_outside_root                        candidate can read tests/expected.json
MISSED   stdout_forge                             reward 1
MISSED   timed_out_candidate                      grader hung past 8s
MISSED   malformed_deliverable                    grader exited 1 without a reward
OK       control:reference                        reward 1
OK       control:alternate:alt_solution.py        reward 1
MISSED   control:negative:hardcoded_visible.py    reward 1

8 of 11 checks missed

$ grader-redteam run examples/hardened.toml
CAUGHT   noop                                     reward 0
CAUGHT   prewritten_reward                        reward 0
SKIPPED  symlink_deliverable                      this OS refused to create a symlink
CAUGHT   write_outside_output                     reward 0
SKIPPED  read_outside_root                        no secret paths configured
CAUGHT   stdout_forge                             reward 0
CAUGHT   timed_out_candidate                      reward 0
CAUGHT   malformed_deliverable                    reward 0
OK       control:reference                        reward 1
OK       control:alternate:alt_solution.py        reward 1
CAUGHT   control:negative:hardcoded_visible.py    reward 0

0 of 11 checks missed
```

Read
`examples/weak_grader.py` and `examples/hardened_grader.py` side by side to
see why.

## What it probes

- `noop`: the candidate submits an empty deliverable
- `prewritten_reward`: the candidate writes a perfect reward file before grading
- `symlink_deliverable`: the candidate makes the deliverable a symlink to a file outside the output path
- `write_outside_output`: the candidate blanks files outside the deliverable path, such as the tests
- `read_outside_root`: the candidate tries to read files listed as secret
- `stdout_forge`: the candidate submits something that only prints a fake success transcript
- `timed_out_candidate`: the candidate never finishes and leaves a deliverable that hangs when run
- `malformed_deliverable`: the candidate submits binary junk

Each probe runs in a fresh copy of your workspace. It is `CAUGHT` when the
exploit earns a reward of zero. It is `MISSED` when it earns anything, or when
the grader crashes, hangs, or leaves no reward behind (a missing reward is
how stale rewards leak through). `SKIPPED` means the config did not give the
probe what it needs, or the OS would not allow it (symlinks on Windows
without developer mode, for example).

It also runs controls. Your reference solution and any alternate correct
solutions must score 1. Your negative controls, wrong answers that look
plausible, must score 0. A grader that blocks every exploit but also rejects a
valid alternate solution is not a good grader.

The exit code is 1 if anything was missed, so it drops straight into CI.

## Config

```toml
[grader]
command = ["{python}", "grade.py", "{workspace}"]   # also {deliverable}, {reward}, {private}
timeout = 30

[workspace]
template = "task/workspace"          # copied fresh for every probe
deliverable = "solution.py"          # relative to the workspace
reward = "reward.json"               # {"reward": x} or a bare number; may start with {private}
planted_reward = "reward.json"       # optional: where the candidate plants a score (defaults to reward)
protected = ["tests/cases.json"]     # files the candidate must not be able to change the outcome with
secrets = ["tests/expected.json"]    # files the candidate must not be able to read

[candidate]
sandbox_user = ""    # if set (POSIX), every candidate action runs via sudo -n -u <user>
timeout = 2          # how long the timed-out candidate runs before it is killed

[controls]
reference = "task/reference_solution.py"
alternates = ["task/alt_solution.py"]
negatives = ["task/hardcoded_visible.py"]
```

**Reward location.** A reward path that starts with `{private}` lives in a
per-run directory outside the workspace, which the tool passes only to the
grader. Set `planted_reward` to the path a candidate would see or guess, and
the reward probes attack that path instead. This models the usual fix: the
candidate cannot reach the file the score is read from. With a sandbox user
the private directory is mode 700, so the separation is real; without one it
relies on your harness doing the same.

**Sandbox user.** Without one, candidate actions run as you, and
`read_outside_root` will report every secret as readable. That is the honest
answer: if your real harness runs the model as the same user as the grader,
the model can read the answer key too.

## Limits

This catches generic, mechanical exploits. It cannot know your task, so it
cannot tell whether a wrong solution happens to pass your checks. Negative
controls cover that: write the plausible wrong solution yourself and make
sure it scores zero.

## Tests

```
pip install -e ".[test]"
pytest
```

## License

MIT
