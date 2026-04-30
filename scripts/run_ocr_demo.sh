#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-ocr"
PDF_DIR="${1:-${ROOT_DIR}/test_pdfs}"
OUTPUT_DIR="${2:-${ROOT_DIR}/results_ubuntu_demo}"
MAX_PDFS="${MAX_PDFS:-1}"

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Virtual environment not found: ${VENV_DIR}"
  echo "Please run: bash ${ROOT_DIR}/scripts/setup_ubuntu24_ocr.sh"
  exit 1
fi

if [[ ! -d "${PDF_DIR}" ]]; then
  echo "PDF directory not found: ${PDF_DIR}"
  exit 1
fi

source "${VENV_DIR}/bin/activate"

echo "Running OCR comparison demo"
echo "PDF_DIR=${PDF_DIR}"
echo "OUTPUT_DIR=${OUTPUT_DIR}"
echo "MAX_PDFS=${MAX_PDFS} (set MAX_PDFS=0 to process all PDFs)"

python "${ROOT_DIR}/run_mineru_comparison.py" \
  --pdf-dir "${PDF_DIR}" \
  --output "${OUTPUT_DIR}" \
  --max-pdfs "${MAX_PDFS}"

echo
echo "Done. Key outputs:"
echo "  ${OUTPUT_DIR}/summary.json"
echo "  ${OUTPUT_DIR}/comparison_table.csv"
echo "  ${OUTPUT_DIR}/markdown/"
