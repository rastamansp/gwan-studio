# start-real.ps1 - dev local com servicos reais (Claude, FFmpeg, YouTube)
# Carrega gwan-studio/.env + backend/.env.local e sobe Daphne na porta 3018.
#
# Uso:
#   cd gwan-studio; .\make.ps1 dev
#   cd backend; .\start-real.ps1

param([string]$Port = "3018")

$ErrorActionPreference = "Stop"
$here = Split-Path $MyInvocation.MyCommand.Path -Resolve
$studioRoot = Split-Path $here -Parent

function Import-DotEnvFile {
    param([string]$Path, [switch]$Override)
    if (-not (Test-Path $Path)) { return }
    foreach ($line in Get-Content $Path) {
        if ($line -match '^\s*#' -or $line -match '^\s*$') { continue }
        if ($line -match '^([^=]+)=(.*)$') {
            $k = $Matches[1].Trim()
            $v = $Matches[2].Trim()
            if ($Override -or -not (Test-Path "Env:$k")) {
                [Environment]::SetEnvironmentVariable($k, $v, 'Process')
            }
        }
    }
}

Import-DotEnvFile (Join-Path $studioRoot ".env")
Import-DotEnvFile (Join-Path $here ".env.local") -Override

$thumbSim = ($env:THUMBNAIL_SIMULATE -ne 'false')
$seoSim = ($env:SEO_SIMULATE -ne 'false')
if ((-not $thumbSim) -or (-not $seoSim)) {
    if (-not $env:ANTHROPIC_API_KEY) {
        Write-Error "ANTHROPIC_API_KEY obrigatoria quando THUMBNAIL_SIMULATE ou SEO_SIMULATE=false"
    }
}

$publishSim = ($env:PUBLISH_SIMULATE -ne 'false')
if ((-not $publishSim) -and (-not $env:YOUTUBE_REFRESH_TOKEN)) {
    Write-Warning "PUBLISH_SIMULATE=false mas YOUTUBE_REFRESH_TOKEN vazio."
    Write-Warning "Rode: .\.venv\Scripts\python.exe scripts\get_youtube_token.py"
}

$wingetPkgs = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages"
$ffmpegBin = Get-ChildItem $wingetPkgs -Filter "ffmpeg.exe" -Recurse -ErrorAction SilentlyContinue |
    Select-Object -First 1 | Select-Object -ExpandProperty DirectoryName
if ($ffmpegBin) {
    $env:PATH = "$ffmpegBin;$env:PATH"
    Write-Host "[OK] FFmpeg: $ffmpegBin"
} else {
    Write-Warning "FFmpeg nao encontrado - merge/export reais podem falhar."
    Write-Warning "Instale: winget install Gyan.FFmpeg"
}

Write-Host ""
Write-Host "Modos ativos:"
Write-Host "  MERGE_SIMULATE     = $($env:MERGE_SIMULATE)"
Write-Host "  EXPORT_SIMULATE    = $($env:EXPORT_SIMULATE)"
Write-Host "  THUMBNAIL_SIMULATE = $($env:THUMBNAIL_SIMULATE)"
Write-Host "  SEO_SIMULATE       = $($env:SEO_SIMULATE)"
Write-Host "  PUBLISH_SIMULATE   = $($env:PUBLISH_SIMULATE)"
if ($env:ANTHROPIC_API_KEY) {
    $tail = ($env:ANTHROPIC_API_KEY)[-8..-1] -join ''
    Write-Host "  ANTHROPIC_API_KEY  = sk-ant-***$tail"
}
Write-Host ""
Write-Host "Servidor: http://localhost:$Port"
Write-Host ""

& (Join-Path $here ".venv\Scripts\python.exe") manage.py runserver $Port
