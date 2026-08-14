#!/usr/bin/env bash
# ============================================================
# ai-do 条款引用校验 (macOS/Linux 版; Windows 用 check-refs.ps1)
# 用法:
#   ./check-refs.sh
#   ./check-refs.sh -t "检查单文本"
#   ./check-refs.sh -f ./checklist.txt
#   STANDARDS_PATH=./references/core-standards.md ./check-refs.sh
# 退出码: 0 = 通过; 1 = 悬空引用或无引用
# ============================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
SKILL_FILE="${SKILL_PATH:-$SKILL_ROOT/SKILL.md}"
STANDARDS_PATH="${STANDARDS_PATH:-$SKILL_ROOT/references}"

MODE="skill"
TEXT=""
FILE=""

while getopts "t:f:h" opt; do
  case "$opt" in
    t) MODE="text"; TEXT="$OPTARG" ;;
    f) MODE="file"; FILE="$OPTARG" ;;
    h) echo "用法: $0 [-t 文本 | -f 文件]"; exit 0 ;;
    *) echo "未知参数"; exit 1 ;;
  esac
done

ok()   { echo "[OK]   $*"; }
warn() { echo "[WARN] $*"; }
err()  { echo "[ERR]  $*"; }
info() { echo "[INFO] $*"; }

if [ ! -e "$STANDARDS_PATH" ]; then
  err "规范路径不存在: $STANDARDS_PATH"
  exit 1
fi

if [ -d "$STANDARDS_PATH" ]; then
  STANDARD_FILES=$(find "$STANDARDS_PATH" -maxdepth 1 -type f -name "*.md" | sort)
else
  STANDARD_FILES="$STANDARDS_PATH"
fi

DEFINED=$(while IFS= read -r f; do
  [ -f "$f" ] || continue
  grep -oE '^##[[:space:]]+[0-9]+(\.[0-9]+)*|^-[[:space:]]+[0-9]+(\.[0-9]+)*' "$f" | grep -oE '[0-9]+(\.[0-9]+)*$'
done <<< "$STANDARD_FILES" | sort -u)

if [ -z "$DEFINED" ]; then
  err "未解析到任何条款编号: $STANDARDS_PATH"
  exit 1
fi
info "已解析规范条款编号 $(printf '%s\n' "$DEFINED" | wc -l | tr -d ' ') 个"

if [ "$MODE" = "text" ]; then
  TARGET="$TEXT"
  SRC_DESC="命令行文本"
elif [ "$MODE" = "file" ]; then
  if [ ! -f "$FILE" ]; then err "文件不存在: $FILE"; exit 1; fi
  TARGET="$(cat "$FILE")"
  SRC_DESC="$FILE"
else
  if [ ! -f "$SKILL_FILE" ]; then err "SKILL.md 不存在: $SKILL_FILE"; exit 1; fi
  TARGET="$(cat "$SKILL_FILE")"
  SRC_DESC="$SKILL_FILE"
fi

REFS=$(printf '%s\n' "$TARGET" | grep -oE '§[[:space:]]*[0-9][0-9./[:space:]]*' | grep -oE '[0-9]+(\.[0-9]+)*' | sort -u)
info "来源: $SRC_DESC"
info "提取到 § 引用 $(printf '%s\n' "$REFS" | grep -c .) 个: $(printf '%s\n' "$REFS" | tr '\n' ' ')"

if [ -z "$REFS" ]; then
  if [ "$MODE" != "skill" ]; then
    err "文本中没有任何 § 引用，检查单必须包含条款编号引用"
    exit 1
  fi
  warn "SKILL.md 中没有任何 § 引用"
  exit 0
fi

GOOD=""
BAD=""
for r in $REFS; do
  esc_r=$(printf '%s' "$r" | sed 's/\./\\./g')
  if printf '%s\n' "$DEFINED" | grep -qx "$r"; then
    GOOD="$GOOD $r"
  elif printf '%s\n' "$DEFINED" | grep -qE "^$esc_r\."; then
    GOOD="$GOOD $r"
  else
    BAD="$BAD $r"
  fi
done

if [ -n "$GOOD" ]; then ok "有效引用 $(echo $GOOD | wc -w | tr -d ' ') 个:$(echo "$GOOD" | sed 's/^ //; s/ /,/g')"; fi
if [ -n "$BAD" ]; then
  for b in $BAD; do err "悬空引用: §$b (规范中不存在)"; done
  exit 1
fi

ok "校验通过"
exit 0
