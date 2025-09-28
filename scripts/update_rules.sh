#!/bin/bash

# 统一入口：使用 Python 脚本按照 manifest 下载规则文件。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: 未找到 python3，请先安装后再运行。" >&2
  exit 1
fi

python3 "$REPO_ROOT/scripts/fetch_rules.py" "$@"
