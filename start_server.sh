#!/bin/bash
# サーバー起動スクリプト

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER_DIR="$SCRIPT_DIR/server"
CERTS_DIR="$SCRIPT_DIR/certs"

cd "$SERVER_DIR"

# 環境変数設定
export SSL_CERT_FILE="$CERTS_DIR/cert.pem"
export SSL_KEY_FILE="$CERTS_DIR/key.pem"
export DATABASE_URL="${DATABASE_URL:-postgresql://valve_user:valve_password@localhost:5432/valve_angle_db}"

# 証明書確認
if [ ! -f "$SSL_CERT_FILE" ] || [ ! -f "$SSL_KEY_FILE" ]; then
    echo "❌ SSL証明書が見つかりません"
    echo "証明書を生成してください:"
    echo "  cd $SCRIPT_DIR && ./generate_certs.sh"
    exit 1
fi

echo "🚀 サーバーを起動します..."
echo "  HTTPS: https://localhost:3000"
echo "  証明書: $SSL_CERT_FILE"
echo ""

# サーバー起動
python3 main.py

