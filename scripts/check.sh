#!/usr/bin/env bash
#
# 品質 gate：唯一入口，任一步驟失敗即以非零結束。
#
# 掃描範圍只含新系統（src/hotstock、tests）。舊 src/*.py、run_news.py
# 依 ADR-0001 DEC-002 不屬新主線，不在此檢查。
#
# 本腳本只做檢查，不寫檔、不自動 format、不自動 fix。
# 用法：./scripts/check.sh（可從任意 cwd 執行）

set -euo pipefail

# 從任意 cwd 啟動都先定位 repo root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

step() {
    echo
    echo "──────────────────────────────────────────────"
    echo "▶ $1"
    echo "──────────────────────────────────────────────"
}

step "1/6 lockfile 漂移檢查"
uv lock --check

step "2/6 shell 語法檢查"
bash -n scripts/check.sh

step "3/6 format 檢查（不修改檔案）"
uv run --frozen ruff format --check src/hotstock tests

step "4/6 lint"
uv run --frozen ruff check src/hotstock tests

step "5/6 型別檢查"
uv run --frozen mypy src/hotstock

step "6/6 測試"
uv run --frozen pytest

echo
echo "=============================================="
echo "✅ 全部通過"
echo "=============================================="
