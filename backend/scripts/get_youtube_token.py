"""
Script one-shot para obter o refresh_token do YouTube com o credential instalado.

Uso (a partir da pasta backend/):
    .venv/Scripts/python.exe scripts/get_youtube_token.py [path/to/client_secret.json]

Padrao: le o primeiro client_secret*.json em apps/ffmpeg-colab/ ou no diretorio pai.
"""
import json
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

# Procura o arquivo de credenciais
def _find_secret(arg: str | None) -> str:
    if arg and os.path.isfile(arg):
        return arg
    # Tenta pasta pai (apps/ffmpeg-colab/)
    here = os.path.dirname(os.path.abspath(__file__))
    search_dirs = [
        os.path.join(here, '..'),          # backend/
        os.path.join(here, '..', '..'),    # gwan-studio/
        os.path.join(here, '..', '..', '..'),  # apps/ffmpeg-colab/
    ]
    for d in search_dirs:
        for f in os.listdir(os.path.abspath(d)):
            if f.startswith('client_secret') and f.endswith('.json'):
                path = os.path.join(os.path.abspath(d), f)
                print(f'[get_youtube_token] Usando: {path}')
                return path
    raise FileNotFoundError(
        'Nenhum client_secret*.json encontrado. Passe o caminho como argumento.'
    )


def main():
    secrets_file = _find_secret(sys.argv[1] if len(sys.argv) > 1 else None)

    flow = InstalledAppFlow.from_client_secrets_file(secrets_file, SCOPES)
    print('\n[get_youtube_token] Abrindo navegador para autorização OAuth...')
    creds = flow.run_local_server(port=0, open_browser=True)

    print('\n' + '=' * 60)
    print('Autorização concluída! Adicione ao seu .env.local:\n')
    print(f'YOUTUBE_REFRESH_TOKEN={creds.refresh_token}')
    print('=' * 60)
    print('\nDepois reinicie o servidor com start-real.ps1')


if __name__ == '__main__':
    main()
