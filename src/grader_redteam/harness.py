"""Workspace setup, candidate execution, grading and reward reading."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import candidate as _candidate_module
from .config import Config

CANDIDATE_SCRIPT = str(Path(_candidate_module.__file__).resolve())
IS_WINDOWS = os.name == "nt"


@dataclass
class GradeOutcome:
    reward: float | None
    note: str


class Run:
    """One isolated attempt: a fresh workspace, a candidate, a grader."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.root = Path(tempfile.mkdtemp(prefix="grt-"))
        self.ws = self.root / "workspace"
        self.private = self.root / "private"
        self.private.mkdir()
        if not IS_WINDOWS:
            os.chmod(self.private, 0o700)
        if cfg.template:
            shutil.copytree(cfg.template, self.ws)
        else:
            self.ws.mkdir()
        if cfg.sandbox_user and not IS_WINDOWS:
            subprocess.run(["chmod", "-R", "a+rwX", str(self.ws)], check=False)
            os.chmod(self.root, 0o755)

    # paths
    def in_ws(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else self.ws / p

    @property
    def deliverable(self) -> Path:
        return self.in_ws(self.cfg.deliverable)

    def resolve(self, rel: str) -> Path:
        """Workspace-relative path, or one under the private dir via {private}."""
        if rel.startswith("{private}"):
            return self.private / rel[len("{private}"):].lstrip("/\\")
        return self.in_ws(rel)

    @property
    def reward(self) -> Path:
        """Where the grader writes the score."""
        return self.resolve(self.cfg.reward)

    @property
    def planted(self) -> Path:
        """Where a hostile candidate tries to plant a score."""
        return self.resolve(self.cfg.planted_reward or self.cfg.reward)

    def stage(self, name: str, data: bytes) -> Path:
        """Put attacker content somewhere the candidate can read it."""
        p = self.root / "stage" / name
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(data)
        if self.cfg.sandbox_user and not IS_WINDOWS:
            os.chmod(p.parent, 0o755)
            os.chmod(p, 0o644)
        return p

    # candidate
    def _candidate_cmd(self, *args: str) -> list[str]:
        cmd = [sys.executable, CANDIDATE_SCRIPT, *args]
        if self.cfg.sandbox_user and not IS_WINDOWS:
            cmd = ["sudo", "-n", "-u", self.cfg.sandbox_user, *cmd]
        return cmd

    def _candidate_env(self) -> dict[str, str]:
        return dict(os.environ)

    def candidate(self, *args: str, timeout: float | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            self._candidate_cmd(*args),
            capture_output=True,
            text=True,
            env=self._candidate_env(),
            timeout=timeout or self.cfg.candidate_timeout + 10,
        )

    def candidate_until_timeout(self, *args: str) -> None:
        proc = subprocess.Popen(
            self._candidate_cmd(*args),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=self._candidate_env(),
        )
        try:
            proc.wait(timeout=self.cfg.candidate_timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    # grading
    def grade(self) -> GradeOutcome:
        cfg = self.cfg
        mapping = {
            "{python}": sys.executable,
            "{workspace}": str(self.ws),
            "{deliverable}": str(self.deliverable),
            "{reward}": str(self.reward),
            "{private}": str(self.private),
        }
        cmd = []
        for part in cfg.command:
            for k, v in mapping.items():
                part = part.replace(k, v)
            cmd.append(part)
        try:
            proc = subprocess.run(
                cmd, cwd=cfg.base, capture_output=True,
                timeout=cfg.grader_timeout,
            )
        except subprocess.TimeoutExpired:
            return GradeOutcome(None, f"grader hung past {cfg.grader_timeout:g}s")
        reward, note = self.read_reward()
        if proc.returncode != 0 and reward is None:
            note = f"grader exited {proc.returncode} without a reward"
        return GradeOutcome(reward, note)

    def read_reward(self) -> tuple[float | None, str]:
        try:
            text = self.reward.read_text()
        except (OSError, UnicodeDecodeError):
            return None, "no reward file"
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None, "reward file is not JSON or a number"
        if isinstance(data, (int, float)):
            data = {"reward": float(data)}
        if not isinstance(data, dict) or not isinstance(data.get("reward"), (int, float)):
            return None, "reward file has no numeric reward"
        value = float(data["reward"])
        return value, f"reward {value:g}"

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
