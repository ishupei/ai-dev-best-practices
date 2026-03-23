# ============================================================
# AI Skills & Rules 同步脚本 (PowerShell)
# 用法: .\sync-skills.ps1 [-Target <项目路径|all>] [-Register <项目路径>] [-List]
#
# 功能:
#   1. 同步 Claude Code skills（目录）到全局 (~/.claude/skills/)
#   2. 同步 Cursor skills 到全局 (~/.cursor/skills/)
#   3. 同步 Cursor skills/rules 到指定项目
#
# 示例:
#   .\sync-skills.ps1                                    # 同步全局 (Claude + Cursor)
#   .\sync-skills.ps1 -Target D:\work\my-project         # 同步到指定项目
#   .\sync-skills.ps1 -Target all                        # 同步到所有已注册项目
#   .\sync-skills.ps1 -Register D:\work\my-project       # 注册一个项目
# ============================================================

param(
    [string]$Target,
    [string]$Register,
    [switch]$List,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

# ---- 配置 ----
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RegistryFile = Join-Path $SourceDir ".sync-targets"

# ---- 日志 ----
function Log-Ok($msg)   { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Log-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Log-Err($msg)  { Write-Host "[ERR]  $msg" -ForegroundColor Red }

# ---- 1. 同步 Claude Code 全局 skills（.claude/skills/<name>/SKILL.md）----
function Sync-ClaudeGlobal {
    $claudeSkillsGlobal = Join-Path $env:USERPROFILE ".claude\skills"
    if (-not (Test-Path $claudeSkillsGlobal)) {
        New-Item -ItemType Directory -Path $claudeSkillsGlobal -Force | Out-Null
    }

    Write-Host ""
    Write-Host "=== 同步 Claude Code 全局 Skills（目录）==="

    $sourceSkills = Join-Path $SourceDir ".claude\skills"
    $count = 0

    if (-not (Test-Path $sourceSkills -PathType Container)) {
        Log-Warn "未找到 $sourceSkills，跳过 Claude 同步"
        return
    }

    Get-ChildItem -Path $sourceSkills -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $skillName = $_.Name
        $srcSkillMd = Join-Path $_.FullName "SKILL.md"
        if (-not (Test-Path $srcSkillMd)) { return }

        $destDir = Join-Path $claudeSkillsGlobal $skillName
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        Copy-Item -LiteralPath $srcSkillMd -Destination (Join-Path $destDir "SKILL.md") -Force
        Log-Ok "  $skillName/SKILL.md"
        $count++
    }

    Write-Host "  共同步 $count 个技能目录到 $claudeSkillsGlobal"
}

# ---- 2. 同步 Cursor skills 到全局 ----
function Sync-CursorGlobal {
    $cursorSkillsDir = Join-Path $env:USERPROFILE ".cursor\skills"
    if (-not (Test-Path $cursorSkillsDir)) {
        New-Item -ItemType Directory -Path $cursorSkillsDir -Force | Out-Null
    }

    Write-Host ""
    Write-Host "=== 同步 Cursor 全局 Skills ==="

    $sourceSkills = Join-Path $SourceDir ".cursor\skills"
    $count = 0

    Get-ChildItem -Path $sourceSkills -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $targetDir = Join-Path $cursorSkillsDir $_.Name
        Copy-Item $_.FullName -Destination $targetDir -Recurse -Force
        Log-Ok "  $($_.Name)"
        $count++
    }

    Write-Host "  共同步 $count 个技能到 $cursorSkillsDir"
}

# ---- 3. 同步 Cursor skills/rules 到目标项目 ----
function Sync-CursorToProject($targetPath) {
    if (-not (Test-Path $targetPath -PathType Container)) {
        Log-Err "目标项目不存在: $targetPath"
        return
    }

    Write-Host ""
    Write-Host "=== 同步 Cursor 到: $targetPath ==="

    $sourceSkills = Join-Path $SourceDir ".cursor\skills"
    $targetSkills = Join-Path $targetPath ".cursor\skills"
    $sourceRules  = Join-Path $SourceDir ".cursor\rules"
    $targetRules  = Join-Path $targetPath ".cursor\rules"

    # -- 同步 skills --
    if (Test-Path $sourceSkills -PathType Container) {
        Copy-Item $sourceSkills -Destination (Join-Path $targetPath ".cursor\skills") -Recurse -Force
        Log-Ok "skills -> $targetSkills"
    }

    # -- 同步 rules --
    if (Test-Path $sourceRules -PathType Container) {
        if (-not (Test-Path $targetRules)) {
            New-Item -ItemType Directory -Path $targetRules -Force | Out-Null
        }

        Get-ChildItem -Path $sourceRules -Filter "*.mdc" | ForEach-Object {
            Copy-Item $_.FullName -Destination (Join-Path $targetRules $_.Name) -Force
            Log-Ok "  rules/$($_.Name)"
        }
    }
}

# ---- 4. 注册项目 ----
function Register-Target($targetPath) {
    $resolved = (Resolve-Path $targetPath).Path

    if ((Test-Path $RegistryFile) -and ((Get-Content $RegistryFile) -contains $resolved)) {
        Log-Warn "项目已注册: $resolved"
    } else {
        Add-Content -Path $RegistryFile -Value $resolved
        Log-Ok "已注册项目: $resolved"
    }
}

# ---- 5. 同步所有已注册项目 ----
function Sync-AllRegistered {
    if (-not (Test-Path $RegistryFile)) {
        Log-Warn "暂无已注册项目。使用 -Register <路径> 添加项目。"
        return
    }

    Get-Content $RegistryFile | Where-Object { $_.Trim() -ne "" } | ForEach-Object {
        Sync-CursorToProject $_
    }
}

# ---- 主流程 ----
function Main {
    Write-Host "============================================"
    Write-Host "  AI Skills & Rules 同步工具"
    Write-Host "  中心仓库: $SourceDir"
    Write-Host "============================================"

    if ($Help) {
        Write-Host ""
        Write-Host "用法:"
        Write-Host "  .\sync-skills.ps1                                # 同步全局 (Claude + Cursor)"
        Write-Host "  .\sync-skills.ps1 -Target D:\work\project        # 同步到指定项目"
        Write-Host "  .\sync-skills.ps1 -Target all                    # 同步到所有已注册项目"
        Write-Host "  .\sync-skills.ps1 -Register D:\work\project      # 注册一个项目"
        Write-Host "  .\sync-skills.ps1 -List                          # 查看已注册项目"
        return
    }

    # 始终同步全局配置
    Sync-ClaudeGlobal
    Sync-CursorGlobal

    # 处理注册
    if ($Register) {
        Register-Target $Register
    }

    # 处理同步目标
    if ($Target) {
        if ($Target -eq "all") {
            Sync-AllRegistered
        } else {
            Sync-CursorToProject $Target
        }
    }

    # 查看列表
    if ($List) {
        Write-Host ""
        Write-Host "=== 已注册项目 ==="
        if (Test-Path $RegistryFile) {
            Get-Content $RegistryFile
        } else {
            Write-Host "(空)"
        }
    }

    Write-Host ""
    Write-Host "============================================"
    Write-Host "  同步完成"
    Write-Host "============================================"
}

Main
