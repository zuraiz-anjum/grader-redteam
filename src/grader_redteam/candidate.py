"""Actions a hostile candidate performs inside the workspace.

Every action runs in its own process so that, when a sandbox user is
configured, it runs with that user's permissions and not the tool's.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def main(argv: list[str]) -> int:
    action, *args = argv
    if action == "write":
        dest, src = args
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(Path(src).read_bytes())
    elif action == "symlink":
        dest, target = args
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target, dest)
    elif action == "read":
        try:
            data = Path(args[0]).read_bytes()
        except OSError:
            print("DENIED")
            return 0
        print(f"READ {len(data)}")
    elif action == "hang":
        dest, src = args
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(Path(src).read_bytes())
        while True:
            time.sleep(1)
    else:
        print(f"unknown action {action}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
