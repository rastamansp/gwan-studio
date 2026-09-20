"""
F05 — Extração de frames candidatos para thumbnail.
Usa ffmpeg para extrair N frames uniformemente distribuídos.
"""
import base64
import os
import subprocess
import tempfile

from infrastructure.ffmpeg.errors import stderr_tail


def extract_frames(video_path: str, n: int = 6) -> list[str]:
    """
    Extrai N frames do vídeo em intervalos uniformes.
    Retorna lista de strings base64 (JPEG).
    Levanta FileNotFoundError se ffmpeg não estiver no PATH.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f'Vídeo não encontrado: {video_path}')

    # Descobrir duração via ffprobe
    probe = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', video_path],
        capture_output=True, text=True, timeout=30,
    )
    import json
    try:
        duration = float(json.loads(probe.stdout)['format']['duration'])
    except Exception:
        duration = 60.0

    frames_b64 = []
    last_stderr = ''
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(n):
            t = duration * (i + 0.5) / n
            out = os.path.join(tmpdir, f'frame_{i:02d}.jpg')
            result = subprocess.run(
                ['ffmpeg', '-y', '-ss', str(t), '-i', video_path,
                 '-vframes', '1', '-q:v', '5', out],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                # Um instante isolado pode falhar (vídeo curto, seek além do fim)
                # sem invalidar os demais — guarda o motivo para o caso de nenhum
                # frame sair.
                last_stderr = result.stderr or ''
                continue
            if os.path.exists(out):
                with open(out, 'rb') as f:
                    frames_b64.append(base64.b64encode(f.read()).decode())

    if not frames_b64:
        # Sem isto o job seguia para o Claude Vision com zero imagens e ainda
        # registrava "3 planos recebidos" — thumbnails montadas a partir de nada.
        raise RuntimeError(
            f'Nenhum frame extraído de {os.path.basename(video_path)} '
            f'({os.path.getsize(video_path)} bytes). {stderr_tail(last_stderr)}'.strip()
        )

    return frames_b64
