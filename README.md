# バルブ角度計測システム - 実装ガイド

**プロジェクト名**: iPhone Pro LiDARを使用した金属容器バルブの地面相対角度算出システム

---

## プロジェクト構成

```
valve_angle_system/
├── server/                    # サーバー実装
│   ├── main.py               # FastAPIアプリケーション
│   ├── database.py           # DB接続・操作
│   ├── models.py             # SQLAlchemyモデル
│   ├── requirements.txt      # Python依存関係
│   └── Dockerfile            # Dockerイメージ定義
├── client/
│   ├── iphone/               # iPhone側HTML/JS
│   └── pc/                   # PC側HTML/JS
├── database/
│   └── migrations/           # データベースマイグレーション
├── certs/                     # SSL証明書
└── docker-compose.yml         # Docker Compose設定
```

---

## セットアップ手順

### 1. 環境準備

```bash
cd valve_angle_system
```

### 2. SSL証明書生成（HTTPS用）

```bash
# mkcertを使用（推奨）
brew install mkcert  # macOS
mkcert -install

# 証明書生成
cd certs
mkcert localhost YOUR_PC_IP 192.168.0.0/16
mv localhost+2.pem cert.pem
mv localhost+2-key.pem key.pem
cd ..
```

### 3. 環境変数設定

```bash
cp server/.env.example server/.env
# .envファイルを編集して必要な値を設定
```

### 4. Docker環境で起動

```bash
# PostgreSQLとFastAPIサーバーを起動
docker-compose up -d

# ログ確認
docker-compose logs -f

# 停止
docker-compose down
```

### 5. アクセス

- **PC側ダッシュボード**: `https://localhost:3000` または `https://YOUR_PC_IP:3000`
- **iPhone側クライアント**: `https://YOUR_PC_IP:3000/iphone`
- **WebSocket**: `wss://YOUR_PC_IP:3000/ws/lidar`

---

## 開発状況

### ✅ Sprint 1完了項目

- ✅ プロジェクト構造作成
- ✅ Docker Compose設定
- ✅ PostgreSQLスキーマ作成
- ✅ FastAPIサーバー基本実装
- ✅ WebSocket基本実装
- ✅ データベース接続プール実装

### ⏳ 進行中

- ⏳ HTTPS/WSS対応（SSL証明書生成必要）

### 📋 次回実装予定

- Sprint 2: iPhone側UI実装（ROI選択、基準合わせ）
- Sprint 3: 幾何フィット実装（RANSAC）
- Sprint 4: PC側UI実装（3D表示、角度表示）
- Sprint 5: データ保存機能（DB連携）

---

## トラブルシューティング

### 証明書エラー

- ブラウザで「接続がプライベートではありません」警告が出る場合
- → 詳細設定 → 続行（localhostへの接続）を選択

### データベース接続エラー

```bash
# PostgreSQLコンテナのログ確認
docker-compose logs postgres

# PostgreSQLコンテナに接続
docker exec -it valve_angle_postgres psql -U valve_user -d valve_angle_db
```

---

## 参考ドキュメント

- `docs/requirements_valve_angle_measurement.md` - 要件定義書
- `docs/architecture_valve_angle_measurement.md` - アーキテクチャ設計書
- `docs/api_specification_valve_angle_measurement.md` - API仕様書

