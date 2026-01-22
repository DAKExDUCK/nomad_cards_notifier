FROM ubuntu:22.04

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Aqtobe

COPY requirements.txt .

RUN apt-get update && \
    apt-get install -yqq --no-install-recommends python3.10 python3-pip tzdata && \
    python3.10 -m pip install -r requirements.txt && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    dpkg-reconfigure --frontend noninteractive tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*


WORKDIR /nomad_cards_notifier
COPY . /nomad_cards_notifier

RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /nomad_cards_notifier
USER appuser

CMD ["python3.10", "main.py"]