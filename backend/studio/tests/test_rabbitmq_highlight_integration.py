"""
F17 — teste de integração REAL contra RabbitMQ (sem mock de pika).

Não depende de GPU/Whisper: simula o lado do highlight-worker com uma thread
que consome `highlight.detect` e publica em `highlight.results`, exatamente
como o worker real faz (mesmo contrato de fila/exchange/payload). Isso trava
a ponte Django→RabbitMQ→worker→Django de ponta a ponta.

Requer um RabbitMQ real acessível (docker-compose.dev.yml do gwan-studio,
`amqp://guest:guest@localhost:5673/`). Se não estiver no ar, o teste é
pulado — não deve quebrar quem roda a suíte sem a infra de dev.
"""
import json
import threading

from django.test import SimpleTestCase

from infrastructure.messaging.rabbitmq_highlight_client import (
    HighlightWorkerFailedError, HighlightWorkerTimeoutError, RabbitMqHighlightWorkerClient,
)

RABBITMQ_URL = 'amqp://guest:guest@localhost:5673/'
# Fila própria do teste — NUNCA reaproveitar 'highlight.detect': se um
# highlight-worker real estiver rodando (docker-compose --profile worker),
# ele consome a mensagem de teste antes da thread fake abaixo e tenta baixar
# um audio_wav_key que não existe, quebrando o teste por corrida.
QUEUE = 'highlight.detect.integration_test'
EXCHANGE = 'highlight'
ROUTING_KEY = 'highlight.results'


def _rabbitmq_available() -> bool:
    try:
        import pika
        connection = pika.BlockingConnection(
            pika.URLParameters(RABBITMQ_URL),
        )
        connection.close()
        return True
    except Exception:
        return False


def _run_fake_worker(response_builder, stop_event):
    """Consome UMA mensagem de `highlight.detect` e publica a resposta
    montada por `response_builder(request: dict) -> dict`, imitando o
    highlight-worker real (mesmo par fila/exchange)."""
    import pika

    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    try:
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE, durable=True)
        channel.exchange_declare(exchange=EXCHANGE, exchange_type='topic', durable=True)

        for method, _properties, body in channel.consume(QUEUE, inactivity_timeout=1):
            if stop_event.is_set():
                break
            if method is None:
                continue
            request = json.loads(body)
            channel.basic_ack(method.delivery_tag)

            result = response_builder(request)
            channel.basic_publish(
                exchange=EXCHANGE,
                routing_key=ROUTING_KEY,
                body=json.dumps(result).encode('utf-8'),
                properties=pika.BasicProperties(content_type='application/json', delivery_mode=2),
            )
            break
    finally:
        connection.close()


class RabbitMqHighlightIntegrationTests(SimpleTestCase):
    def setUp(self):
        if not _rabbitmq_available():
            self.skipTest(
                'RabbitMQ não disponível em amqp://guest:guest@localhost:5673/ — '
                'suba `docker compose -f gwan-studio/docker-compose.dev.yml up -d` para rodar este teste.'
            )

    def _client(self, timeout_sec=15):
        return RabbitMqHighlightWorkerClient(
            url=RABBITMQ_URL, queue=QUEUE, exchange=EXCHANGE, routing_key=ROUTING_KEY,
            timeout_sec=timeout_sec,
        )

    def test_round_trip_with_real_broker(self):
        def build_success(request):
            return {
                'job_id': request['job_id'],
                'project_id': request['project_id'],
                'source_id': request['source_id'],
                'status': 'done',
                'moments': [
                    {'timestamp_sec': 42.0, 'tipo': 'gol', 'descricao': 'Gol real via RabbitMQ', 'importancia': 9},
                ],
            }

        stop_event = threading.Event()
        worker_thread = threading.Thread(target=_run_fake_worker, args=(build_success, stop_event), daemon=True)
        worker_thread.start()
        try:
            client = self._client()
            moments = client.detect_moments(
                project_id='proj-integration', source_id='source-integration',
                audio_wav_key='studio/proj-integration/tmp/source-integration.wav',
                energy_peaks=[42.0], importancia_min=5,
            )
            self.assertEqual(moments, [
                {'timestamp': 42.0, 'tipo': 'gol', 'descricao': 'Gol real via RabbitMQ', 'importancia': 9},
            ])
        finally:
            stop_event.set()
            worker_thread.join(timeout=5)

    def test_round_trip_propagates_worker_failure(self):
        def build_failure(request):
            return {
                'job_id': request['job_id'], 'project_id': request['project_id'],
                'source_id': request['source_id'], 'status': 'failed',
                'moments': [], 'error': 'CUDA out of memory (simulado)',
            }

        stop_event = threading.Event()
        worker_thread = threading.Thread(target=_run_fake_worker, args=(build_failure, stop_event), daemon=True)
        worker_thread.start()
        try:
            client = self._client()
            with self.assertRaises(HighlightWorkerFailedError):
                client.detect_moments(
                    project_id='proj-integration', source_id='source-integration',
                    audio_wav_key='k', energy_peaks=[1.0], importancia_min=5,
                )
        finally:
            stop_event.set()
            worker_thread.join(timeout=5)

    def test_timeout_when_no_worker_consumes(self):
        client = self._client(timeout_sec=3)
        try:
            with self.assertRaises(HighlightWorkerTimeoutError):
                client.detect_moments(
                    project_id='proj-integration', source_id='source-sem-worker',
                    audio_wav_key='k', energy_peaks=[1.0], importancia_min=5,
                )
        finally:
            # Sem consumidor, o request fica durável na fila — drena para não
            # poluir uma eventual execução real do worker depois deste teste.
            self._drain_orphan_request('source-sem-worker')

    def _drain_orphan_request(self, source_id: str) -> None:
        import pika

        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        try:
            channel = connection.channel()
            for _ in range(20):
                method, _properties, body = channel.basic_get(QUEUE, auto_ack=False)
                if method is None:
                    break
                payload = json.loads(body)
                if payload.get('source_id') == source_id:
                    channel.basic_ack(method.delivery_tag)
                    break
                channel.basic_nack(method.delivery_tag, requeue=True)
        finally:
            connection.close()
