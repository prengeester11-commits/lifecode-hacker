FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성: WeasyPrint(GTK) + 한글 폰트 + 빌드 도구(C확장 패키지용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    fonts-noto-cjk \
    fonts-nanum \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# pip/setuptools 최신화 (metadata-generation-failed 방지)
RUN pip install --upgrade pip setuptools wheel

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
