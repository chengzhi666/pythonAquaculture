#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-ocr"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PYTHON_VENV_PKG="${PYTHON_VENV_PKG:-python3-venv}"

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo"
fi

echo "[1/5] Installing Ubuntu system packages"
${SUDO} apt update
DEBIAN_FRONTEND=noninteractive ${SUDO} apt install -y \
  build-essential \
  git \
  "${PYTHON_BIN}" \
  "${PYTHON_VENV_PKG}" \
  python3-dev \
  python3-pip \
  libgl1 \
  libglib2.0-0 \
  libsm6 \
  libxext6 \
  libxrender1 \
  poppler-utils

echo "[2/5] Creating virtual environment at ${VENV_DIR}"
"${PYTHON_BIN}" -m venv "${VENV_DIR}"

echo "[3/5] Upgrading pip tooling"
source "${VENV_DIR}/bin/activate"
python -m pip install -U pip setuptools wheel

echo "[4/5] Installing OCR demo dependencies"
python -m pip install -r "${ROOT_DIR}/requirements-ocr.txt"

if [[ "${SKIP_MINERU_MODEL_DOWNLOAD:-0}" != "1" ]]; then
  echo "[5/5] Downloading MinerU models and writing magic-pdf.json"
  python "${ROOT_DIR}/scripts/download_mineru_models.py" --root-dir "${ROOT_DIR}"
else
  echo "[5/5] Skipping MinerU model download because SKIP_MINERU_MODEL_DOWNLOAD=1"
fi

echo
echo "Setup complete."
echo "Activate with:"
echo "  source ${VENV_DIR}/bin/activate"
echo "Run demo with:"
echo "  bash ${ROOT_DIR}/scripts/run_ocr_demo.sh"
