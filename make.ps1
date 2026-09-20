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

    "e2e-setup" {
        Require-Venv
        & $VenvPip install -r (Join-Path $Backend "requirements\e2e.txt")
        & $VenvPython -m playwright install chromium
        Write-Host "[gwan-studio] E2E pronto. Rode: .\make.ps1 e2e"
    }

    "e2e" {
        Require-Venv
        Push-Location $Backend
        # Repassa o que vier depois do alvo: --pular-ia, --headed, --exigir-real...
        & $VenvPython scripts\e2e_pipeline.py @args
        $rc = $LASTEXITCODE
        Pop-Location
        exit $rc
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
        # Nada de caracteres fora do ASCII aqui: o Windows PowerShell 5.1 le este
        # arquivo (UTF-8 sem BOM) como ANSI, e uma seta "->" em UTF-8 termina no
        # byte 0x92, que em CP1252 e uma aspa simples — ela fechava a string e
        # quebrava o parser do script inteiro.
        Write-Host "Uso: .\make.ps1 [setup|install|dev|migrate|youtube-token|health|e2e-setup|e2e]"
        Write-Host "  setup          venv + pip install + .env"
        Write-Host "  install        pip install phase0.txt"
        Write-Host "  migrate        django migrate"
        Write-Host "  dev            sobe servidor real (Claude + FFmpeg + YouTube)"
        Write-Host "  youtube-token  OAuth one-shot -> YOUTUBE_REFRESH_TOKEN"
        Write-Host "  health         GET /api/health/"
        Write-Host "  e2e-setup      instala Playwright + Chromium (uma vez)"
        Write-Host "  e2e            teste end-to-end pelo navegador"
        Write-Host "                 extras: --pular-ia --exigir-real --headed"
    }
}
