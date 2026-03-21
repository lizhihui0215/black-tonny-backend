#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from app.db.engine import init_databases
from app.services.capture_transform_service import transform_capture_batch_to_serving


def main() -> int:
    parser = argparse.ArgumentParser(description="Transform one capture batch into serving tables.")
    parser.add_argument("--capture-batch-id", required=True, help="Capture batch id to transform")
    parser.add_argument("--analysis-batch-id", help="Optional target analysis batch id")
    args = parser.parse_args()

    init_databases()
    analysis_batch_id = transform_capture_batch_to_serving(
        args.capture_batch_id,
        analysis_batch_id=args.analysis_batch_id,
    )
    print(
        json.dumps(
            {
                "capture_batch_id": args.capture_batch_id,
                "analysis_batch_id": analysis_batch_id,
                "status": "success",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
