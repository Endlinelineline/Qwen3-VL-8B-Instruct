#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo '此离线包需要 Apple Silicon Mac 和原生 arm64 终端。' >&2
  exit 1
fi
PYTHON="${QWEN_PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  PYTHON="$(command -v python3.11 || true)"
  if [[ -z "$PYTHON" ]]; then
    PYTHON=/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11
  fi
fi
if [[ -z "$PYTHON" ]] || ! "$PYTHON" -c 'import platform,sys; sys.exit(not (sys.version_info[:2] == (3,11) and platform.machine() == "arm64"))'; then
  echo '请先安装原生 Apple Silicon Python 3.11；安装包位于 macos_offline/python_installer/。' >&2
  exit 1
fi
if [[ ! -f macos_offline/requirements-locked.txt || ! -d macos_offline/wheelhouse ]]; then
  echo '未找到离线依赖包，请将 macos_offline 文件夹完整复制到 Mac。' >&2
  exit 1
fi
if [[ ! -x .venv/bin/python ]]; then
  if [[ -e .venv ]]; then
    echo '已有 .venv 不是可用的 Mac 虚拟环境，请将其改名后重新运行。' >&2
    exit 1
  fi
  "$PYTHON" -m venv .venv
fi
if ! .venv/bin/python -c 'import platform,sys; sys.exit(not (sys.version_info[:2] == (3,11) and platform.machine() == "arm64"))'; then
  echo '已有 .venv 不适用于此 Mac，请将它改名后重新运行。' >&2
  exit 1
fi
echo '正在从本地安装和验证依赖……'
.venv/bin/python -m pip install --no-index --find-links macos_offline/wheelhouse --require-hashes -r macos_offline/requirements-locked.txt
.venv/bin/python -m pip check
.venv/bin/python -c 'import torch, torchvision, transformers, openpyxl; print("依赖加载成功；MPS:", torch.backends.mps.is_available())'
if [[ $# -eq 0 ]]; then
  set -- --input '.data/模型推理问题记录v8.xlsx' --max-new-tokens 256
fi
exec .venv/bin/python -m scripts.qwen3_vl.run_excel "$@"
