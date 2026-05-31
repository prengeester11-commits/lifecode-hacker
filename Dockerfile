FROM python:3.11-slim

WORKDIR /app

# WeasyPrint와 한글 폰트 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-noto-cjk \
    fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

# 의존성 먼저 설치 (캐시 최적화)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 복사
COPY . .

# Cloud Run은 PORT 환경변수를 자동으로 설정함
ENV PORT=8080
ENV FLASK_DEBUG=false

EXPOSE 8080

CMD exec gunicorn --bind :$PORT --workers 2 --timeout 180 app:app
