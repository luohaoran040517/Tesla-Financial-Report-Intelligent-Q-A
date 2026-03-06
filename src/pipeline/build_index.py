from __future__ import annotations

import argparse
import time

from src.core.config import AppConfig
from src.core.indexer import IndexBuilder
from src.core.parser import build_parsed_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse Tesla filings and build hybrid indexes")
    parser.add_argument("--skip-parse", action="store_true", help="Skip PDF parsing and reuse existing parsed_chunks.jsonl")
    args = parser.parse_args()

    config = AppConfig()
    config.ensure_dirs()

    t0 = time.time()
    if not args.skip_parse:
        chunks = build_parsed_chunks(config)
        print(f"[build_index] parsed chunks: {len(chunks)}")
    else:
        print("[build_index] skip parsing, reusing existing chunks file")

    builder = IndexBuilder(config)
    stats = builder.build()

    print(f"[build_index] index build done: {stats}")
    print(f"[build_index] elapsed: {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()

