FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Aqtobe

WORKDIR /nomad_cards_notifier

COPY requirements.txt ./

RUN apt-get update && \
    apt-get install -y --no-install-recommends tzdata && \
    python -m pip install --no-cache-dir -r requirements.txt && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    dpkg-reconfigure --frontend noninteractive tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY . /nomad_cards_notifier

RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /nomad_cards_notifier
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os; os.kill(1, 0)"

CMD ["python", "run_bot.py"]