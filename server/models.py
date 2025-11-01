#!/usr/bin/env python3
"""
SQLAlchemyモデル定義
"""

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, ForeignKey, CheckConstraint, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Asset(Base):
    """アセットテーブル（図面等）"""
    __tablename__ = 'assets'
    
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(20), nullable=False)
    file_path = Column(Text, nullable=False, unique=True)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    metadata_json = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(String(100))
    
    # リレーションシップ
    containers = relationship("Container", back_populates="drawing_asset")


class Container(Base):
    """容器マスタテーブル"""
    __tablename__ = 'containers'
    
    id = Column(Integer, primary_key=True, index=True)
    container_number = Column(String(50), nullable=False)
    processed_date = Column(Date, nullable=False)
    drawing_pdf_id = Column(Integer, ForeignKey('assets.id', ondelete='SET NULL'), nullable=True)
    description = Column(Text)
    location = Column(String(255))
    status = Column(String(20), default='active')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(String(100))
    
    # リレーションシップ
    drawing_asset = relationship("Asset", back_populates="containers")
    measurements = relationship("Measurement", back_populates="container", cascade="all, delete-orphan")
    sessions = relationship("MeasurementSession", back_populates="container", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive', 'archived')", name='check_container_status'),
    )


class MeasurementSession(Base):
    """計測セッションテーブル"""
    __tablename__ = 'measurement_sessions'
    
    id = Column(Integer, primary_key=True, index=True)
    container_id = Column(Integer, ForeignKey('containers.id', ondelete='CASCADE'), nullable=False)
    session_name = Column(String(255))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    status = Column(String(20), default='in_progress')
    operator = Column(String(100))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # リレーションシップ
    container = relationship("Container", back_populates="sessions")
    measurements = relationship("Measurement", back_populates="session")
    
    __table_args__ = (
        CheckConstraint("status IN ('in_progress', 'completed', 'cancelled')", name='check_session_status'),
    )


class Measurement(Base):
    """計測結果テーブル"""
    __tablename__ = 'measurements'
    
    id = Column(Integer, primary_key=True, index=True)
    container_id = Column(Integer, ForeignKey('containers.id', ondelete='CASCADE'), nullable=False)
    session_id = Column(Integer, ForeignKey('measurement_sessions.id', ondelete='SET NULL'), nullable=True)
    target_type = Column(String(1), nullable=False)
    pitch_deg = Column(Float, nullable=False)
    roll_deg = Column(Float, nullable=False)
    basis = Column(String(10), nullable=False)
    
    # ROI情報
    roi_json = Column(JSON, default={})
    roi_center_x = Column(Float)
    roi_center_y = Column(Float)
    roi_center_z = Column(Float)
    roi_width = Column(Float)
    roi_height = Column(Float)
    roi_depth = Column(Float)
    
    # 計測情報
    distance_m = Column(Float)
    point_count = Column(Integer)
    inlier_ratio = Column(Float)
    residual_rms = Column(Float)
    quality_score = Column(Float)
    
    # メタデータ
    imu_data_json = Column(JSON, default={})
    measurement_note = Column(Text)
    operator = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # リレーションシップ
    container = relationship("Container", back_populates="measurements")
    session = relationship("MeasurementSession", back_populates="measurements")
    
    __table_args__ = (
        CheckConstraint("target_type IN ('A', 'B', 'C', 'D')", name='check_target_type'),
        CheckConstraint("pitch_deg >= -180.0 AND pitch_deg <= 180.0", name='check_pitch_range'),
        CheckConstraint("roll_deg >= -180.0 AND roll_deg <= 180.0", name='check_roll_range'),
        CheckConstraint("basis IN ('imu', 'plane')", name='check_basis'),
        CheckConstraint("distance_m > 0 AND distance_m <= 10.0", name='check_distance_range'),
    )


class SystemSetting(Base):
    """システム設定テーブル"""
    __tablename__ = 'system_settings'
    
    id = Column(Integer, primary_key=True, index=True)
    setting_key = Column(String(100), nullable=False, unique=True)
    setting_value = Column(Text)
    setting_type = Column(String(20), default='string')
    description = Column(Text)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(String(100))
    
    __table_args__ = (
        CheckConstraint("setting_type IN ('string', 'number', 'boolean', 'json')", name='check_setting_type'),
    )

