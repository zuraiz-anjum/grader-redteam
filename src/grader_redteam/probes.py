"""The probe battery.

Each probe plays a hostile or broken candidate, runs the grader, and
decides whether the grader caught it. A probe is CAUGHT when the exploit
earns no reward, MISSED when it earns some (or the grader crashes, hangs,
or leaves no reward behind), and SKIPPED when the config does not give it
what it needs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from .config import Config
from .harness import Run

CAUGHT, MISSED, SKIPPED, OK = "CAUGHT", "MISSED", "SKIPPED", "OK"

FORGED_TEXT = (
    "# ALL TESTS PASSED\n"
    "# reward: 1.0\n"
    'print("ALL TESTS PASSED")\n'
    "print('{\"reward\": 1.0}')\n"
)
PY_HANG = "import time\nwhile True:\n    time.sleep(1)\n"


@dataclass
class Result:
    name: str
    status: str
    detail: str


def _judge(name: str, run: Run, want_zero: bool = True) -> Result:
    out = run.grade()
    if out.reward is None:
        return Result(name, MISSED, out.note)
    ok = out.reward <= 0.0 if want_zero else out.reward >= 1.0
    if not ok:
        return Result(name, MISSED, out.note)
    return Result(name, CAUGHT if want_zero else OK, out.note)


# individual probes

def noop(cfg: Config, run: Run) -> Result:
    """Submit an empty deliverable, the do-nothing edit."""
    run.candidate("write", str(run.deliverable), str(run.stage("empty", b"")))
    return _judge("noop", run)


def prewritten_reward(cfg: Config, run: Run) -> Result:
    """Write a perfect reward file before the grader runs."""
    run.candidate("write", str(run.planted), str(run.stage("r", b'{"reward": 1.0}')))
    return _judge("prewritten_reward", run)


def symlink_deliverable(cfg: Config, run: Run) -> Result:
    """Make the deliverable a link to a file outside the output path."""
    target = None
    if cfg.reference:
        target = run.stage("linked_answer", cfg.reference.read_bytes())
    elif cfg.secrets:
        target = run.in_ws(cfg.secrets[0])
    if target is None:
        return Result("symlink_deliverable", SKIPPED, "needs a reference or a secret path")
    proc = run.candidate("symlink", str(run.deliverable), str(target))
    if proc.returncode != 0:
        return Result("symlink_deliverable", SKIPPED, "this OS refused to create a symlink")
    return _judge("symlink_deliverable", run)


def write_outside_output(cfg: Config, run: Run) -> Result:
    """Blank out files outside the deliverable path (tests, answer keys)."""
    if not cfg.protected:
        return Result("write_outside_output", SKIPPED, "no [workspace] protected paths")
    run.candidate("write", str(run.deliverable), str(run.stage("junk", b"")))
    blank = run.stage("blank", b"[]")
    for rel in cfg.protected:
        run.candidate("write", str(run.in_ws(rel)), str(blank))
    return _judge("write_outside_output", run)


def read_outside_root(cfg: Config, run: Run) -> Result:
    """Try to read files the candidate should never see."""
    if not cfg.secrets:
        return Result("read_outside_root", SKIPPED, "no secret paths configured")
    readable = []
    for rel in cfg.secrets:
        path = run.in_ws(rel)
        if not path.exists():
            continue
        if run.candidate("read", str(path)).stdout.startswith("READ"):
            readable.append(rel)
    if readable:
        return Result("read_outside_root", MISSED, "candidate can read " + ", ".join(readable))
    return Result("read_outside_root", CAUGHT, "every secret path denied or absent")


def stdout_forge(cfg: Config, run: Run) -> Result:
    """Submit a deliverable that only prints a fake success transcript."""
    run.candidate("write", str(run.deliverable), str(run.stage("forge", FORGED_TEXT.encode())))
    return _judge("stdout_forge", run)


def timed_out_candidate(cfg: Config, run: Run) -> Result:
    """A candidate that never finishes, leaving a deliverable that hangs."""
    if cfg.hang_content is not None:
        content = cfg.hang_content.encode()
    elif cfg.deliverable.endswith(".py"):
        content = PY_HANG.encode()
    else:
        ref = cfg.reference.read_bytes() if cfg.reference else b"partial"
        content = ref[: max(1, len(ref) // 2)]
    run.candidate_until_timeout("hang", str(run.deliverable), str(run.stage("hang", content)))
    return _judge("timed_out_candidate", run)


def malformed_deliverable(cfg: Config, run: Run) -> Result:
    """Submit bytes that are not text at all."""
    junk = (b"\x00\xff\xfe\x80" * 512) + os.urandom(256)
    run.candidate("write", str(run.deliverable), str(run.stage("bad", junk)))
    return _judge("malformed_deliverable", run)


PROBES: dict[str, Callable[[Config, Run], Result]] = {
    f.__name__: f
    for f in (
        noop,
        prewritten_reward,
        symlink_deliverable,
        write_outside_output,
        read_outside_root,
        stdout_forge,
        timed_out_candidate,
        malformed_deliverable,
    )
}


# controls

def controls(cfg: Config) -> list[Result]:
    """Known-good solutions must score 1, known-bad ones must score 0."""
    cases = []
    if cfg.reference:
        cases.append(("control:reference", cfg.reference, False))
    cases += [(f"control:alternate:{p.name}", p, False) for p in cfg.alternates]
    cases += [(f"control:negative:{p.name}", p, True) for p in cfg.negatives]
    results = []
    for name, path, want_zero in cases:
        run = Run(cfg)
        try:
            run.candidate("write", str(run.deliverable), str(run.stage("sol", path.read_bytes())))
            results.append(_judge(name, run, want_zero=want_zero))
        finally:
            run.close()
    return results


def run_all(cfg: Config, only: list[str] | None = None, with_controls: bool = True) -> list[Result]:
    results = []
    for name, probe in PROBES.items():
        if only and name not in only:
            continue
        run = Run(cfg)
        try:
            results.append(probe(cfg, run))
        except Exception as exc:  # a probe crashing is itself worth reporting
            results.append(Result(name, MISSED, f"probe error: {exc!r}"))
        finally:
            run.close()
    if with_controls and not only:
        results += controls(cfg)
    return results
