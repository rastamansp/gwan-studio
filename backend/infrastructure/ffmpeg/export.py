"""
F04 — export do vídeo final via FFmpeg.
Input: merged.mp4  →  Output: final.mp4 com codec/resolução/bitrate configuráveis.
"""
import os
import shutil
import subprocess


RESOLUTION_MAP = {
    'original': None,
    '4k':       '3840:2160',
    'fhd':      '1920:1080',
    'hd':       '1280:720',
}


def run_ffmpeg_export(
    merged_path: str,
    output_path: str,
    codec: str = 'copy',
    resolution: str = 'original',
    bitrate: str = '',
) -> list[str]:
    """
    Exporta merged.mp4 para final.mp4.
    codec: 'copy' | 'h264' | 'h265'
    resolution: 'original' | '4k' | 'fhd' | 'hd'
    bitrate: ex. '8000k', '50M', '' = manter original
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    cmd = ['ffmpeg', '-y', '-i', merged_path]

    if codec == 'copy':
        cmd += ['-c', 'copy']
    else:
        vcodec = 'libx264' if codec == 'h264' else 'libx265'
        cmd += ['-c:v', vcodec]
        scale = RESOLUTION_MAP.get(resolution)
        if scale:
            cmd += ['-vf', f'scale={scale}']
        if bitrate:
            cmd += ['-b:v', bitrate]
        cmd += ['-c:a', 'copy']

    cmd.append(output_path)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    log_lines = [l for l in result.stderr.split('\n') if l.strip()]
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, 'ffmpeg', stderr=result.stderr)
    return log_lines


def simulate_export(
    merged_path: str,
    output_path: str,
    codec: str = 'copy',
    resolution: str = 'original',
    bitrate: str = '',
) -> list[str]:
    """Dev bypass — copia merged.mp4 como final.mp4."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if merged_path and os.path.exists(merged_path):
        shutil.copy2(merged_path, output_path)
    else:
        open(output_path, 'wb').close()
    preset_label = f'{codec.upper()} / {resolution}' + (f' @ {bitrate}' if bitrate else '')
    return [
        f'[SIMULADO] Exportando com preset: {preset_label}',
        f'[SIMULADO] Input:  {merged_path}',
        f'[SIMULADO] Output: {output_path}',
        '[SIMULADO] Export concluído com sucesso (modo simulação)',
    ]
