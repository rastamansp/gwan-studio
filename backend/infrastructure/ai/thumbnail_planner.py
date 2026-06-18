"""
F05 — Planejamento de thumbnails via Claude Vision.
"""
import json


SYSTEM_PROMPT = """Você é um especialista em thumbnails de YouTube com alto CTR.
Analise os frames fornecidos e retorne exatamente 3 planos de thumbnail como JSON válido."""

USER_TEMPLATE = """Frames do vídeo "{project_name}".{seo_line}

Retorne SOMENTE o seguinte JSON (sem markdown, sem explicação):
{{
  "plans": [
    {{
      "variant": "A",
      "description": "<descrição do layout>",
      "text_overlay": "<texto para sobrepor, máx 40 chars>",
      "color_palette": ["#hex1", "#hex2"],
      "focus_area": "face|action|landscape|product",
      "font_style": "bold|clean|dramatic"
    }},
    {{ "variant": "B", ... }},
    {{ "variant": "C", ... }}
  ]
}}

Cada variante deve ter estilo distinto. text_overlay em português."""


def plan_thumbnails(
    frames_b64: list[str],
    project_name: str,
    seo_title: str = '',
    api_key: str = '',
) -> list[dict]:
    """
    Chama Claude Vision com até 6 frames e retorna 3 planos de thumbnail.
    Levanta Exception se a API falhar ou o JSON vier malformado.
    """
    import anthropic

    seo_line = f'\nTítulo SEO: {seo_title}' if seo_title else ''
    user_text = USER_TEMPLATE.format(project_name=project_name, seo_line=seo_line)

    content: list = []
    for b64 in frames_b64[:6]:
        content.append({
            'type': 'image',
            'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b64},
        })
    content.append({'type': 'text', 'text': user_text})

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model='claude-opus-4-8',
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': content}],
    )
    raw = msg.content[0].text.strip()
    data = json.loads(raw)
    return data['plans']
