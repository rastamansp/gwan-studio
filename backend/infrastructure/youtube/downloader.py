"""
Import de source a partir de um link do YouTube (alternativa ao upload de
arquivo) — usa yt-dlp para baixar o vídeo já em MP4 (h264/aac quando
disponível, evita remux extra no pipeline de merge/highlights).
"""
import re

_YOUTUBE_HOST_RE = re.compile(
    r'^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtube\.com/shorts/|youtu\.be/)', re.IGNORECASE,
)


class YouTubeDownloadError(Exception):
    """Falha ao baixar ou processar o vídeo do YouTube."""


def is_youtube_url(url: str) -> bool:
    return bool(url) and bool(_YOUTUBE_HOST_RE.match(url.strip()))


def download_youtube_video(url: str, output_path_no_ext: str) -> dict:
    """Baixa o vídeo do YouTube para `<output_path_no_ext>.mp4`.

    Retorna `{title, duration_sec, filepath}`. `output_path_no_ext` não deve
    incluir extensão — o yt-dlp decide o container final conforme o formato
    escolhido (forçamos mp4 via `merge_output_format`).
    """
    import yt_dlp

    ydl_opts = {
        'outtmpl': output_path_no_ext + '.%(ext)s',
        'format': 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
        # Downloads longos (jogos de futebol podem passar de 1h) são mais
        # sujeitos a quedas de conexão intermitentes — sem retry, um "Got
        # error: N bytes read, M more expected" no meio do download derruba
        # o import inteiro em vez de só tentar de novo o pedaço que faltou.
        'retries': 10,
        'fragment_retries': 10,
        'socket_timeout': 30,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            # merge_output_format força .mp4, mas prepare_filename pode retornar
            # a extensão original antes do merge — normaliza para .mp4.
            import os
            mp4_path = os.path.splitext(filepath)[0] + '.mp4'
            if os.path.exists(mp4_path):
                filepath = mp4_path
    except yt_dlp.utils.DownloadError as exc:
        raise YouTubeDownloadError(str(exc)) from exc

    return {
        'title': info.get('title') or 'video_youtube',
        'duration_sec': int(info.get('duration') or 0),
        'filepath': filepath,
    }
