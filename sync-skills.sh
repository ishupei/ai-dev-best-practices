#!/bin/bash
# ============================================================
# AI Skills & Rules 同步脚本
# 用法: bash sync-skills.sh [--target <项目路径>]
#
# 功能:
#   1. 同步 Claude Code commands 到全局 (~/.claude/commands/)
#   2. 同步 Cursor skills/rules 到指定项目（通过 symlink）
#
# 示例:
#   bash sync-skills.sh                          # 仅同步 Claude Code 全局
#   bash sync-skills.sh --target ~/my-project    # 同步到指定项目
#   bash sync-skills.sh --target all             # 同步到所有已注册项目
# ============================================================

set -euo pipefail

# ---- 配置 ----
# 中心仓库路径（本脚本所在目录）
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
# 已注册的项目列表文件
REGISTRY_FILE="$SOURCE_DIR/.sync-targets"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err()  { echo -e "${RED}[ERR]${NC} $1"; }

# ---- 1. 同步 Claude Code 全局命令 ----
sync_claude_global() {
    local claude_cmd_dir="$HOME/.claude/commands"
    mkdir -p "$claude_cmd_dir"

    echo ""
    echo "=== 同步 Claude Code 全局命令 ==="

    local count=0
    for f in "$SOURCE_DIR/.claude/commands/"*.md; do
        [ -f "$f" ] || continue
        local fname=$(basename "$f")
        cp "$f" "$claude_cmd_dir/$fname"
        log_ok "  $fname"
        ((count++))
    done

    echo "  共同步 $count 个命令到 $claude_cmd_dir"
}

# ---- 2. 同步 Cursor skills/rules 到目标项目 ----
sync_cursor_to_project() {
    local target="$1"

    # 展开 ~ 路径
    target="${target/#\~/$HOME}"

    if [ ! -d "$target" ]; then
        log_err "目标项目不存在: $target"
        return 1
    fi

    echo ""
    echo "=== 同步 Cursor 到: $target ==="

    # 同步 skills（使用 symlink 指向中心仓库）
    local target_skills="$target/.cursor/skills"
    local source_skills="$SOURCE_DIR/.cursor/skills"

    if [ -d "$source_skills" ]; then
        # 如果目标是普通目录（非 symlink），先备份
        if [ -d "$target_skills" ] && [ ! -L "$target_skills" ]; then
            local backup="${target_skills}.bak.$(date +%Y%m%d%H%M%S)"
            mv "$target_skills" "$backup"
            log_warn "已备份原 skills 目录到 $backup"
        fi

        # 确保父目录存在
        mkdir -p "$target/.cursor"

        # 删除旧 symlink
        [ -L "$target_skills" ] && rm "$target_skills"

        # 创建 symlink
        ln -s "$source_skills" "$target_skills"
        log_ok "skills -> $source_skills"
    fi

    # 同步 rules（逐文件 symlink，保留项目自有 rules）
    local target_rules="$target/.cursor/rules"
    local source_rules="$SOURCE_DIR/.cursor/rules"

    if [ -d "$source_rules" ]; then
        mkdir -p "$target_rules"

        for f in "$source_rules/"*.mdc; do
            [ -f "$f" ] || continue
            local fname=$(basename "$f")
            local target_file="$target_rules/$fname"

            # 如果目标已有同名非 symlink 文件，跳过（项目自有规则优先）
            if [ -f "$target_file" ] && [ ! -L "$target_file" ]; then
                log_warn "跳过 $fname（项目已有自定义版本）"
                continue
            fi

            [ -L "$target_file" ] && rm "$target_file"
            ln -s "$f" "$target_file"
            log_ok "rules/$fname -> 中心仓库"
        done
    fi
}

# ---- 3. 注册项目 ----
register_target() {
    local target="$1"
    target="${target/#\~/$HOME}"
    target="$(cd "$target" && pwd)"

    if [ -f "$REGISTRY_FILE" ] && grep -qxF "$target" "$REGISTRY_FILE"; then
        log_warn "项目已注册: $target"
    else
        echo "$target" >> "$REGISTRY_FILE"
        log_ok "已注册项目: $target"
    fi
}

# ---- 4. 同步所有已注册项目 ----
sync_all_registered() {
    if [ ! -f "$REGISTRY_FILE" ]; then
        log_warn "暂无已注册项目。使用 --register <路径> 添加项目。"
        return
    fi

    while IFS= read -r project; do
        [ -z "$project" ] && continue
        sync_cursor_to_project "$project"
    done < "$REGISTRY_FILE"
}

# ---- 主流程 ----
main() {
    echo "============================================"
    echo "  AI Skills & Rules 同步工具"
    echo "  中心仓库: $SOURCE_DIR"
    echo "============================================"

    # 始终同步 Claude Code 全局命令
    sync_claude_global

    # 解析参数
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --target)
                shift
                if [ "$1" = "all" ]; then
                    sync_all_registered
                else
                    sync_cursor_to_project "$1"
                fi
                shift
                ;;
            --register)
                shift
                register_target "$1"
                shift
                ;;
            --list)
                echo ""
                echo "=== 已注册项目 ==="
                if [ -f "$REGISTRY_FILE" ]; then
                    cat "$REGISTRY_FILE"
                else
                    echo "(空)"
                fi
                shift
                ;;
            --help|-h)
                echo ""
                echo "用法:"
                echo "  bash sync-skills.sh                          # 同步 Claude Code 全局"
                echo "  bash sync-skills.sh --target ~/project       # 同步到指定项目"
                echo "  bash sync-skills.sh --target all              # 同步到所有已注册项目"
                echo "  bash sync-skills.sh --register ~/project     # 注册一个项目"
                echo "  bash sync-skills.sh --list                    # 查看已注册项目"
                shift
                ;;
            *)
                log_err "未知参数: $1"
                exit 1
                ;;
        esac
    done

    echo ""
    echo "============================================"
    echo "  同步完成"
    echo "============================================"
}

main "$@"
