#!/usr/bin/env python3
"""
データベース操作サービス層
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from datetime import datetime, date
from typing import Optional, List, Dict, Any
import logging

import models
from database import SessionLocal

logger = logging.getLogger(__name__)


# ============================================================
# コンテナ管理サービス
# ============================================================

def get_or_create_container(
    db: Session,
    container_number: str,
    processed_date: date,
    description: Optional[str] = None,
    location: Optional[str] = None,
    drawing_pdf_id: Optional[int] = None,
    operator: Optional[str] = None
) -> models.Container:
    """
    コンテナを取得または作成
    
    Args:
        db: データベースセッション
        container_number: 容器番号
        processed_date: 処理日
        description: 説明
        location: 場所
        drawing_pdf_id: 図面PDFアセットID
        operator: オペレータ名
        
    Returns:
        Container: コンテナオブジェクト
    """
    try:
        # 既存のコンテナを検索（容器番号 + 処理日でユニークキー）
        container = db.query(models.Container).filter(
            models.Container.container_number == container_number,
            models.Container.processed_date == processed_date
        ).first()
        
        if container:
            logger.info(f"既存のコンテナを取得: ID={container.id}, {container_number}")
            return container
        
        # 新規作成
        container = models.Container(
            container_number=container_number,
            processed_date=processed_date,
            description=description,
            location=location,
            drawing_pdf_id=drawing_pdf_id,
            status='active',
            created_by=operator
        )
        
        db.add(container)
        db.commit()
        db.refresh(container)
        
        logger.info(f"新規コンテナを作成: ID={container.id}, {container_number}")
        return container
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"コンテナ作成エラー（整合性違反）: {e}")
        raise ValueError(f"コンテナの作成に失敗しました: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"コンテナ作成エラー（DB）: {e}")
        raise RuntimeError(f"データベースエラー: {str(e)}")


def get_container(db: Session, container_id: int) -> Optional[models.Container]:
    """コンテナを取得"""
    return db.query(models.Container).filter(models.Container.id == container_id).first()


def list_containers(
    db: Session,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 10
) -> Dict[str, Any]:
    """
    コンテナ一覧を取得
    
    Returns:
        Dict with 'items' and 'total'
    """
    query = db.query(models.Container)
    
    if status:
        query = query.filter(models.Container.status == status)
    
    total = query.count()
    
    # ページネーション
    offset = (page - 1) * limit
    items = query.order_by(models.Container.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit > 0 else 0
    }


# ============================================================
# 計測セッション管理サービス
# ============================================================

def create_session(
    db: Session,
    container_id: int,
    session_name: Optional[str] = None,
    operator: Optional[str] = None,
    notes: Optional[str] = None
) -> models.MeasurementSession:
    """
    計測セッションを作成
    
    Args:
        db: データベースセッション
        container_id: 容器ID
        session_name: セッション名
        operator: オペレータ名
        notes: 備考
        
    Returns:
        MeasurementSession: セッションオブジェクト
    """
    try:
        session = models.MeasurementSession(
            container_id=container_id,
            session_name=session_name or f"Session-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            operator=operator,
            notes=notes,
            status='in_progress'
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        logger.info(f"計測セッションを作成: ID={session.id}, コンテナID={container_id}")
        return session
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"セッション作成エラー: {e}")
        raise RuntimeError(f"セッション作成エラー: {str(e)}")


def get_session(db: Session, session_id: int) -> Optional[models.MeasurementSession]:
    """計測セッションを取得"""
    return db.query(models.MeasurementSession).filter(
        models.MeasurementSession.id == session_id
    ).first()


def complete_session(db: Session, session_id: int) -> bool:
    """計測セッションを完了にする"""
    try:
        session = get_session(db, session_id)
        if not session:
            return False
        
        session.status = 'completed'
        session.completed_at = datetime.now()
        db.commit()
        
        logger.info(f"セッションを完了: ID={session_id}")
        return True
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"セッション完了エラー: {e}")
        return False


# ============================================================
# 計測結果保存サービス
# ============================================================

def save_measurement(
    db: Session,
    container_id: int,
    target_type: str,
    pitch_deg: float,
    roll_deg: float,
    basis: str,
    session_id: Optional[int] = None,
    roi_json: Optional[Dict] = None,
    roi_center: Optional[Dict[str, float]] = None,
    roi_size: Optional[Dict[str, float]] = None,
    distance_m: Optional[float] = None,
    point_count: Optional[int] = None,
    inlier_ratio: Optional[float] = None,
    residual_rms: Optional[float] = None,
    quality_score: Optional[float] = None,
    imu_data_json: Optional[Dict] = None,
    measurement_note: Optional[str] = None,
    operator: Optional[str] = None
) -> models.Measurement:
    """
    計測結果を保存
    
    Args:
        db: データベースセッション
        container_id: 容器ID
        target_type: 対象タイプ（A/B/C/D）
        pitch_deg: ピッチ角度（度）
        roll_deg: ロール角度（度）
        basis: 基準方式（imu/plane）
        session_id: セッションID（オプション）
        roi_json: ROI情報（JSON）
        roi_center: ROI中心座標
        roi_size: ROIサイズ
        distance_m: 距離（メートル）
        point_count: 点群数
        inlier_ratio: インライア率
        residual_rms: 残差RMS
        quality_score: 品質スコア
        imu_data_json: IMUデータ（JSON）
        measurement_note: 計測備考
        operator: オペレータ名
        
    Returns:
        Measurement: 保存された計測結果
    """
    try:
        # 角度を1桁に丸める
        pitch_rounded = round(pitch_deg, 1)
        roll_rounded = round(roll_deg, 1)
        
        measurement = models.Measurement(
            container_id=container_id,
            session_id=session_id,
            target_type=target_type,
            pitch_deg=pitch_rounded,
            roll_deg=roll_rounded,
            basis=basis,
            roi_json=roi_json or {},
            roi_center_x=roi_center.get('x') if roi_center else None,
            roi_center_y=roi_center.get('y') if roi_center else None,
            roi_center_z=roi_center.get('z') if roi_center else None,
            roi_width=roi_size.get('width') if roi_size else None,
            roi_height=roi_size.get('height') if roi_size else None,
            roi_depth=roi_size.get('depth') if roi_size else None,
            distance_m=distance_m,
            point_count=point_count,
            inlier_ratio=inlier_ratio,
            residual_rms=residual_rms,
            quality_score=quality_score,
            imu_data_json=imu_data_json or {},
            measurement_note=measurement_note,
            operator=operator
        )
        
        db.add(measurement)
        db.commit()
        db.refresh(measurement)
        
        logger.info(
            f"計測結果を保存: ID={measurement.id}, "
            f"容器ID={container_id}, 対象={target_type}, "
            f"ピッチ={pitch_rounded}°, ロール={roll_rounded}°"
        )
        
        return measurement
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"計測結果保存エラー（整合性違反）: {e}")
        raise ValueError(f"計測結果の保存に失敗しました: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"計測結果保存エラー（DB）: {e}")
        raise RuntimeError(f"データベースエラー: {str(e)}")


def get_measurement(db: Session, measurement_id: int) -> Optional[models.Measurement]:
    """計測結果を取得"""
    return db.query(models.Measurement).filter(
        models.Measurement.id == measurement_id
    ).first()


def list_measurements(
    db: Session,
    container_id: Optional[int] = None,
    session_id: Optional[int] = None,
    target_type: Optional[str] = None,
    page: int = 1,
    limit: int = 10
) -> Dict[str, Any]:
    """
    計測結果一覧を取得
    
    Returns:
        Dict with 'items' and 'total'
    """
    query = db.query(models.Measurement)
    
    if container_id:
        query = query.filter(models.Measurement.container_id == container_id)
    if session_id:
        query = query.filter(models.Measurement.session_id == session_id)
    if target_type:
        query = query.filter(models.Measurement.target_type == target_type)
    
    total = query.count()
    
    # ページネーション
    offset = (page - 1) * limit
    items = query.order_by(models.Measurement.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if limit > 0 else 0
    }


def delete_measurement(db: Session, measurement_id: int) -> bool:
    """計測結果を削除"""
    try:
        measurement = get_measurement(db, measurement_id)
        if not measurement:
            return False
        
        db.delete(measurement)
        db.commit()
        
        logger.info(f"計測結果を削除: ID={measurement_id}")
        return True
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"計測結果削除エラー: {e}")
        return False


# ============================================================
# ヘルパー関数
# ============================================================

def check_database_connection() -> bool:
    """データベース接続確認"""
    try:
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception as e:
        logger.error(f"データベース接続エラー: {e}")
        return False


def parse_date(date_str: str) -> date:
    """日付文字列をdateオブジェクトに変換"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError(f"無効な日付形式: {date_str} (期待: YYYY-MM-DD)")

