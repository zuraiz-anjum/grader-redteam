import os
from pathlib import Path

import pytest

from grader_redteam.config import load
from grader_redteam.probes import CAUGHT, MISSED, OK, SKIPPED, run_all

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

WEAK_MUST_MISS = {
    "noop",
    "prewritten_reward",
    "write_outside_output",
    "read_outside_root",
    "stdout_forge",
    "timed_out_candidate",
    "malformed_deliverable",
    "control:negative:hardcoded_visible.py",
}


@pytest.fixture(scope="module")
def weak():
    return {r.name: r for r in run_all(load(EXAMPLES / "weak.toml"))}


@pytest.fixture(scope="module")
def hardened():
    return {r.name: r for r in run_all(load(EXAMPLES / "hardened.toml"))}


@pytest.mark.parametrize("name", sorted(WEAK_MUST_MISS))
def test_weak_grader_misses(weak, name):
    assert weak[name].status == MISSED, weak[name]


posix_only = pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")


@posix_only
def test_weak_grader_misses_symlink(weak):
    assert weak["symlink_deliverable"].status == MISSED, weak["symlink_deliverable"]


@posix_only
def test_hardened_grader_catches_symlink(hardened):
    assert hardened["symlink_deliverable"].status == CAUGHT, hardened["symlink_deliverable"]


def test_weak_still_accepts_real_solutions(weak):
    assert weak["control:reference"].status == OK
    assert weak["control:alternate:alt_solution.py"].status == OK


def test_hardened_grader_misses_nothing(hardened):
    missed = [r for r in hardened.values() if r.status == MISSED]
    assert not missed, missed


def test_hardened_catches_every_probe_it_can_run(hardened):
    for name in WEAK_MUST_MISS - {"read_outside_root", "control:negative:hardcoded_visible.py"}:
        assert hardened[name].status == CAUGHT, hardened[name]
    assert hardened["control:negative:hardcoded_visible.py"].status == CAUGHT
    assert hardened["control:reference"].status == OK
    assert hardened["control:alternate:alt_solution.py"].status == OK
