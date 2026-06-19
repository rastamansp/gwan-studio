"""
F06 — Geração de metadados SEO para YouTube via Claude.
"""
import json


SYSTEM_PROMPT = (
    'Você é especialista em SEO para YouTube em português brasileiro. '
    'Retorne SOMENTE JSON válido, sem markdown, sem explicações.'
)

USER_TEMPLATE = """\
Vídeo: "{project_name}"
Canal: "{channel_name}"{context_line}

Gere metadados otimizados para YouTube:
{{
  "title": "<título atraente, máx 100 chars, gere curiosidade>",
  "description": "<descrição completa, máx 5000 chars. Parágrafo 1: resumo do vídeo (aparece na busca). Parágrafo 2: detalhes e contexto. Parágrafo 3: CTAs — inscrição, outros vídeos, redes sociais.>",
  "tags": ["tag1", "tag2", "..."]
}}

Regras:
- Título em português BR, com palavras-chave principais, máx 100 chars.
- Tags: 10–20 tags, da mais específica à mais geral. Sem repetir palavras do título.
- Linguagem: português brasileiro, tom do canal "{channel_name}".\
"""


def generate_seo(
    project_name: str,
    channel_name: str,
    context: str = '',
    api_key: str = '',
) -> dict:
    """Chama Claude e retorna {'title': ..., 'description': ..., 'tags': [...]}."""
    import anthropic

    context_line = f'\nContexto: {context}' if context.strip() else ''
    user_text = USER_TEMPLATE.format(
        project_name=project_name,
        channel_name=channel_name or 'YouTube',
        context_line=context_line,
    )

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model='claude-opus-4-8',
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': user_text}],
    )
    raw = msg.content[0].text.strip()
    return json.loads(raw)
