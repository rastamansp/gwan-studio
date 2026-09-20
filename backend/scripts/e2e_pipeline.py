"""
Teste end-to-end do pipeline pelo navegador (Playwright).

Percorre o fluxo inteiro como um operador: login → criar projeto → upload →
highlights → export → SEO → thumbnails. Nada é chamado por baixo da UI; se um
botão sumir ou parar de habilitar, o teste quebra.

O fixture de vídeo é GERADO pelo FFmpeg (não versionado): 24s com três rajadas
de áudio em instantes conhecidos, então `audio_energy_peaks` tem de achar picos
perto de 5s, 13s e 20s. Vídeo de verdade levaria minutos e não caberia no repo.

    python scripts/e2e_pipeline.py                  # fluxo completo
    python scripts/e2e_pipeline.py --pular-ia       # para no export (não chama Claude)
    python scripts/e2e_pipeline.py --exigir-real    # falha se alguma etapa rodar simulada
    python scripts/e2e_pipeline.py --headed         # ver o navegador trabalhando

Pré-requisitos: servidor de pé (`.\\start-real.ps1`), FFmpeg no PATH e
`pip install -r requirements/e2e.txt` + `python -m playwright install chromium`.
"""
import argparse
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FIXTURE_DIR = BASE_DIR / '.e2e'
FIXTURE = FIXTURE_DIR / 'fixture-highlights.mp4'

# Rajadas de áudio nestes intervalos — é o que vira pico de energia.
PICOS_ESPERADOS = [(4, 6), (12, 14), (19, 21)]
DURACAO_FIXTURE = 24

# Jobs pesados: FFmpeg em vídeo real e chamadas de rede ao Claude.
TIMEOUT_JOB_MS = 300_000


class FalhaE2E(Exception):
    pass


def log(msg: str) -> None:
    print(msg, flush=True)


def gerar_fixture() -> Path:
    """Vídeo sintético com picos de áudio em instantes conhecidos."""
    if FIXTURE.exists():
        log(f'[fixture] reaproveitando {FIXTURE.name} ({FIXTURE.stat().st_size // 1024} KB)')
        return FIXTURE

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    rajadas = '+'.join(f'between(t,{ini},{fim})' for ini, fim in PICOS_ESPERADOS)
    audio = (
        f"aevalsrc='(0.05+0.85*({rajadas}))*sin(2*PI*440*t)'"
        f':s=44100:d={DURACAO_FIXTURE}'
    )
    log('[fixture] gerando com FFmpeg…')
    resultado = subprocess.run(
        [
            'ffmpeg', '-y',
            '-f', 'lavfi', '-i', f'testsrc2=size=640x360:rate=30:duration={DURACAO_FIXTURE}',
            '-f', 'lavfi', '-i', audio,
            '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-shortest', str(FIXTURE),
        ],
        capture_output=True, text=True, timeout=300,
    )
    if resultado.returncode != 0:
        raise FalhaE2E(f'FFmpeg não gerou o fixture: {resultado.stderr[-400:]}')
    log(f'[fixture] {FIXTURE.name} ({FIXTURE.stat().st_size // 1024} KB)')
    return FIXTURE


def checar_simulado(page, etapa: str, exigir_real: bool) -> None:
    """A marca `[SIMULADO]` fica no log do job, dentro de um <details> fechado —
    `text_content()` lê mesmo recolhido, `inner_text()` não leria."""
    texto = page.locator('body').text_content() or ''
    if '[SIMULADO]' in texto:
        if exigir_real:
            raise FalhaE2E(
                f'{etapa} rodou em modo SIMULADO e --exigir-real foi pedido. '
                f'Confira as flags *_SIMULATE no .env.local do servidor.'
            )
        log(f'    ⚠ {etapa} rodou SIMULADO (o servidor está com *_SIMULATE=true)')


def clicar(page, nome: str, tentativas: int = 8) -> None:
    """Clique com repetição.

    Os painéis de etapa são recarregados pelo HTMX em intervalo curto; um clique
    que cai entre a troca encontra o botão "detached from the DOM". A repetição
    do Playwright sozinha não resolve porque o elemento volta a ser substituído
    dentro da mesma espera.
    """
    ultimo = None
    for _ in range(tentativas):
        try:
            page.get_by_role('button', name=nome).first.click(timeout=5_000)
            return
        except Exception as exc:  # detached / re-render em curso
            ultimo = exc
            page.wait_for_timeout(1_000)
    raise FalhaE2E(f'não consegui clicar em "{nome}" após {tentativas} tentativas: {ultimo}')


