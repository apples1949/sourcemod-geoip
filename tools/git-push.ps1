# 把本仓库初始化并推送到 GitHub（可选辅助脚本）
#
# 用法:
#   powershell -ExecutionPolicy Bypass -File tools/git-push.ps1 -Repo sourcemod-geoip
#   powershell -ExecutionPolicy Bypass -File tools/git-push.ps1 -Repo sourcemod-geoip -Visibility public -Push
#
# 不带 -Push 时只做本地 init/commit/remote，不联网推送。

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Repo,

    [string]$Owner = "",

    [ValidateSet('public', 'private')]
    [string]$Visibility = 'public',

    [string]$Message = 'Add SourceMod GeoIP extension with GitHub Actions build for 1.11/1.12',

    [switch]$Push
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'git 未安装' }

if (-not $Owner) {
    $Owner = (git config --global user.name)
    if (-not $Owner) { throw '无法推断 GitHub 用户名，请用 -Owner 指定' }
    Write-Host "[i] 未指定 -Owner，使用 git user.name = $Owner（如不正确请用 -Owner 覆盖）" -ForegroundColor Yellow
}

$slug = "$Owner/$Repo"
$url = "https://github.com/$slug.git"

Push-Location $root
try {
    if (-not (Test-Path (Join-Path $root '.git'))) {
        Write-Host "[1/5] git init" -ForegroundColor Cyan
        git init -b main | Out-Null
    } else {
        Write-Host "[1/5] 已是 git 仓库，跳过 init" -ForegroundColor Cyan
    }

    Write-Host "[2/5] git add" -ForegroundColor Cyan
    git add -A

    $staged = git diff --cached --name-only
    if (-not $staged) {
        Write-Host "      没有需要提交的改动" -ForegroundColor Yellow
    } else {
        Write-Host "[3/5] git commit（$($staged.Count) 个文件）" -ForegroundColor Cyan
        git commit -m $Message | Out-Null
    }

    $existing = git remote
    if ($existing -contains 'origin') {
        Write-Host "[4/5] 更新 origin -> $url" -ForegroundColor Cyan
        git remote set-url origin $url
    } else {
        Write-Host "[4/5] 添加 origin -> $url" -ForegroundColor Cyan
        git remote add origin $url
    }

    Write-Host ""
    Write-Host "本地准备完成。" -ForegroundColor Green
    Write-Host "仓库地址: $url"
    Write-Host ""

    if ($Push) {
        Write-Host "[5/5] 推送（需要 GitHub 凭据）" -ForegroundColor Cyan
        git push -u origin main
        Write-Host ""
        Write-Host "推送完成，Actions 会自动开始构建:" -ForegroundColor Green
        Write-Host "  https://github.com/$slug/actions"
    } else {
        Write-Host "如需创建远端仓库并推送，二选一：" -ForegroundColor Yellow
        Write-Host "  1) 网页新建空仓库 https://github.com/new （名称 $Repo，不要勾选 README/.gitignore）"
        Write-Host "     然后执行: git push -u origin main"
        Write-Host "  2) 安装 gh CLI 后执行:"
        Write-Host "     gh repo create $slug --$Visibility --source . --remote origin --push"
    }
} finally {
    Pop-Location
}
