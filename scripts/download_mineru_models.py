"""Download MinerU model files and write magic-pdf.json.

The script uses ModelScope, which is usually more reliable from mainland China.
It keeps model files under the demo folder so the deployment is self-contained.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from modelscope import snapshot_download


PDF_EXTRACT_PATTERNS = [
    "models/Layout/YOLO/*",
    "models/MFD/YOLO/*",
    "models/MFR/unimernet_hf_small_2503/*",
    "models/OCR/paddleocr_torch/*",
    "models/TabRec/RapidTable/*",
]

LAYOUTREADER_PATTERNS = ["*"]


def snapshot_with_retry(
    model_id: str,
    local_dir: Path,
    allow_patterns: list[str],
    max_workers: int,
    retries: int,
) -> str:
    local_dir.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return snapshot_download(
                model_id,
                allow_patterns=allow_patterns,
                local_dir=str(local_dir),
                max_workers=max_workers,
            )
        except Exception as exc:  # pragma: no cover - depends on network/modelscope
            last_error = exc
            print(f"[download] {model_id} attempt {attempt}/{retries} failed: {exc}")
            if attempt < retries:
                time.sleep(5 * attempt)
    raise RuntimeError(f"Failed to download {model_id}") from last_error


def write_magic_pdf_config(config_path: Path, models_dir: Path, layoutreader_dir: Path) -> None:
    payload = {
        "config_version": "1.1.1",
        "models-dir": str(models_dir),
        "layoutreader-model-dir": str(layoutreader_dir),
        "device-mode": "cpu",
        "layout-config": {"model": "doclayout_yolo"},
        "formula-config": {
            "mfd_model": "yolo_v8_mfd",
            "mfr_model": "unimernet_small",
            "enable": True,
        },
        "table-config": {
            "model": "rapid_table",
            "sub_model": "slanet_plus",
            "enable": True,
            "max_time": 400,
        },
    }
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def patch_paddleocr_model_config() -> None:
    """Align MinerU's bundled OCR config with the v5 torch detector from ModelScope."""
    import magic_pdf

    config_path = (
        Path(magic_pdf.__file__).resolve().parent
        / "model"
        / "sub_modules"
        / "ocr"
        / "paddleocr2pytorch"
        / "pytorchocr"
        / "utils"
        / "resources"
        / "models_config.yml"
    )
    if not config_path.exists():
        print(f"[warn] OCR config not found: {config_path}")
        return
    text = config_path.read_text(encoding="utf-8")
    updated = text.replace("ch_PP-OCRv3_det_infer.pth", "ch_PP-OCRv5_det_infer.pth")
    if updated != text:
        backup_path = config_path.with_suffix(config_path.suffix + ".bak")
        if not backup_path.exists():
            backup_path.write_text(text, encoding="utf-8")
        config_path.write_text(updated, encoding="utf-8")
        print(f"patched OCR config: {config_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download MinerU models from ModelScope.")
    parser.add_argument(
        "--root-dir",
        default=str(Path(__file__).resolve().parents[1]),
        help="Demo/project root. Models are stored under <root-dir>/.mineru_models.",
    )
    parser.add_argument(
        "--config",
        default=os.path.join(str(Path.home()), "magic-pdf.json"),
        help="Path to magic-pdf.json.",
    )
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--retries", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = Path(args.root_dir).expanduser().resolve()
    model_root = root_dir / ".mineru_models"

    pdf_extract_dir = model_root / "PDF-Extract-Kit-1.0"
    layoutreader_dir = model_root / "layoutreader"

    print("[1/3] Downloading PDF-Extract-Kit models from ModelScope")
    pdf_repo_dir = Path(
        snapshot_with_retry(
            "opendatalab/PDF-Extract-Kit-1.0",
            pdf_extract_dir,
            PDF_EXTRACT_PATTERNS,
            max_workers=args.max_workers,
            retries=args.retries,
        )
    )

    print("[2/3] Downloading layoutreader model from ModelScope")
    layout_repo_dir = Path(
        snapshot_with_retry(
            "ppaanngggg/layoutreader",
            layoutreader_dir,
            LAYOUTREADER_PATTERNS,
            max_workers=args.max_workers,
            retries=args.retries,
        )
    )

    models_dir = pdf_repo_dir / "models"
    config_path = Path(args.config).expanduser().resolve()
    print("[3/3] Writing MinerU config")
    write_magic_pdf_config(config_path, models_dir, layout_repo_dir)
    patch_paddleocr_model_config()

    print(f"models-dir: {models_dir}")
    print(f"layoutreader-model-dir: {layout_repo_dir}")
    print(f"config: {config_path}")


if __name__ == "__main__":
    main()
