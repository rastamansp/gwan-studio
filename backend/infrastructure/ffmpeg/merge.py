"""
F03 — merge de clipes via FFmpeg stream copy.
"""
import os
import shutil
import subprocess
import tempfile


def run_ffmpeg_merge(source_paths: list[str], output_path: str) -> list[str]:
    """
    Concatena sources com FFmpeg (-c copy, sem re-encode).
    Retorna lista de linhas de log (stderr do ffmpeg).
    Levanta FileNotFoundError se ffmpeg não estiver no PATH,
    ou CalledProcessError se o processo falhar.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.txt', delete=False, encoding='utf-8'
    ) as f:
        for path in source_paths:
            safe = path.replace("'", "\\'")
            f.write(f"file '{safe}'\n")
        concat_file = f.name

    try:
        result = subprocess.run(
            [
                'ffmpeg', '-y',
                '-f', 'concat', '-safe', '0',
                '-i', concat_file,
                '-c', 'copy',
                output_path,
            ],
            capture_output=True,
            text=True,
            timeout=3600,
        )
        log_lines = [l for l in result.stderr.split('\n') if l.strip()]
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, 'ffmpeg', stderr=result.stderr
            )
        return log_lines
    finally:
        try:
            os.unlink(concat_file)
        except OSError:
            pass


def simulate_merge(source_paths: list[str], output_path: str) -> list[str]:
    """
    Simula merge para dev sem FFmpeg: copia o primeiro source como output.
    Ativado via MERGE_SIMULATE=True em settings.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if source_paths and os.path.exists(source_paths[0]):
        shutil.copy2(source_paths[0], output_path)
    else:
        open(output_path, 'wb').close()
    return [
        '[SIMULADO] FFmpeg não encontrado — copiando primeiro source como merged.mp4',
        f'[SIMULADO] Input:  {source_paths[0] if source_paths else "(vazio)"}',
        f'[SIMULADO] Output: {output_path}',
        '[SIMULADO] Merge concluído com sucesso (modo simulação)',
    ]
