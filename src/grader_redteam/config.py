"""Load and validate the TOML config."""

from __future__ import annotations

import sys

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    base: Path
    command: list[str]
    grader_timeout: float
    template: Path | None
    deliverable: str
    reward: str
    planted_reward: str = ""
    protected: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    sandbox_user: str = ""
    candidate_timeout: float = 2.0
    hang_content: str | None = None
    reference: Path | None = None
    alternates: list[Path] = field(default_factory=list)
    negatives: list[Path] = field(default_factory=list)


def _path(base: Path, value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(value)
    return p if p.is_absolute() else (base / p).resolve()


def load(path: str | Path) -> Config:
    path = Path(path).resolve()
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    base = path.parent
    grader = raw.get("grader", {})
    ws = raw.get("workspace", {})
    cand = raw.get("candidate", {})
    ctl = raw.get("controls", {})

    command = grader.get("command")
    if isinstance(command, str):
        command = command.split()
    if not command:
        raise ValueError("[grader] command is required")
    if "deliverable" not in ws or "reward" not in ws:
        raise ValueError("[workspace] needs both deliverable and reward")

    return Config(
        base=base,
        command=list(command),
        grader_timeout=float(grader.get("timeout", 30)),
        template=_path(base, ws.get("template")),
        deliverable=ws["deliverable"],
        reward=ws["reward"],
        planted_reward=ws.get("planted_reward", ws["reward"]),
        protected=list(ws.get("protected", [])),
        secrets=list(ws.get("secrets", [])),
        sandbox_user=cand.get("sandbox_user", ""),
        candidate_timeout=float(cand.get("timeout", 2)),
        hang_content=cand.get("hang_content"),
        reference=_path(base, ctl.get("reference")),
        alternates=[_path(base, p) for p in ctl.get("alternates", [])],
        negatives=[_path(base, p) for p in ctl.get("negatives", [])],
    )
