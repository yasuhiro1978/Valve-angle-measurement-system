-- ============================================================
-- バルブ角度計測システム - 初期スキーマ作成
-- バージョン: 1.0.0
-- 作成日: 2025-01-XX
-- ============================================================

-- 拡張機能の有効化
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 1. アセットテーブル（図面等）
-- ============================================================
CREATE TABLE assets (
    id SERIAL PRIMARY KEY,
    type VARCHAR(20) NOT NULL CHECK (type IN ('pdf', 'image', 'document')),
    file_path TEXT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT,
    mime_type VARCHAR(100),
    metadata_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    CONSTRAINT assets_file_path_unique UNIQUE (file_path)
);

COMMENT ON TABLE assets IS 'アセット管理テーブル（図面、画像等）';
COMMENT ON COLUMN assets.id IS 'アセットID（自動採番）';
COMMENT ON COLUMN assets.type IS 'アセット種別（pdf/image/document）';
COMMENT ON COLUMN assets.file_path IS 'ファイルパス（絶対パス）';
COMMENT ON COLUMN assets.file_name IS 'ファイル名';
COMMENT ON COLUMN assets.metadata_json IS 'メタデータ（JSON形式）';

-- ============================================================
-- 2. 容器マスタテーブル
-- ============================================================
CREATE TABLE containers (
    id SERIAL PRIMARY KEY,
    container_number VARCHAR(50) NOT NULL,
    processed_date DATE NOT NULL,
    drawing_pdf_id INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    description TEXT,
    location VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'archived')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    CONSTRAINT containers_unique_key UNIQUE (container_number, processed_date)
);

COMMENT ON TABLE containers IS '容器マスタテーブル';
COMMENT ON COLUMN containers.id IS '容器ID（自動採番）';
COMMENT ON COLUMN containers.container_number IS '容器番号';
COMMENT ON COLUMN containers.processed_date IS '処理日';
COMMENT ON COLUMN containers.drawing_pdf_id IS '関連図面ID（外部キー）';
COMMENT ON COLUMN containers.status IS 'ステータス（active/inactive/archived）';

-- ============================================================
-- 3. 計測セッションテーブル（複数バルブ計測のグループ化）
-- ============================================================
CREATE TABLE measurement_sessions (
    id SERIAL PRIMARY KEY,
    container_id INTEGER NOT NULL REFERENCES containers(id) ON DELETE CASCADE,
    session_name VARCHAR(255),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed', 'cancelled')),
    operator VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE measurement_sessions IS '計測セッションテーブル（複数バルブ計測のグループ化）';
COMMENT ON COLUMN measurement_sessions.status IS 'セッションステータス（in_progress/completed/cancelled）';

-- ============================================================
-- 4. 計測結果テーブル
-- ============================================================
CREATE TABLE measurements (
    id SERIAL PRIMARY KEY,
    container_id INTEGER NOT NULL REFERENCES containers(id) ON DELETE CASCADE,
    session_id INTEGER REFERENCES measurement_sessions(id) ON DELETE SET NULL,
    target_type CHAR(1) NOT NULL CHECK (target_type IN ('A', 'B', 'C', 'D')),
    pitch_deg DECIMAL(5,1) NOT NULL CHECK (pitch_deg >= -180.0 AND pitch_deg <= 180.0),
    roll_deg DECIMAL(5,1) NOT NULL CHECK (roll_deg >= -180.0 AND roll_deg <= 180.0),
    basis VARCHAR(10) NOT NULL CHECK (basis IN ('imu', 'plane')),
    roi_json JSONB DEFAULT '{}'::jsonb,
    roi_center_x DECIMAL(8,3),
    roi_center_y DECIMAL(8,3),
    roi_center_z DECIMAL(8,3),
    roi_width DECIMAL(8,3),
    roi_height DECIMAL(8,3),
    roi_depth DECIMAL(8,3),
    distance_m DECIMAL(5,2) CHECK (distance_m > 0 AND distance_m <= 10.0),
    point_count INTEGER,
    inlier_ratio DECIMAL(4,3) CHECK (inlier_ratio >= 0.0 AND inlier_ratio <= 1.0),
    residual_rms DECIMAL(8,4),
    quality_score DECIMAL(4,3) CHECK (quality_score >= 0.0 AND quality_score <= 1.0),
    imu_data_json JSONB DEFAULT '{}'::jsonb,
    measurement_note TEXT,
    operator VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE measurements IS '計測結果テーブル';
COMMENT ON COLUMN measurements.id IS '計測ID（自動採番）';
COMMENT ON COLUMN measurements.container_id IS '容器ID（外部キー）';
COMMENT ON COLUMN measurements.target_type IS '対象タイプ（A:ステム軸, B:ハンドル面, C:フランジ面, D:配管軸）';
COMMENT ON COLUMN measurements.pitch_deg IS 'ピッチ角度（度、小数1桁）';
COMMENT ON COLUMN measurements.roll_deg IS 'ロール角度（度、小数1桁）';
COMMENT ON COLUMN measurements.basis IS '基準方式（imu:IMU基準, plane:地面推定）';
COMMENT ON COLUMN measurements.roi_json IS 'ROI情報（JSON形式）';
COMMENT ON COLUMN measurements.quality_score IS 'フィット品質スコア（0.0-1.0）';

-- ============================================================
-- 5. システム設定テーブル（将来拡張用）
-- ============================================================
CREATE TABLE system_settings (
    id SERIAL PRIMARY KEY,
    setting_key VARCHAR(100) NOT NULL UNIQUE,
    setting_value TEXT,
    setting_type VARCHAR(20) DEFAULT 'string' CHECK (setting_type IN ('string', 'number', 'boolean', 'json')),
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100)
);

COMMENT ON TABLE system_settings IS 'システム設定テーブル';
COMMENT ON COLUMN system_settings.setting_key IS '設定キー（ユニーク）';
COMMENT ON COLUMN system_settings.setting_value IS '設定値（テキスト形式）';
COMMENT ON COLUMN system_settings.setting_type IS '設定値の型（string/number/boolean/json）';

-- ============================================================
-- 6. 更新時刻自動更新トリガー関数
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_containers_updated_at
    BEFORE UPDATE ON containers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_measurements_updated_at
    BEFORE UPDATE ON measurements
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_measurement_sessions_updated_at
    BEFORE UPDATE ON measurement_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_assets_updated_at
    BEFORE UPDATE ON assets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_system_settings_updated_at
    BEFORE UPDATE ON system_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

