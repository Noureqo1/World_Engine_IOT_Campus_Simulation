"""Generate the Phase 2 JSON/CSV/config artifacts used by the deployment."""

from __future__ import annotations

import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from world_engine.phase2.artifacts import write_phase2_artifacts


def main() -> None:
    output_root = WORKSPACE_ROOT / "docs" / "Phase2"
    paths = write_phase2_artifacts(output_root)
    for label, path in sorted(paths.items()):
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
