# ============================================================
# AI Skills & Rules 同步脚本 (PowerShell)
# 用法: .\sync-skills.ps1 [-Target <项目路径|all>] [-Register <项目路径>] [-List]
#
# 功能:
#   1. 从中心仓库 skills/ 同步 Claude Code skills 到全局 (~/.claude/skills/)
#   2. 从中心仓库 skills/ 同步 Cursor skills 到全局 (~/.cursor/skills/)
#   3. 从中心仓库 skills/ 与 rules/ 同步到目标项目（Cursor / Trae）
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

# ---- 1. 从中心仓库同步 Claude Code 全局 skills ----
function Sync-ClaudeGlobal {
    $claudeSkillsGlobal = Join-Path $env:USERPROFILE ".claude\skills"
    if (-not (Test-Path $claudeSkillsGlobal)) {
        New-Item -ItemType Directory -Path $claudeSkillsGlobal -Force | Out-Null
    }

    Write-Host ""
    Write-Host "=== 同步 Claude Code 全局 Skills ==="

    $sourceSkills = Join-Path $SourceDir "skills"
    if (-not (Test-Path $sourceSkills -PathType Container)) {
        Log-Warn "未找到 $sourceSkills，跳过 Claude 同步"
        return
    }

    $skillDirs = Get-ChildItem -Path $sourceSkills -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName "SKILL.md") }

    foreach ($d in $skillDirs) {
        $targetDir = Join-Path $claudeSkillsGlobal $d.Name
        if (Test-Path $targetDir) {
            Remove-Item $targetDir -Recurse -Force
        }
        Copy-Item $d.FullName -Destination $targetDir -Recurse -Force
        Log-Ok "  $($d.Name)"
    }

    Write-Host "  共同步 $($skillDirs.Count) 个技能目录到 $claudeSkillsGlobal"
}

# ---- 2. 从中心仓库同步 Cursor skills 到全局 ----
function Sync-CursorGlobal {
    $cursorSkillsDir = Join-Path $env:USERPROFILE ".cursor\skills"
    if (-not (Test-Path $cursorSkillsDir)) {
        New-Item -ItemType Directory -Path $cursorSkillsDir -Force | Out-Null
    }

    Write-Host ""
    Write-Host "=== 同步 Cursor 全局 Skills ==="

    $sourceSkills = Join-Path $SourceDir "skills"
    $count = 0

    Get-ChildItem -Path $sourceSkills -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $targetDir = Join-Path $cursorSkillsDir $_.Name
        if (Test-Path $targetDir) {
            Remove-Item $targetDir -Recurse -Force
        }
        Copy-Item $_.FullName -Destination $targetDir -Recurse -Force
        Log-Ok "  $($_.Name)"
        $count++
    }

    Write-Host "  共同步 $count 个技能到 $cursorSkillsDir"
}

# ---- 3. 同步 Cursor / Trae 到目标项目 ----
function Sync-ProjectTargets($targetPath) {
    if (-not (Test-Path $targetPath -PathType Container)) {
        Log-Err "目标项目不存在: $targetPath"
        return
    }

    Write-Host ""
    Write-Host "=== 同步项目配置到: $targetPath ==="

    $sourceSkills = Join-Path $SourceDir "skills"
    $targetSkills = Join-Path $targetPath ".cursor\skills"
    $targetCursor = Join-Path $targetPath ".cursor"
    $sourceRules  = Join-Path $SourceDir "rules"
    $targetRules  = Join-Path $targetPath ".cursor\rules"
    $targetTrae   = Join-Path $targetPath ".trae"
    $targetTraeSkills = Join-Path $targetPath ".trae\skills"
    $targetTraeRules  = Join-Path $targetPath ".trae\rules"

    # -- 同步 skills --
    if (Test-Path $sourceSkills -PathType Container) {
        if (-not (Test-Path $targetCursor)) {
            New-Item -ItemType Directory -Path $targetCursor -Force | Out-Null
        }
        if (Test-Path $targetSkills) {
            Remove-Item $targetSkills -Recurse -Force
        }
        Copy-Item $sourceSkills -Destination $targetSkills -Recurse -Force
        Log-Ok "cursor skills -> $targetSkills"
    }

    # -- 同步 cursor rules --
    if (Test-Path $sourceRules -PathType Container) {
        if (-not (Test-Path $targetRules)) {
            New-Item -ItemType Directory -Path $targetRules -Force | Out-Null
        }

        Get-ChildItem -Path $sourceRules -Filter "*.md" | ForEach-Object {
            $targetRuleName = [System.IO.Path]::GetFileNameWithoutExtension($_.Name) + ".mdc"
            Copy-Item $_.FullName -Destination (Join-Path $targetRules $targetRuleName) -Force
            Log-Ok "  cursor rules/$targetRuleName"
        }
    }

    # -- 同步 trae skills --
    if (Test-Path $sourceSkills -PathType Container) {
        if (-not (Test-Path $targetTrae)) {
            New-Item -ItemType Directory -Path $targetTrae -Force | Out-Null
        }
        if (Test-Path $targetTraeSkills) {
            Remove-Item $targetTraeSkills -Recurse -Force
        }
        Copy-Item $sourceSkills -Destination $targetTraeSkills -Recurse -Force
        Log-Ok "trae skills -> $targetTraeSkills"
    }

    # -- 同步 trae rules --
    if (Test-Path $sourceRules -PathType Container) {
        if (-not (Test-Path $targetTraeRules)) {
            New-Item -ItemType Directory -Path $targetTraeRules -Force | Out-Null
        }

        Get-ChildItem -Path $sourceRules -Filter "*.md" | ForEach-Object {
            Copy-Item $_.FullName -Destination (Join-Path $targetTraeRules $_.Name) -Force
            Log-Ok "  trae rules/$($_.Name)"
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
        Sync-ProjectTargets $_
    }
}

# ---- 主流程 ----
function Main {
    Write-Host "============================================"
    Write-Host "  AI Skills  Rules 同步工具"
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
            Sync-ProjectTargets $Target
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
