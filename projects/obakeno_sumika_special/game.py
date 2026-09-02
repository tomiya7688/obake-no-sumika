from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_knowledge() -> dict[str, object]:
    return json.loads((ROOT / "data" / "knowledge.json").read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="obakeno_sumika_special placeholder")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    knowledge = load_knowledge()
    if args.validate:
        print(f"OK: special knowledge entries={len(knowledge.get('knowledge', []))}")
    else:
        print("obakeno_sumika_special is a separated placeholder project.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
