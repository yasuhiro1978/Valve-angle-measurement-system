FROM python:3.10-slim

WORKDIR /app

# システムパッケージインストール
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係インストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードコピー
COPY . .

# ポート公開
EXPOSE 3000

# サーバー起動
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000", "--reload"]

