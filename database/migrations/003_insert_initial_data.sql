-- ============================================================
-- バルブ角度計測システム - 初期データ投入
-- バージョン: 1.0.0
-- 作成日: 2025-01-XX
-- ============================================================

-- ============================================================
-- 1. システム設定の初期値
-- ============================================================
INSERT INTO system_settings (setting_key, setting_value, setting_type, description) VALUES
    ('app_version', '1.0.0', 'string', 'アプリケーションバージョン'),
    ('max_point_count', '10000', 'number', '最大点群数'),
    ('min_inlier_ratio', '0.6', 'number', '最小インライア比率'),
    ('max_residual_rms', '0.01', 'number', '最大残差RMS（メートル）'),
    ('default_measurement_distance', '1.0', 'number', 'デフォルト計測距離（メートル）'),
    ('angle_precision', '1', 'number', '角度表示精度（小数桁数）'),
    ('enable_auto_roi', 'true', 'boolean', '自動ROI生成を有効化'),
    ('enable_manual_roi_adjustment', 'true', 'boolean', '手動ROI調整を有効化')
ON CONFLICT (setting_key) DO NOTHING;

