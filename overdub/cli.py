"""CLI entry point:  overdub <url> [--config overdub.toml] [--force] [--only STAGE ...]"""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import Config
from .pipeline import Context, run_pipeline
from .stages import all_stages
from .workdir import WorkDir


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="overdub", description="Local YouTube→Russian dubbing")
    p.add_argument("url", help="YouTube video URL")
    p.add_argument("--config", type=Path, default=Path("overdub.toml"), help="TOML config path")
    p.add_argument("--force", action="store_true", help="re-run stages even if artifacts exist")
    p.add_argument("--only", nargs="+", metavar="STAGE", help="run only these stages")
    args = p.parse_args(argv)

    cfg = Config.load(args.config)
    work = WorkDir.for_url(args.url, cfg.work_root)
    ctx = Context(url=args.url, cfg=cfg, work=work)

    print(f"overdub: {args.url}")
    print(f"work dir: {work.root}")
    run_pipeline(ctx, all_stages(cfg), force=args.force,
                 only=set(args.only) if args.only else None)


if __name__ == "__main__":
    main()