def esperar_job(page, marcador: str, etapa: str) -> None:
    """Espera o painel do job chegar a um estado terminal — sucesso pelo marcador
    da etapa, falha pelo texto de erro, para não ficar pendurado até o timeout."""
    sucesso = page.get_by_text(marcador, exact=False).first
    # Inclui as recusas de validação ("Adicione pelo menos uma fonte…"), que não
    # criam job nenhum: sem elas aqui, o teste ficava pendurado até o timeout
    # esperando por um job que nunca ia existir.
    erro = page.get_by_text(
        re.compile(r'Falhou|Erro no|erro:|Adicione pelo menos|já foram exportados', re.I)
    ).first
    limite = time.time() + TIMEOUT_JOB_MS / 1000
    while time.time() < limite:
        if sucesso.count() and sucesso.is_visible():
            return
        if erro.count() and erro.is_visible():
            raise FalhaE2E(f'{etapa} falhou: {erro.text_content()}')
        page.wait_for_timeout(1000)
    raise FalhaE2E(f'{etapa} não terminou em {TIMEOUT_JOB_MS // 1000}s')


def rodar(args) -> int:
    from playwright.sync_api import sync_playwright

    fixture = gerar_fixture()
    base = args.base_url.rstrip('/')
    nome_projeto = f'E2E {uuid.uuid4().hex[:8]}'
    erros_console: list[str] = []

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=not args.headed, slow_mo=args.slow_mo)
        page = navegador.new_page(viewport={'width': 1280, 'height': 900})
        page.on('pageerror', lambda e: erros_console.append(str(e)))
        page.set_default_timeout(30_000)

        try:
            log(f'\n→ {base} | projeto "{nome_projeto}"')

            # 1. Login
            page.goto(f'{base}/login/')
            page.get_by_role('textbox', name='Usuario').fill(args.usuario)
            page.get_by_role('textbox', name='Senha').fill(args.senha)
            page.get_by_role('button', name='Entrar no Studio').click()
            page.wait_for_url('**/dashboard/')
            log('  ✓ login')

            # 2. Criar projeto (highlights só existem em project_type=futebol)
            page.goto(f'{base}/projects/')
            page.get_by_role('button', name='Novo projeto').click()
            page.get_by_role('textbox', name='Nome do projeto').fill(nome_projeto)
            page.get_by_label('Tipo de projeto', exact=True).select_option(label='Futebol')
            page.get_by_role('button', name='Criar projeto').click()
            page.wait_for_url(re.compile(r'/projects/[0-9a-f-]{36}/$'))
            projeto_id = page.url.rstrip('/').split('/')[-1]
            log(f'  ✓ projeto criado ({projeto_id})')

            # 3. Upload.
            # O input é `@change="handleFiles(...)"` do Alpine: preencher o campo
            # antes do Alpine inicializar deixa o arquivo na fila da tela e NÃO
            # envia nada. Por isso duas guardas — esperar o Alpine e exigir a
            # resposta do servidor. Conferir só o nome do arquivo na página é
            # falso positivo: ele aparece vindo do próprio navegador.
            page.goto(f'{base}/projects/{projeto_id}/sources/')
            page.wait_for_function('() => window.Alpine && window.Alpine.version')
            with page.expect_response(
                lambda r: '/sources/upload/' in r.url, timeout=180_000,
            ) as resposta:
                page.locator('input[type=file]').first.set_input_files(str(fixture))
            status = resposta.value.status
            if status != 200:
                raise FalhaE2E(f'upload devolveu HTTP {status}')
            # E confirma na lista renderizada pelo servidor, não na fila local.
            page.goto(f'{base}/projects/{projeto_id}/sources/')
            if fixture.name not in (page.locator('body').text_content() or ''):
                raise FalhaE2E('upload aceito mas a fonte não aparece na lista do servidor')
            log('  ✓ upload da fonte')

            # 4. Highlights
            page.goto(f'{base}/projects/{projeto_id}/highlights/')
            clicar(page, 'Detectar Highlights')
            esperar_job(page, 'Highlights Detectados', 'highlights')
            checar_simulado(page, 'highlights', args.exigir_real)
            momentos = page.get_by_role('button', name='Excluir').count()
            if momentos == 0:
                raise FalhaE2E('nenhum momento detectado — os picos do fixture não chegaram ao Claude')
            log(f'  ✓ highlights ({momentos} momentos)')

            # 5. Export com re-encode (exercita mais FFmpeg que o stream copy)
            clicar(page, 'Próximo: Export')
            page.get_by_role('combobox').first.select_option(label='H.264 / AVC')
            page.get_by_role('combobox').nth(1).select_option(label='HD — 1280×720')
            clicar(page, 'Exportar')
            esperar_job(page, 'Export Concluído', 'export')
            checar_simulado(page, 'export', args.exigir_real)
            log('  ✓ export')

            etapas_ok = 3
            if args.pular_ia:
                log('  – SEO e thumbnails pulados (--pular-ia)')
            else:
                # 6. SEO
                clicar(page, 'Próximo: SEO')
                clicar(page, 'Gerar com Claude')
                esperar_job(page, 'Aprovar SEO', 'seo')
                checar_simulado(page, 'seo', args.exigir_real)
                clicar(page, 'Aprovar SEO')
                page.get_by_role('button', name='Aprovado!').wait_for()
                log('  ✓ seo')

                # 7. Thumbnails — a regressão que motivou este teste morava aqui:
                # sem frames extraídos o job seguia e "gerava" 3 variantes.
                clicar(page, 'Próximo: Thumbnails')
                clicar(page, 'Gerar com Claude Vision')
                esperar_job(page, 'Thumbnails Geradas', 'thumbnails')
                checar_simulado(page, 'thumbnails', args.exigir_real)
                variantes = page.get_by_text(re.compile(r'^Variante [ABC]$')).count()
                if variantes != 3:
                    raise FalhaE2E(f'esperava 3 variantes de thumbnail, vi {variantes}')
                log(f'  ✓ thumbnails ({variantes} variantes)')
                etapas_ok = 5

            # 8. O rail lateral só reflete o estado depois de recarregar (o HTMX
            # troca apenas o painel) — por isso a conferência final é num GET novo.
            page.goto(f'{base}/projects/{projeto_id}/')
            progresso = page.get_by_text(re.compile(r'^\d/6$')).first.text_content()
            if progresso != f'{etapas_ok}/6':
                raise FalhaE2E(f'progresso {progresso}, esperado {etapas_ok}/6')
            log(f'  ✓ pipeline em {progresso}')

            if erros_console:
                log(f'\n⚠ {len(erros_console)} erro(s) de JavaScript durante o fluxo:')
                for e in dict.fromkeys(erros_console):
                    log(f'    {e.splitlines()[0]}')

            log('\nE2E OK\n')
            return 0

        except Exception as exc:
            destino = FIXTURE_DIR / 'falha.png'
            try:
                page.screenshot(path=str(destino), full_page=True)
                log(f'\nE2E FALHOU: {exc}\nScreenshot: {destino}\n')
            except Exception:
                log(f'\nE2E FALHOU: {exc}\n')
            return 1
        finally:
            navegador.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--base-url', default=os.environ.get('E2E_BASE_URL', 'http://localhost:3018'))
    parser.add_argument('--usuario', default=os.environ.get('E2E_USER', 'demo'))
    parser.add_argument('--senha', default=os.environ.get('E2E_PASSWORD', 'gwan-demo'))
    parser.add_argument('--headed', action='store_true', help='mostra o navegador')
    parser.add_argument('--slow-mo', type=int, default=0, help='ms entre ações (depuração)')
    parser.add_argument('--pular-ia', action='store_true', help='para no export; não chama o Claude')
    parser.add_argument('--exigir-real', action='store_true', help='falha se alguma etapa rodar simulada')
    args = parser.parse_args()

    try:
        return rodar(args)
    except FalhaE2E as exc:
        log(f'\nE2E FALHOU: {exc}\n')
        return 1


if __name__ == '__main__':
    sys.exit(main())
