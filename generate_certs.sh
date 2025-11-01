#!/bin/bash
# SSL証明書生成スクリプト

set -e

echo "🔐 SSL証明書を生成します..."

# certsディレクトリに移動
cd "$(dirname "$0")/certs"

# mkcertがインストールされているか確認
if ! command -v mkcert &> /dev/null; then
    echo "❌ mkcertがインストールされていません"
    echo "インストール方法:"
    echo "  macOS: brew install mkcert"
    echo "  Linux: https://github.com/FiloSottile/mkcert#installation を参照"
    exit 1
fi

# ローカルCAをインストール（初回のみ）
if [ ! -f "$(mkcert -CAROOT)/rootCA.pem" ]; then
    echo "📦 ローカルCAをインストールします..."
    mkcert -install
fi

# 証明書を生成
echo "📝 証明書を生成します..."
# 社内LAN用に複数のIPアドレスを指定（必要に応じて追加・変更してください）
# 例: mkcert localhost 127.0.0.1 ::1 YOUR_PC_IP
mkcert localhost 127.0.0.1 ::1

# 生成された証明書ファイルを検索してリネーム
CERT_FILE=$(ls localhost+*.pem 2>/dev/null | grep -v key | head -1)
KEY_FILE=$(ls localhost+*-key.pem 2>/dev/null | head -1)

if [ -n "$CERT_FILE" ] && [ -n "$KEY_FILE" ]; then
    mv "$CERT_FILE" cert.pem
    mv "$KEY_FILE" key.pem
    echo "✅ 証明書生成完了:"
    echo "  cert.pem: $(pwd)/cert.pem"
    echo "  key.pem: $(pwd)/key.pem"
else
    echo "❌ 証明書ファイルが見つかりません"
    exit 1
fi

cd ..

