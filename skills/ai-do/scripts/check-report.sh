#!/usr/bin/env bash
# ============================================================
# ai-do 汇报完整性校验 (macOS/Linux 版; Windows 用 check-report.ps1)
# 用法:
#   ./check-report.sh -f ./report.md
#   ./check-report.sh -t "最终汇报文本"
# 退出码: 0 = 通过; 1 = 缺少必填块
# ============================================================

set -uo pipefail

MODE=""
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
err()  { echo "[ERR]  $*"; }
info() { echo "[INFO] $*"; }

if [ "$MODE" = "text" ]; then
  TARGET="$TEXT"
  SRC_DESC="命令行文本"
elif [ "$MODE" = "file" ]; then
  if [ ! -f "$FILE" ]; then err "文件不存在: $FILE"; exit 1; fi
  TARGET="$(cat "$FILE")"
  SRC_DESC="$FILE"
else
  err "必须提供 -t 或 -f"
  exit 1
fi

info "来源: $SRC_DESC"

NAMES=("执行契约" "完成范围" "变更文件" "验证等级" "diff 复核" "构建/命令" "测试执行" "技术栈判定" "规范检查" "未执行验证" "规范读取凭证")
PATTERNS=("执行契约|执行契约摘要" "完成范围" "变更文件|改动文件" "验证等级|静态自检" "diff|Diff" "构建|编译|命令" "测试执行|测试" "技术栈判定|技术栈" "规范检查" "未执行验证|未执行" "规范读取凭证|已读规范|读取凭证")

MISSING=0
for i in "${!NAMES[@]}"; do
  if ! printf '%s\n' "$TARGET" | grep -Eq "${PATTERNS[$i]}"; then
    err "缺少必填块: ${NAMES[$i]}"
    MISSING=1
  fi
done

if [ "$MISSING" -ne 0 ]; then exit 1; fi
ok "汇报完整性校验通过"
exit 0
