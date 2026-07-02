"""
F17 — ponte RabbitMQ com o highlight-worker externo (Whisper + Claude reais).

Contrato exato definido em
apps/ffmpeg-colab/highlight-worker/src/gwan_highlight_worker/domain/models.py
(`HighlightRequest`/`HighlightResult`) — qualquer mudança de payload precisa
ser espelhada nos dois lados.

Fluxo (RPC síncrono sobre pub/sub, já que o worker publica em um exchange
topic, não numa fila de resposta dedicada):
  1. Declara uma fila exclusiva própria, bindada ao exchange `highlight`
     com a routing key `highlight.results`, ANTES de publicar o request
     (evita perder a resposta por corrida).
  2. Publica o request em `highlight.detect`.
  3. Consome a fila exclusiva até achar uma mensagem com o `job_id` esperado
     (mensagens de outros jobs em voo são reconhecidas e descartadas) ou
     estourar o timeout.
"""
import json
import time
import uuid


class HighlightWorkerTimeoutError(Exception):
    """O highlight-worker (GPU externo) não respondeu dentro do timeout configurado."""


class HighlightWorkerFailedError(Exception):
    """O highlight-worker processou o job e retornou status=failed."""


class RabbitMqHighlightWorkerClient:
    def __init__(self, url: str, queue: str, exchange: str, routing_key: str, timeout_sec: int = 900):
        self.url = url
        self.queue = queue
        self.exchange = exchange
        self.routing_key = routing_key
        self.timeout_sec = timeout_sec

    def detect_moments(
        self,
        *,
        project_id: str,
        source_id: str,
        audio_wav_key: str,
        energy_peaks: list[float],
        importancia_min: int,
    ) -> list[dict]:
        """Publica o job e bloqueia até a transcrição+análise real voltar.

        Retorna `[{timestamp, tipo, descricao, importancia}, ...]` — mesmo
        formato do adapter provisório (`ClaudeHighlightAnalyzer`), para que
        o restante do pipeline (merge_moments, HighlightMomentModel) não
        precise saber qual dos dois gerou o resultado.
        """
        import pika

        job_id = uuid.uuid4().hex
        request = {
            'job_id': job_id,
            'project_id': project_id,
            'source_id': source_id,
            'audio_wav_key': audio_wav_key,
            'energy_peaks': energy_peaks,
            'importancia_min': importancia_min,
        }

        connection = pika.BlockingConnection(pika.URLParameters(self.url))
        try:
            channel = connection.channel()

            channel.exchange_declare(exchange=self.exchange, exchange_type='topic', durable=True)
            result_queue = channel.queue_declare(queue='', exclusive=True, auto_delete=True).method.queue
            channel.queue_bind(exchange=self.exchange, queue=result_queue, routing_key=self.routing_key)

            channel.queue_declare(queue=self.queue, durable=True)
            channel.basic_publish(
                exchange='',
                routing_key=self.queue,
                body=json.dumps(request).encode('utf-8'),
                properties=pika.BasicProperties(content_type='application/json', delivery_mode=2),
            )

            deadline = time.monotonic() + self.timeout_sec
            for method, _properties, body in channel.consume(result_queue, inactivity_timeout=5):
                if method is None:
                    if time.monotonic() >= deadline:
                        raise HighlightWorkerTimeoutError(
                            f'highlight-worker não respondeu em {self.timeout_sec}s (job {job_id})'
                        )
                    continue

                channel.basic_ack(method.delivery_tag)
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    continue
                if payload.get('job_id') != job_id:
                    continue  # resultado de outro job em voo — descarta e segue esperando

                if payload.get('status') != 'done':
                    raise HighlightWorkerFailedError(
                        payload.get('error') or 'highlight-worker retornou status=failed'
                    )

                return [
                    {
                        'timestamp': m['timestamp_sec'],
                        'tipo': m['tipo'],
                        'descricao': m['descricao'],
                        'importancia': m['importancia'],
                    }
                    for m in payload.get('moments', [])
                ]

            raise HighlightWorkerTimeoutError(
                f'highlight-worker não respondeu em {self.timeout_sec}s (job {job_id})'
            )
        finally:
            connection.close()
