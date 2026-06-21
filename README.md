# Gwan Studio

Plataforma web de produção de vídeo para YouTube. O usuário faz upload de clipes brutos, passa por um pipeline guiado — merge, export, thumbnails com IA, SEO com IA — e publica diretamente no canal.

**Stack:** Django 5.2 LTS · HTMX 2 · Alpine.js · Tailwind · Django Channels (WebSocket) · FFmpeg · Claude API · MinIO

---

## Funcionalidades

| # | Feature | Descrição |
|---|---------|-----------|
| F01 | Projetos | Criar e listar projetos; fase rastreada (`new → published`) |
| F02 | Upload de fontes | Multi-upload de clipes `.mp4/.mov/.avi/.mkv`; drag-drop + reordenação |
| F03 | Merge | Concatenação via FFmpeg stream-copy (sem re-encode) |
| F04 | Export | Re-encode com codec, resolução e bitrate configuráveis |
| F05 | Thumbnails IA | Claude Vision analisa frames e planeja 3 variantes; Pillow renderiza |
| F06 | SEO IA | Claude gera título, descrição e tags em português para YouTube |
| F07 | Publicar | Upload via YouTube Data API v3 com OAuth 2.0 |
| F08 | Storage | Porta de storage transparente: filesystem local ou MinIO/S3 |
| F09 | WebSocket | Streaming de logs em tempo real via Django Channels; REST API de jobs |

---

## Arquitetura

```
presentation/          HTMX views + Alpine.js (sem SPA framework)
    └── WebSocket       ws/projects/<id>/  →  streaming de eventos de job
application/           Use cases (orquestração pura, sem imports Django)
domain/                Entities + Ports (ABCs)
infrastructure/
    ├── ffmpeg/         merge, export, extração de frames
    ├── ai/             thumbnail_planner (Claude Vision), seo_generator
    ├── image/          thumbnail_renderer (Pillow)
    ├── storage/        LocalStorageAdapter | MinioStorageAdapter
    ├── ws/             ProjectConsumer (Channels) + InMemoryEventStore
    ├── youtube/        uploader (Data API v3)
    └── orm/            DjangoProjectRepository
studio/                Django app: modelos ORM (ProjectModel, JobModel …)
```

**Padrão de jobs:** cada etapa pesada roda em `threading.Thread(daemon=True)`. O worker emite eventos no `InMemoryEventStore`; o consumer WebSocket poll a 300 ms e faz streaming para o browser. O browser usa HTMX como fallback de 2 s para detectar conclusão.

---

## Pré-requisitos

| Dependência | Versão mínima | Obrigatória |
|-------------|---------------|-------------|
| Python | 3.11 | ✅ |
| FFmpeg + ffprobe | qualquer | thumbnails e merge reais |
| Anthropic API key | — | thumbnails e SEO reais |
| Google OAuth 2.0 | — | publicação real no YouTube |
| MinIO / S3 | — | storage em produção |

---

## Início rápido (Fase 0 — tudo simulado)

```bash
# 1. Clonar e criar venv
git clone https://github.com/rastamansp/gwan-studio.git
cd gwan-studio/backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

# 2. Instalar dependências
pip install -r requirements/phase0.txt

# 3. Migrar banco (SQLite local)
python manage.py migrate

# 4. Subir servidor
python manage.py runserver 3018
```

