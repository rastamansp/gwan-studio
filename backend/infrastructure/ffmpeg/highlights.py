"""
F17 — extração de áudio, picos de energia e corte/concat dos highlights.

Mesma convenção do F03 (infrastructure/ffmpeg/merge.py): funções puras de
subprocess, sem I/O de rede, com uma variante `simulate_*` para dev sem
FFmpeg/librosa instalados.
"""
import os
import shutil
import subprocess


def extract_audio_wav(video_path: str, output_wav_path: str) -> None:
    """Extrai áudio mono 16kHz — formato ótimo para análise de energia e Whisper."""
    os.makedirs(os.path.dirname(output_wav_path), exist_ok=True)
    result = subprocess.run(
        ['ffmpeg', '-y', '-i', video_path, '-ac', '1', '-ar', '16000', '-vn', output_wav_path],
        capture_output=True, text=True, timeout=1800,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, 'ffmpeg', stderr=result.stderr)


def audio_energy_peaks(wav_path: str, top_n: int = 40) -> list[float]:
    """RF03 — picos de energia RMS do áudio (torcida, narrador em alta).

    Algoritmo (ver F17-futebol-highlights.md §5.2):
      1. RMS por frame (hop_length=2048)
      2. Suavização por média móvel (15 frames)
      3. Threshold dinâmico = média + desvio padrão
      4. Agrupamento de índices contíguos (gap > 3s → novo grupo)
      5. Pico de cada grupo, retorna os `top_n` mais altos, em ordem cronológica
    """
    import librosa
    import numpy as np

    y, sr = librosa.load(wav_path, sr=None, mono=True)
    hop_length = 2048
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]

    window = 15
    kernel = np.ones(window) / window
    smoothed = np.convolve(rms, kernel, mode='same')

    threshold = smoothed.mean() + smoothed.std()
    candidate_idx = np.where(smoothed >= threshold)[0]
    if candidate_idx.size == 0:
        return []

    frame_times = librosa.frames_to_time(candidate_idx, sr=sr, hop_length=hop_length)

    groups: list[list[int]] = [[candidate_idx[0]]]
    for prev_t, idx, t in zip(frame_times, candidate_idx[1:], frame_times[1:]):
        if t - prev_t > 3.0:
            groups.append([idx])
        else:
            groups[-1].append(idx)

    peaks = []
    for group in groups:
        best_idx = max(group, key=lambda i: smoothed[i])
        peaks.append(float(librosa.frames_to_time(best_idx, sr=sr, hop_length=hop_length)))

    peaks_sorted_by_energy = sorted(
        peaks, key=lambda t: smoothed[librosa.time_to_frames(t, sr=sr, hop_length=hop_length)], reverse=True,
    )
    top_peaks = peaks_sorted_by_energy[:top_n]
    return sorted(top_peaks)


def simulate_energy_peaks(duration_sec: float, top_n: int = 40) -> list[float]:
    """[SIMULADO] Picos distribuídos uniformemente, sem análise real de áudio."""
    if duration_sec <= 0:
        return []
    count = min(top_n, max(1, int(duration_sec // 90)))
    step = duration_sec / (count + 1)
    return [round(step * (i + 1), 1) for i in range(count)]


def cut_and_concat(clips: list[tuple[str, float, float]], output_path: str) -> list[str]:
    """RF06/RN-F17-03 — corta cada intervalo (podendo vir de sources diferentes,
    ex.: 2 tempos de jogo) e concatena. Re-encode (`-c:v libx264 -c:a aac`),
    diferente do merge F03 (stream copy), pois cortes não caem em keyframe.

    `clips`: lista de `(video_path, start, end)` na ordem final desejada.
    """
    import tempfile

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    tmp_dir = tempfile.mkdtemp(prefix='highlight_clips_')
    log_lines = []
    clip_paths = []
    try:
        for i, (video_path, start, end) in enumerate(clips):
            clip_path = os.path.join(tmp_dir, f'clip_{i:03d}.mp4')
            result = subprocess.run(
                [
                    'ffmpeg', '-y',
                    '-ss', str(start), '-to', str(end),
                    '-i', video_path,
                    '-c:v', 'libx264', '-c:a', 'aac',
                    clip_path,
                ],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, 'ffmpeg', stderr=result.stderr)
            clip_paths.append(clip_path)
            log_lines.append(f'[OK] Corte {i + 1}/{len(clips)}: {start:.1f}s–{end:.1f}s')

        concat_file = os.path.join(tmp_dir, 'concat.txt')
        with open(concat_file, 'w', encoding='utf-8') as f:
            for clip_path in clip_paths:
                f.write(f"file '{clip_path}'\n")

        result = subprocess.run(
            ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_file, '-c', 'copy', output_path],
            capture_output=True, text=True, timeout=1800,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, 'ffmpeg', stderr=result.stderr)

        size_mb = os.path.getsize(output_path) / (1024 * 1024) if os.path.exists(output_path) else 0
        log_lines.append(f'[OK] Highlight concluído — {os.path.basename(output_path)} ({size_mb:.1f} MB)')
        return log_lines
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def simulate_cut_and_concat(clips: list[tuple[str, float, float]], output_path: str) -> list[str]:
    """[SIMULADO] Copia o primeiro source como highlight final, sem cortar de fato."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    first_video = clips[0][0] if clips else None
    if first_video and os.path.exists(first_video):
        shutil.copy2(first_video, output_path)
    else:
        open(output_path, 'wb').close()
    return [
        '[SIMULADO] FFmpeg/librosa não usados — copiando primeiro source como highlight final',
        f'[SIMULADO] {len(clips)} intervalo(s) seriam cortados e concatenados',
        '[SIMULADO] Highlight concluído com sucesso (modo simulação)',
    ]
