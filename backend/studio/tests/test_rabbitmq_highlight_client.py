"""
F17 — ponte RabbitMQ↔highlight-worker: valida a lógica de correlação/timeout
do RabbitMqHighlightWorkerClient sem precisar de um broker real (mocka pika).
"""
import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from infrastructure.messaging.rabbitmq_highlight_client import (
    HighlightWorkerFailedError, HighlightWorkerTimeoutError, RabbitMqHighlightWorkerClient,
)


def _fake_method(delivery_tag=1):
    m = MagicMock()
    m.delivery_tag = delivery_tag
    return m


class RabbitMqHighlightWorkerClientTests(SimpleTestCase):
    def _client(self, timeout_sec=30):
        return RabbitMqHighlightWorkerClient(
            url='amqp://guest:guest@localhost:5673/',
            queue='highlight.detect',
            exchange='highlight',
            routing_key='highlight.results',
            timeout_sec=timeout_sec,
        )

    @patch('pika.BlockingConnection')
    def test_returns_moments_on_matching_job_id(self, mock_conn_cls):
        channel = MagicMock()
        mock_conn_cls.return_value.channel.return_value = channel
        channel.queue_declare.return_value.method.queue = 'amq.gen-fake'

        captured = {}

        def fake_publish(exchange, routing_key, body, properties):
            captured['request'] = json.loads(body)

        channel.basic_publish.side_effect = fake_publish

        def fake_consume(queue, inactivity_timeout):
            result = {
                'job_id': captured['request']['job_id'],
                'project_id': 'proj-1',
                'source_id': 'src-1',
                'status': 'done',
                'moments': [
                    {'timestamp_sec': 12.5, 'tipo': 'gol', 'descricao': 'Gol', 'importancia': 9},
                ],
            }
            yield _fake_method(), None, json.dumps(result).encode('utf-8')

        channel.consume.side_effect = fake_consume

        client = self._client()
        moments = client.detect_moments(
            project_id='proj-1', source_id='src-1', audio_wav_key='studio/proj-1/tmp/src-1.wav',
            energy_peaks=[12.5], importancia_min=5,
        )

        self.assertEqual(moments, [{'timestamp': 12.5, 'tipo': 'gol', 'descricao': 'Gol', 'importancia': 9}])
        self.assertEqual(captured['request']['audio_wav_key'], 'studio/proj-1/tmp/src-1.wav')
        self.assertEqual(captured['request']['energy_peaks'], [12.5])
        channel.basic_ack.assert_called_once()

    @patch('pika.BlockingConnection')
    def test_discards_results_from_other_jobs_in_flight(self, mock_conn_cls):
        channel = MagicMock()
        mock_conn_cls.return_value.channel.return_value = channel
        channel.queue_declare.return_value.method.queue = 'amq.gen-fake'

        captured = {}
        channel.basic_publish.side_effect = (
            lambda exchange, routing_key, body, properties: captured.update(request=json.loads(body))
        )

        def fake_consume(queue, inactivity_timeout):
            other_job = {'job_id': 'other-job', 'status': 'done', 'moments': []}
            yield _fake_method(1), None, json.dumps(other_job).encode('utf-8')

            def _mine():
                return {
                    'job_id': captured['request']['job_id'], 'status': 'done',
                    'moments': [{'timestamp_sec': 1.0, 'tipo': 'chance', 'descricao': 'x', 'importancia': 5}],
                }
            yield _fake_method(2), None, json.dumps(_mine()).encode('utf-8')

        channel.consume.side_effect = fake_consume

        client = self._client()
        moments = client.detect_moments(
            project_id='p', source_id='s', audio_wav_key='k', energy_peaks=[1.0], importancia_min=5,
        )
        self.assertEqual(len(moments), 1)
        self.assertEqual(channel.basic_ack.call_count, 2)  # ambas as mensagens são ack'ed

    @patch('pika.BlockingConnection')
    def test_raises_failed_error_when_worker_reports_failure(self, mock_conn_cls):
        channel = MagicMock()
        mock_conn_cls.return_value.channel.return_value = channel
        channel.queue_declare.return_value.method.queue = 'amq.gen-fake'
        captured = {}
        channel.basic_publish.side_effect = (
            lambda exchange, routing_key, body, properties: captured.update(request=json.loads(body))
        )

        def fake_consume(queue, inactivity_timeout):
            yield _fake_method(), None, json.dumps({
                'job_id': captured['request']['job_id'], 'status': 'failed', 'error': 'GPU sem memória',
            }).encode('utf-8')

        channel.consume.side_effect = fake_consume

        client = self._client()
        with self.assertRaises(HighlightWorkerFailedError):
            client.detect_moments(
                project_id='p', source_id='s', audio_wav_key='k', energy_peaks=[1.0], importancia_min=5,
            )

    @patch('time.monotonic')
    @patch('pika.BlockingConnection')
    def test_raises_timeout_error_when_no_response(self, mock_conn_cls, mock_monotonic):
        channel = MagicMock()
        mock_conn_cls.return_value.channel.return_value = channel
        channel.queue_declare.return_value.method.queue = 'amq.gen-fake'

        # primeira chamada define o deadline; chamadas seguintes já estão "no futuro".
        mock_monotonic.side_effect = [0, 100, 100]

        def fake_consume(queue, inactivity_timeout):
            yield None, None, None  # inactivity_timeout estourado, sem mensagem

        channel.consume.side_effect = fake_consume

        client = self._client(timeout_sec=10)
        with self.assertRaises(HighlightWorkerTimeoutError):
            client.detect_moments(
                project_id='p', source_id='s', audio_wav_key='k', energy_peaks=[1.0], importancia_min=5,
            )
