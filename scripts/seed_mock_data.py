#!/usr/bin/env python3
"""Load reproducible Mock data after Alembic migration."""

from __future__ import annotations

import argparse
import json

from rolelens.db.seed import seed_database


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    counts = seed_database(seed=args.seed)
    print(json.dumps({"seed": args.seed, "counts": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