Acesse [http://localhost:3018](http://localhost:3018).

Nenhum serviço externo é necessário — FFmpeg, Claude e YouTube são simulados.

---

## Modo real (Claude + FFmpeg)

Para ativar thumbnails e SEO com Claude de verdade:

**1. Instalar FFmpeg** (Windows via winget):
```powershell
winget install Gyan.FFmpeg
```

**2. Criar `.env.local`** (nunca commitar):
```env
ANTHROPIC_API_KEY=sk-ant-...

THUMBNAIL_SIMULATE=false
SEO_SIMULATE=false

# manter simulado (não precisa de OAuth)
MERGE_SIMULATE=true
EXPORT_SIMULATE=true
PUBLISH_SIMULATE=true
```

**3. Subir com o script de ambiente:**
```powershell
cd backend
.\start-real.ps1
```

O script carrega o `.env.local`, adiciona FFmpeg ao PATH da sessão e verifica a chave antes de subir.

---

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `MERGE_SIMULATE` | `true` | Simula merge (copia 1ª fonte) |
| `EXPORT_SIMULATE` | `true` | Simula export (copia merged) |
| `THUMBNAIL_SIMULATE` | `true` | Simula thumbnails (sem Claude Vision) |
| `SEO_SIMULATE` | `true` | Simula SEO (sem Claude) |
| `PUBLISH_SIMULATE` | `true` | Simula upload YouTube |
| `ANTHROPIC_API_KEY` | `""` | Chave Anthropic |
| `GOOGLE_CLIENT_ID` | `""` | OAuth 2.0 — YouTube |
| `GOOGLE_CLIENT_SECRET` | `""` | OAuth 2.0 — YouTube |
| `STORAGE_BACKEND` | `local` | `local` ou `minio` |
| `MINIO_ENDPOINT` | `""` | ex.: `https://s3.gwan.cloud` |
| `MINIO_ACCESS_KEY` | `""` | MinIO access key |
| `MINIO_SECRET_KEY` | `""` | MinIO secret key |
| `MINIO_BUCKET` | `studio` | Bucket de artefatos |

---

## Endpoints

### Páginas (HTMX)

| Método | URL | Descrição |
|--------|-----|-----------|
| GET | `/` | Lista de projetos |
| GET/POST | `/projects/new/` | Criar projeto |
| GET | `/projects/<id>/` | Detalhe do projeto |
| GET | `/projects/<id>/sources/` | Passo 1 — fontes |
| GET | `/projects/<id>/merge/` | Passo 2 — merge |
| GET | `/projects/<id>/export/` | Passo 3 — export |
| GET | `/projects/<id>/thumbnail/` | Passo 4 — thumbnails |
| GET | `/projects/<id>/seo/` | Passo 5 — SEO |
| GET | `/projects/<id>/publish/` | Passo 6 — publicar |

### REST API

| Método | URL | Descrição |
|--------|-----|-----------|
| GET | `/api/health/` | Health check |
| GET | `/api/projects/<id>/jobs/` | Lista jobs (últimos 20) |
| GET | `/api/projects/<id>/jobs/<jobId>/` | Job com logs completos |

### WebSocket

```
ws://localhost:3018/ws/projects/<project_id>/
```

Ao conectar, recebe snapshot dos últimos 100 eventos. Eventos enviados:

```jsonc
// Em andamento — linha de log incremental
{ "event": "job.update", "data": { "jobId": "...", "type": "merge", "status": "running", "log_line": "..." } }

// Concluído
{ "event": "job.update", "data": { "jobId": "...", "type": "merge", "status": "done", "output_params": { ... } } }

// Snapshot inicial
{ "event": "project.snapshot", "data": { "projectId": "...", "recentEvents": [ ... ] } }
```

---

## Estrutura de diretórios

```
backend/
├── config/
│   ├── settings/
│   │   ├── phase0.py       ← dev (SQLite, simulate=true, InMemoryChannelLayer)
│   │   ├── base.py         ← base compartilhada
│   │   └── production.py   ← prod (PostgreSQL, Redis, MinIO)
│   ├── asgi.py             ← ProtocolTypeRouter (HTTP + WebSocket)
│   └── urls.py
├── domain/
│   ├── entities.py         ← dataclasses puras
│   └── ports.py            ← ABCs (IObjectStoragePort, etc.)
├── infrastructure/
│   ├── ffmpeg/             ← merge.py, export.py, frames.py
│   ├── ai/                 ← seo_generator.py, thumbnail_planner.py
│   ├── image/              ← thumbnail_renderer.py (Pillow)
│   ├── storage/            ← local.py, minio_adapter.py, __init__.py (factory)
│   ├── ws/                 ← consumer.py (Channels), event_store.py
│   ├── youtube/            ← uploader.py
│   └── orm/                ← repositories.py
├── application/
│   └── projects/           ← use_cases.py (CreateProject, etc.)
├── presentation/
│   └── views/projects.py   ← todas as views (HTMX + REST)
├── studio/
│   └── models.py           ← ProjectModel, SourceModel, JobModel, ThumbnailModel, SeoMetadataModel, PublishRecord
├── templates/              ← HTML por feature (merge/, export/, thumbnail/, seo/, publish/)
├── static/                 ← CSS, JS
├── requirements/
│   ├── phase0.txt          ← mínimo para dev sem serviços externos
│   ├── base.txt            ← dependências compartilhadas
│   └── production.txt      ← prod
├── manage.py
└── start-real.ps1          ← script Windows para subir com Claude + FFmpeg reais
```

---

## Fases do projeto

```
new  →  sources_uploaded  →  merge_done  →  export_done
     →  thumbnails_done   →  seo_approved  →  published
```

---

## Deploy (produção)

Deploy exclusivamente via **Portainer** — `studio.gwan.cloud` (frontend) e `api-studio.gwan.cloud` (Daphne ASGI). Ver [F10-deploy.md](docs/spec/20-features/F10-deploy.md) para o `docker-compose.yml` de produção.

Serviços externos requeridos em produção:
- **PostgreSQL** — banco principal
- **Redis** — Celery broker + Django Channels layer
- **MinIO** — armazenamento de artefatos de vídeo
- **Anthropic API** — Claude Vision + geração de texto
- **Google OAuth 2.0** — YouTube Data API v3

---

## Licença

Proprietário — [GWAN Cloud](https://gwan.cloud)
