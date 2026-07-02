# Bootstrap Gwan Studio — dev local (Windows)
# Uso: .\make.ps1 [setup|install|dev|migrate|youtube-token|health|help]

param(
    [Parameter(Position = 0)]
    [string]$cmd = "help"
)

$ErrorActionPreference = "Stop"
$StackRoot = $PSScriptRoot
$Backend = Join-Path $StackRoot "backend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$VenvPip = Join-Path $Backend ".venv\Scripts\pip.exe"

function Require-Venv {
    if (-not (Test-Path $VenvPython)) {
        throw "Venv não encontrado. Rode: .\make.ps1 setup"
    }
}

switch ($cmd) {
    "setup" {
        if (-not (Test-Path $Backend)) { throw "Pasta backend/ não encontrada" }
        if (-not (Test-Path $VenvPython)) {
            Write-Host "[gwan-studio] Criando venv..."
            python -m venv (Join-Path $Backend ".venv")
        }
        & $VenvPip install -r (Join-Path $Backend "requirements\phase0.txt")
        if (-not (Test-Path (Join-Path $Backend ".env.local"))) {
            Copy-Item (Join-Path $Backend ".env.local.example") (Join-Path $Backend ".env.local") -ErrorAction SilentlyContinue
        }
        if (-not (Test-Path (Join-Path $StackRoot ".env"))) {
            Copy-Item (Join-Path $StackRoot ".env.example") (Join-Path $StackRoot ".env")
            Write-Host "[gwan-studio] .env criado — preencha credenciais"
        }
        Write-Host "[gwan-studio] Setup OK. Próximo: .\make.ps1 dev"
    }

    "install" {
        Require-Venv
        & $VenvPip install -r (Join-Path $Backend "requirements\phase0.txt")
    }

    "migrate" {
        Require-Venv
        Push-Location $Backend
        & $VenvPython manage.py migrate
        Pop-Location
    }

    "dev" {
        Require-Venv
        Push-Location $Backend
        & (Join-Path $Backend "start-real.ps1")
        Pop-Location
    }

    "youtube-token" {
        Require-Venv
        Push-Location $Backend
        $secret = Join-Path $StackRoot "..\client_secret_792731767818-84rh1ug3v4ufm5oicgkfcdf7l71h3a51.apps.googleusercontent.com.json"
        if (-not (Test-Path $secret)) {
            $secret = Get-ChildItem (Join-Path $StackRoot "..") -Filter "client_secret*.json" | Select-Object -First 1 -ExpandProperty FullName
        }
        & $VenvPython scripts\get_youtube_token.py $secret
        Pop-Location
    }

    "health" {
        Require-Venv
        try {
            $code = curl.exe -s -o NUL -w "%{http_code}" http://localhost:3018/api/health/
            if ($code -eq "200") { Write-Host "OK http://localhost:3018/api/health/ ($code)" }
            else { Write-Host "WARN health retornou $code — servidor rodando?" }
        } catch {
            Write-Host "WARN servidor não responde em :3018 — rode .\make.ps1 dev"
        }
    }

    default {
        Write-Host "Uso: .\make.ps1 [setup|install|dev|migrate|youtube-token|health]"
        Write-Host "  setup          venv + pip install + .env"
        Write-Host "  install        pip install phase0.txt"
        Write-Host "  migrate        django migrate"
        Write-Host "  dev            sobe servidor real (Claude + FFmpeg + YouTube)"
        Write-Host "  youtube-token  OAuth one-shot → YOUTUBE_REFRESH_TOKEN"
        Write-Host "  health         GET /api/health/"
    }
}
