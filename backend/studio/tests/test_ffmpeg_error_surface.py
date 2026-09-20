"""
Regressão: falha de FFmpeg tem de chegar ao log do job com a mensagem do
processo, e extração de frames não pode devolver lista vazia em silêncio.

Origem: um `merged.mp4` de 0 byte (produzido pelo modo simulado quando o
source não existe em disco) fez o export falhar com
"returned non-zero exit status 3199971767" — número que ninguém decifra — e
fez o job de thumbnail registrar "0 frames extraídos" e mesmo assim seguir
para o Claude Vision, gerando 3 thumbnails a partir de nenhuma imagem.
"""
import os
import shutil
import subprocess
import tempfile

from django.test import SimpleTestCase

from infrastructure.ffmpeg.errors import FfmpegError, raise_if_failed, stderr_tail
from infrastructure.ffmpeg.frames import extract_frames


class FfmpegErrorMessageTests(SimpleTestCase):
    def test_mensagem_inclui_o_stderr_do_ffmpeg(self):
        erro = FfmpegError(
            3199971767, 'ffmpeg',
            stderr='ffmpeg version 8.1.1\n  configuration: ...\n'
                   'Error opening input: Invalid data found when processing input\n',
        )
        texto = str(erro)
        self.assertIn('3199971767', texto)
        self.assertIn('Invalid data found', texto)

    def test_mantem_o_tipo_calledprocesserror(self):
        # Quem já capturava CalledProcessError continua capturando.
        self.assertTrue(issubclass(FfmpegError, subprocess.CalledProcessError))

    def test_stderr_vazio_nao_polui_a_mensagem(self):
        self.assertNotIn('FFmpeg:', str(FfmpegError(1, 'ffmpeg', stderr='')))

    def test_stderr_tail_pega_o_fim_que_e_onde_o_erro_fica(self):
        self.assertEqual(stderr_tail('a\nb\nc\nd\ne', max_lines=2), 'd | e')

    def test_raise_if_failed_deixa_passar_sucesso(self):
        ok = subprocess.CompletedProcess(['ffmpeg'], 0, stdout='', stderr='')
        self.assertIsNone(raise_if_failed(ok))


class ExtractFramesTests(SimpleTestCase):
    def setUp(self):
        if not shutil.which('ffmpeg'):
            self.skipTest('ffmpeg não está no PATH')
        self.tmp = tempfile.mkdtemp(prefix='frames_test_')
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_video_invalido_levanta_em_vez_de_devolver_lista_vazia(self):
        vazio = os.path.join(self.tmp, 'merged.mp4')
        open(vazio, 'wb').close()

        with self.assertRaises(RuntimeError) as ctx:
            extract_frames(vazio, n=3)

        self.assertIn('Nenhum frame extraído', str(ctx.exception))
        self.assertIn('0 bytes', str(ctx.exception))
