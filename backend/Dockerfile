FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt

COPY . .

ENV DJANGO_SETTINGS_MODULE=config.settings.production

# collectstatic precisa importar os settings (que exigem SECRET_KEY/DATABASE_URL).
# Valores dummy SO para o build (inline, nao persistem na imagem); em runtime o
# compose/Portainer injeta os reais. collectstatic nao acessa o banco.
RUN SECRET_KEY=build-only-not-a-secret \
    DATABASE_URL=sqlite:////tmp/build.sqlite3 \
    python manage.py collectstatic --noinput

EXPOSE 3018

CMD ["python", "-m", "daphne", "-b", "0.0.0.0", "-p", "3018", "config.asgi:application"]
