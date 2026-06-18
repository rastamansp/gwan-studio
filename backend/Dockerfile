FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt

COPY . .

ENV DJANGO_SETTINGS_MODULE=config.settings.production

RUN python manage.py collectstatic --noinput

EXPOSE 3018

CMD ["python", "-m", "daphne", "-b", "0.0.0.0", "-p", "3018", "config.asgi:application"]
