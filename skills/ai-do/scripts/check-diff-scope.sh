#!/usr/bin/env bash
# ============================================================
# ai-do diff 范围辅助标定 (macOS/Linux 版; Windows 用 check-diff-scope.ps1)
# 用法:
#   ./check-diff-scope.sh
#   ./check-diff-scope.sh -m 8 -M 2
# 退出码: 0 = 范围未触发闸门; 1 = 触发范围或风险闸门
# ============================================================

set -uo pipefail

MAX_FILES=8
MAX_MODULES=2

while getopts "m:M:h" opt; do
  case "$opt" in
    m) MAX_FILES="$OPTARG" ;;
    M) MAX_MODULES="$OPTARG" ;;
    h) echo "用法: $0 [-m 最大文件数] [-M 最大模块数]"; exit 0 ;;
    *) echo "未知参数"; exit 1 ;;
  esac
done

ok()   { echo "[OK]   $*"; }
warn() { echo "[WARN] $*"; }
err()  { echo "[ERR]  $*"; }
info() { echo "[INFO] $*"; }

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  err "当前目录不是 Git 仓库"
  exit 1
fi

UNSTAGED="$(git diff --name-status)"
STAGED="$(git diff --cached --name-status)"
UNTRACKED="$(git ls-files --others --exclude-standard)"
if [ -z "$UNSTAGED" ] && [ -z "$STAGED" ] && [ -z "$UNTRACKED" ]; then
  ok "当前没有已暂存、未暂存或未跟踪 diff"
  exit 0
fi

FILES="$(printf '%s\n%s\n%s\n' "$UNSTAGED" "$STAGED" "$UNTRACKED" | awk 'NF {print $NF}' | sort -u)"
FILE_COUNT="$(printf '%s\n' "$FILES" | grep -c .)"
MODULES="$(printf '%s\n' "$FILES" | awk -F '[\\/]' '{print $1}' | sort -u)"
MODULE_COUNT="$(printf '%s\n' "$MODULES" | grep -c .)"

info "变更文件 $FILE_COUNT 个"
printf '%s\n' "$FILES" | sed 's/^/  /'
info "顶层模块 $MODULE_COUNT 个: $(printf '%s\n' "$MODULES" | tr '\n' ' ')"

RISKY="$(printf '%s\n' "$FILES" | grep -E '(^|/)(config|deploy/config|secrets|credentials)(/|$)|(^|/)\.env|\.pem$|\.key$|\.p12$|\.pfx$|id_rsa|package-lock\.json$|pnpm-lock\.yaml$|yarn\.lock$|pom\.xml$|build\.gradle$|settings\.gradle$' || true)"
if [ -n "$RISKY" ]; then
  warn "发现高风险或依赖/配置类文件:"
  printf '%s\n' "$RISKY" | sed 's/^/  /'
fi

BLOCKED=0
if [ "$FILE_COUNT" -gt "$MAX_FILES" ]; then
  err "变更文件数 $FILE_COUNT 超过阈值 $MAX_FILES"
  BLOCKED=1
fi
if [ "$MODULE_COUNT" -gt "$MAX_MODULES" ]; then
  err "顶层模块数 $MODULE_COUNT 超过阈值 $MAX_MODULES"
  BLOCKED=1
fi
if [ -n "$RISKY" ]; then
  err "触发风险文件闸门，请人工确认"
  BLOCKED=1
fi

if [ "$BLOCKED" -ne 0 ]; then exit 1; fi
ok "diff 范围未触发闸门"
exit 0
