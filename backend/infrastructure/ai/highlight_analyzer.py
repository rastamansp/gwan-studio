"""
F17 — análise semântica dos picos de áudio detectados na partida.

Implementa `IHighlightAnalysisPort` (domain/ports.py). Esta versão chama o
Claude diretamente sobre os timestamps dos picos de energia; é um adapter
provisório enquanto o worker GPU externo de transcrição (Whisper) não está
implantado — ver docs/spec/20-features/F17-futebol-highlights.md ("Por que
worker externo"). Trocar por um adapter que funde transcrição real é uma
mudança isolada nesta classe, sem tocar nos use cases/views.
"""
import json

from domain.ports import IHighlightAnalysisPort

SYSTEM_PROMPT = (
    'Você é um analista de futebol especializado em identificar os melhores '
    'momentos de uma partida a partir de picos de energia de áudio (torcida, '
    'narrador em alta). Retorne SOMENTE JSON válido, sem markdown, sem explicações.'
)

USER_TEMPLATE = """\
Partida: "{project_name}"
Duração total: {duration_sec:.0f} segundos.

Picos de energia de áudio detectados (segundos, ordem cronológica):
{peaks_list}

Para cada pico, avalie a probabilidade de ser um lance relevante (gol, defesa, \
pênalti, falta perigosa, expulsão ou chance clara) considerando o padrão típico \
de reação de torcida/narração em partidas de futebol, e retorne uma lista JSON:

[
  {{"timestamp": <segundos, float>, "tipo": "gol|defesa|penalti|falta|expulsao|chance|outro", \
"descricao": "<frase curta descrevendo o lance provável>", "importancia": <0-10>}}
]

Regras:
- Um item por pico recebido, na mesma ordem.
- "importancia" reflete a confiança de que é um lance relevante (10 = certeza de gol/lance decisivo).
- Picos isolados sem padrão de gol (só ruído/aplauso) devem receber importancia baixa (<= 3).\
"""


class ClaudeHighlightAnalyzer(IHighlightAnalysisPort):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def detect_moments(
        self,
        energy_peaks: list[float],
        duration_sec: float,
        project_name: str,
        importancia_min: int,
    ) -> list[dict]:
        if not energy_peaks:
            return []

        import anthropic

        peaks_list = '\n'.join(f'- {p:.1f}s' for p in energy_peaks)
        user_text = USER_TEMPLATE.format(
            project_name=project_name,
            duration_sec=duration_sec,
            peaks_list=peaks_list,
        )

        client = anthropic.Anthropic(api_key=self.api_key)
        msg = client.messages.create(
            model='claude-opus-4-8',
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': user_text}],
        )
        raw = msg.content[0].text.strip()
        try:
            moments = json.loads(raw)
        except json.JSONDecodeError:
            # RN-F17-06 — resposta inválida não derruba o job, só perde os momentos.
            return []

        return [m for m in moments if m.get('importancia', 0) >= importancia_min]


TIPOS = ['gol', 'defesa', 'penalti', 'falta', 'chance']


def simulate_detect_moments(energy_peaks: list[float], importancia_min: int) -> list[dict]:
    """[SIMULADO] Classifica os picos ciclicamente entre tipos, sem chamar Claude."""
    moments = []
    for i, peak in enumerate(energy_peaks):
        tipo = TIPOS[i % len(TIPOS)]
        importancia = 8 if tipo == 'gol' else 6
        if importancia < importancia_min:
            continue
        moments.append({
            'timestamp': peak,
            'tipo': tipo,
            'descricao': f'[SIMULADO] Lance de {tipo} detectado por pico de áudio',
            'importancia': importancia,
        })
    return moments
