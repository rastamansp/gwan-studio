"""
F05 — Extração de frames candidatos para thumbnail.
Usa ffmpeg para extrair N frames uniformemente distribuídos.
"""
import base64
import os
import subprocess
import tempfile


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
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(n):
            t = duration * (i + 0.5) / n
            out = os.path.join(tmpdir, f'frame_{i:02d}.jpg')
            subprocess.run(
                ['ffmpeg', '-y', '-ss', str(t), '-i', video_path,
                 '-vframes', '1', '-q:v', '5', out],
                capture_output=True, timeout=30,
            )
            if os.path.exists(out):
                with open(out, 'rb') as f:
                    frames_b64.append(base64.b64encode(f.read()).decode())

    return frames_b64
