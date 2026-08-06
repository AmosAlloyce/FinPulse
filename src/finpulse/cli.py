from __future__ import annotations

import argparse
import json
from pathlib import Path

from finpulse.contracts import json_schema
from finpulse.generator import SyntheticEventGenerator
from finpulse.local_pipeline import run_local_demo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="finpulse", description="FinPulse fintech data platform developer CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    local = subparsers.add_parser(
        "local-demo", help="run the full portable ingestion-to-mart pipeline"
    )
    local.add_argument("--events", type=int, default=10_000)
    local.add_argument("--output", type=Path, default=Path("artifacts/local-demo"))
    local.add_argument("--seed", type=int, default=42)

    emit = subparsers.add_parser("emit", help="print synthetic events as JSON lines")
    emit.add_argument("--count", type=int, default=10)
    emit.add_argument("--seed", type=int, default=42)

    schema = subparsers.add_parser("schema", help="write the event contract JSON schema")
    schema.add_argument("--output", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "local-demo":
        summary = run_local_demo(args.events, args.output, args.seed)
        print(json.dumps(summary, indent=2))
    elif args.command == "emit":
        generator = SyntheticEventGenerator(seed=args.seed)
        for event in generator.events(args.count):
            print(event.to_json())
    elif args.command == "schema":
        content = json.dumps(json_schema(), indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content + "\n", encoding="utf-8")
        else:
            print(content)


if __name__ == "__main__":
    main()
