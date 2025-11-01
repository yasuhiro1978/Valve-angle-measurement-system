#!/bin/bash
# PostgreSQLデータベース起動スクリプト

echo "=========================================="
echo "PostgreSQLコンテナ起動スクリプト"
echo "=========================================="

# Docker Desktopが起動しているか確認
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker Desktopが起動していません"
    echo ""
    echo "以下の手順を実行してください:"
    echo "1. Docker Desktopアプリを起動"
    echo "2. メニューバーのDockerアイコンが安定するまで待機"
    echo "3. このスクリプトを再実行"
    echo ""
    exit 1
fi

echo "✅ Docker Desktopが起動しています"
echo ""

# PostgreSQLコンテナを起動
cd "$(dirname "$0")"
echo "PostgreSQLコンテナを起動中..."
docker-compose up -d postgres

# 起動確認
sleep 3
if docker-compose ps postgres | grep -q "Up"; then
    echo ""
    echo "✅ PostgreSQLコンテナが起動しました"
    echo ""
    echo "接続情報:"
    echo "  ホスト: localhost"
    echo "  ポート: 5432"
    echo "  データベース: valve_angle_db"
    echo "  ユーザー: valve_user"
    echo "  パスワード: valve_password"
    echo ""
    echo "接続確認:"
    docker-compose ps postgres
else
    echo ""
    echo "❌ PostgreSQLコンテナの起動に失敗しました"
    echo ""
    echo "ログを確認:"
    docker-compose logs postgres
    exit 1
fi

