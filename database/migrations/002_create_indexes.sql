-- ============================================================
-- バルブ角度計測システム - インデックス作成
-- バージョン: 1.0.0
-- 作成日: 2025-01-XX
-- ============================================================

-- ============================================================
-- 1. containers テーブルのインデックス
-- ============================================================
CREATE INDEX idx_containers_processed_date ON containers(processed_date);
CREATE INDEX idx_containers_status ON containers(status);
CREATE INDEX idx_containers_drawing_pdf_id ON containers(drawing_pdf_id) WHERE drawing_pdf_id IS NOT NULL;

-- ============================================================
-- 2. measurements テーブルのインデックス
-- ============================================================
CREATE INDEX idx_measurements_container_id ON measurements(container_id);
CREATE INDEX idx_measurements_session_id ON measurements(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX idx_measurements_created_at ON measurements(created_at DESC);
CREATE INDEX idx_measurements_target_type ON measurements(target_type);
CREATE INDEX idx_measurements_container_target ON measurements(container_id, target_type);
CREATE INDEX idx_measurements_container_created ON measurements(container_id, created_at DESC);
CREATE INDEX idx_measurements_quality_score ON measurements(quality_score) WHERE quality_score IS NOT NULL;
CREATE INDEX idx_measurements_roi_json ON measurements USING GIN (roi_json);
CREATE INDEX idx_measurements_imu_json ON measurements USING GIN (imu_data_json) WHERE imu_data_json IS NOT NULL;

-- ============================================================
-- 3. measurement_sessions テーブルのインデックス
-- ============================================================
CREATE INDEX idx_sessions_container_id ON measurement_sessions(container_id);
CREATE INDEX idx_sessions_status ON measurement_sessions(status);
CREATE INDEX idx_sessions_started_at ON measurement_sessions(started_at DESC);
CREATE INDEX idx_sessions_container_status ON measurement_sessions(container_id, status);

-- ============================================================
-- 4. assets テーブルのインデックス
-- ============================================================
CREATE INDEX idx_assets_type ON assets(type);
CREATE INDEX idx_assets_created_at ON assets(created_at DESC);
CREATE INDEX idx_assets_metadata_json ON assets USING GIN (metadata_json);

-- ============================================================
-- 5. 統計情報更新
-- ============================================================
ANALYZE containers;
ANALYZE measurements;
ANALYZE measurement_sessions;
ANALYZE assets;
ANALYZE system_settings;

