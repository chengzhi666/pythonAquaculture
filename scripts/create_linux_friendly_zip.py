"""Create a zip archive with POSIX paths for Linux extraction."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


def create_zip(source_dir: Path, output_zip: Path) -> None:
    source_dir = source_dir.resolve()
    output_zip = output_zip.resolve()
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    if output_zip.exists():
        output_zip.unlink()

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_dir():
                continue
            arcname = path.relative_to(source_dir).as_posix()
            zf.write(path, arcname)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Linux-friendly zip archive.")
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_zip", type=Path)
    args = parser.parse_args()

    create_zip(args.source_dir, args.output_zip)
    print(args.output_zip)


if __name__ == "__main__":
    main()
