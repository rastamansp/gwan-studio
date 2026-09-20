"""
Erro de FFmpeg que carrega a mensagem do processo, não só o exit code.

Motivo: `subprocess.CalledProcessError.__str__` imprime apenas
"Command 'ffmpeg' returned non-zero exit status <n>". O FFmpeg devolve o
AVERROR como inteiro sem sinal (ex.: 3199971767 = -1094995529 =
AVERROR_INVALIDDATA), então o número sozinho não diz nada a quem lê o log do
job — e o `stderr`, que explica o problema em uma linha, era capturado e
descartado.
"""
import subprocess


def stderr_tail(stderr: str | None, max_lines: int = 3) -> str:
    """Últimas linhas úteis do stderr — o FFmpeg imprime banner e configuração
    antes do erro, que fica sempre no fim."""
    if not stderr:
        return ''
    lines = [l.strip() for l in stderr.splitlines() if l.strip()]
    return ' | '.join(lines[-max_lines:])


class FfmpegError(subprocess.CalledProcessError):
    """Mantém o tipo `CalledProcessError` (nada muda para quem captura), só
    acrescenta a mensagem do FFmpeg ao texto do erro."""

    def __str__(self) -> str:
        tail = stderr_tail(self.stderr)
        return f'{super().__str__()} FFmpeg: {tail}' if tail else super().__str__()


def raise_if_failed(result: subprocess.CompletedProcess) -> None:
    """Levanta `FfmpegError` quando o processo terminou com código != 0."""
    if result.returncode != 0:
        raise FfmpegError(result.returncode, 'ffmpeg', stderr=result.stderr)
