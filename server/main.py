#!/usr/bin/env python3
"""
バルブ角度計測システム - FastAPIサーバー
"""

import os
import ssl
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from contextlib import asynccontextmanager
import uvicorn
import json
import logging
from datetime import datetime
from typing import Set
import numpy as np

from database import engine, Base, get_db, SessionLocal
import models  # モデル定義をインポート（テーブル作成用）
from geometry_engine import GeometryFitEngine
from services import (
    get_or_create_container,
    get_container,
    list_containers,
    create_session,
    get_session,
    complete_session,
    save_measurement,
    get_measurement,
    list_measurements,
    delete_measurement,
    check_database_connection,
    parse_date
)
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 接続中のクライアント管理
connected_clients: Set[WebSocket] = set()

# 幾何フィットエンジン
geometry_engine = GeometryFitEngine()

# データベーステーブル作成（起動時）
@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーション起動・終了時の処理"""
    # 起動時
    logger.info("サーバー起動中...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("データベーステーブル作成完了")
    except Exception as e:
        logger.warning(f"⚠️ データベース接続エラー（起動は継続）: {e}")
        logger.warning("⚠️ データベース機能は使用できませんが、WebSocketは動作します")
    yield
    # 終了時
    logger.info("サーバー終了中...")

# FastAPIアプリケーション作成
app = FastAPI(
    title="バルブ角度計測システム API",
    description="iPhone Pro LiDARを使用した金属容器バルブの地面相対角度算出システム",
    version="1.0.0",
    lifespan=lifespan
)

# CORS設定（社内LANのみ）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://192.168.*.*", "https://localhost:3000"],  # 社内LAN（環境に応じて変更してください）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静的ファイル配信（クライアントHTML）
import os
client_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "client")
if os.path.exists(client_dir):
    app.mount("/static", StaticFiles(directory=client_dir), name="static")
else:
    logger.warning(f"⚠️ クライアントディレクトリが見つかりません: {client_dir}")


@app.get("/", response_class=HTMLResponse)
async def root():
    """ルートパス - PC側ダッシュボード"""
    pc_file = os.path.join(client_dir, "pc/valve_viewer.html")
    if os.path.exists(pc_file):
        return FileResponse(pc_file)
    return HTMLResponse("<h1>バルブ角度計測システム</h1><p>PC側ビューアはまだ実装されていません（Sprint 4）</p>")


@app.get("/iphone", response_class=HTMLResponse)
async def iphone_client():
    """iPhone側クライアント"""
    iphone_file = os.path.join(client_dir, "iphone/valve_client.html")
    if os.path.exists(iphone_file):
        return FileResponse(iphone_file)
    return HTMLResponse("<h1>バルブ角度計測システム</h1><p>iPhone側クライアントはまだ実装されていません（Sprint 2）</p>")


@app.get("/pc", response_class=HTMLResponse)
async def pc_viewer():
    """PC側ビューア"""
    pc_file = os.path.join(client_dir, "pc/valve_viewer.html")
    if os.path.exists(pc_file):
        return FileResponse(pc_file)
    return HTMLResponse("<h1>バルブ角度計測システム</h1><p>PC側ビューアはまだ実装されていません（Sprint 4）</p>")


@app.websocket("/ws/lidar")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocketエンドポイント"""
    await websocket.accept()
    connected_clients.add(websocket)
    client_info = f"{websocket.client.host}:{websocket.client.port}"
    logger.info(f"✅ クライアント接続: {client_info}")
    
    try:
        # 接続確認メッセージを送信
        await websocket.send_json({
            "type": "connection",
            "message": "LiDARサーバーに接続しました",
            "timestamp": datetime.now().isoformat(),
            "status": "connected",
            "server_version": "1.0.0"
        })
        
        # メッセージ受信ループ
        while True:
            try:
                data = await websocket.receive_text()
                await handle_websocket_message(websocket, data)
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError as e:
                logger.error(f"JSONデコードエラー: {e}")
                await websocket.send_json({
                    "type": "error",
                    "code": "INVALID_JSON",
                    "message": f"JSONデコードエラー: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"メッセージ処理エラー: {e}")
                await websocket.send_json({
                    "type": "error",
                    "code": "PROCESSING_ERROR",
                    "message": f"処理エラー: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
    
    except WebSocketDisconnect:
        logger.info(f"❌ クライアント切断: {client_info}")
    except Exception as e:
        logger.error(f"❌ WebSocket処理エラー: {e}")
    finally:
        connected_clients.discard(websocket)
        logger.info(f"🔌 クライアント削除: {client_info}")


async def handle_websocket_message(websocket: WebSocket, message: str):
    """WebSocketメッセージ処理"""
    data = json.loads(message)
    message_type = data.get("type", "unknown")
    
    if message_type == "lidar_data":
        await handle_lidar_data(websocket, data)
    elif message_type == "save_measurement":
        await handle_save_measurement(websocket, data)
    elif message_type == "ping":
        await websocket.send_json({
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        })
    else:
        logger.warning(f"⚠️ 未知のメッセージタイプ: {message_type}")
        await websocket.send_json({
            "type": "error",
            "code": "UNKNOWN_MESSAGE_TYPE",
            "message": f"未知のメッセージタイプ: {message_type}",
            "timestamp": datetime.now().isoformat()
        })


async def handle_lidar_data(websocket: WebSocket, data: dict):
    """LiDAR点群データ処理"""
    try:
        logger.info(f"📡 LiDARデータ受信: target_type={data.get('target_type', 'N/A')}, 点数={len(data.get('points', []))}")
        
        # 点群データをNumPy配列に変換
        points_raw = data.get('points', [])
        if not points_raw:
            await websocket.send_json({
                "type": "error",
                "code": "NO_POINTS",
                "message": "点群データが空です",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        points = np.array([[p['x'], p['y'], p['z']] for p in points_raw], dtype=np.float32)
        
        # 対象タイプと基準方式を取得
        target_type = data.get('target_type', 'A')
        basis = data.get('basis', 'imu')
        imu_raw = data.get('imu')
        
        # IMUデータの形式変換（辞書形式から配列形式へ）
        imu = None
        if imu_raw and 'gravity' in imu_raw:
            gravity = imu_raw['gravity']
            # 辞書形式 {'x': ..., 'y': ..., 'z': ...} の場合は配列に変換
            if isinstance(gravity, dict):
                imu = {
                    'gravity': np.array([gravity.get('x', 0.0), gravity.get('y', 0.0), gravity.get('z', 0.0)], dtype=np.float32)
                }
            # 配列形式の場合はそのまま使用
            elif isinstance(gravity, (list, np.ndarray)):
                imu = {
                    'gravity': np.array(gravity, dtype=np.float32) if not isinstance(gravity, np.ndarray) else gravity
                }
        
        # 幾何フィット実行
        result = geometry_engine.estimate_angle(
            points=points,
            target_type=target_type,
            basis=basis,
            imu=imu,
            ground_points=None  # 将来拡張: 地面点群を取得して渡す
        )
        
        if not result['success']:
            # 失敗時
            await websocket.send_json({
                "type": "error",
                "code": "FIT_ERROR",
                "message": result.get('error_message', '幾何フィットに失敗しました'),
                "details": {
                    "inlier_ratio": result['quality']['inlier_ratio'],
                    "residual_rms": result['quality']['residual_rms'],
                    "min_required": 0.6
                },
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # 成功時: 角度計算結果を送信
        # 計測ID生成（暫定: タイムスタンプベース）
        # 注意: 実際の保存時には、このデータを含めて保存する必要がある
        measurement_id = int(datetime.now().timestamp() * 1000) % 1000000
        
        # 角度計算結果をキャッシュ（将来拡張: Redis等を使用）
        # 現在はクライアント側で保持する前提
        angle_result = {
            "type": "angle_result",
            "target_type": target_type,
            "pitch": result['pitch'],
            "roll": result['roll'],
            "basis": result['basis_used'],
            "quality": {
                "inlier_ratio": result['quality']['inlier_ratio'],
                "residual_rms": result['quality']['residual_rms'],
                "quality_score": result['quality']['quality_score']
            },
            "measurement_id": measurement_id,
            "processing_time_ms": result['processing_time_ms'],
            "timestamp": datetime.now().isoformat(),
            # 保存用データも含める
            "measurement_data": {
                "target_type": target_type,
                "pitch": result['pitch'],
                "roll": result['roll'],
                "basis": result['basis_used'],
                "quality": {
                    "inlier_ratio": result['quality']['inlier_ratio'],
                    "residual_rms": result['quality']['residual_rms'],
                    "quality_score": result['quality']['quality_score']
                },
                "imu": imu,
                "roi": data.get('roi'),
                "distance": None,  # 将来拡張: 点群から距離を計算
                "point_count": len(points)
            }
        }
        
        await websocket.send_json(angle_result)
        
        logger.info(f"✅ 角度計算完了: ピッチ={result['pitch']}°, ロール={result['roll']}°")
        
    except Exception as e:
        logger.error(f"❌ LiDARデータ処理エラー: {e}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "code": "PROCESSING_ERROR",
            "message": f"データ処理エラー: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })


async def handle_save_measurement(websocket: WebSocket, data: dict):
    """計測結果保存（データベース保存）"""
    try:
        logger.info(f"💾 保存リクエスト: {data.get('measurement_id', 'N/A')}")
        
        # データベース接続確認
        if not check_database_connection():
            await websocket.send_json({
                "type": "error",
                "code": "DATABASE_ERROR",
                "message": "データベースに接続できません",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # 角度計算結果のキャッシュを取得（将来拡張: Redis等を使用）
        # 現在はWebSocketメッセージに含める前提
        measurement_data = data.get('measurement_data', {})
        if not measurement_data:
            await websocket.send_json({
                "type": "error",
                "code": "MISSING_DATA",
                "message": "計測結果データが見つかりません",
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # コンテナ取得または作成
        db = SessionLocal()
        try:
            container_number = data.get('container_number', 'CNT-TEST')
            processed_date_str = data.get('processed_date', datetime.now().strftime('%Y-%m-%d'))
            processed_date = parse_date(processed_date_str)
            
            container = get_or_create_container(
                db=db,
                container_number=container_number,
                processed_date=processed_date,
                operator=data.get('operator', 'operator')
            )
            
            # セッションID取得（オプション）
            session_id = data.get('session_id')
            if session_id:
                session = get_session(db, session_id)
                if not session:
                    logger.warning(f"セッションが見つかりません: {session_id}")
                    session_id = None
            
            # 計測結果保存
            measurement = save_measurement(
                db=db,
                container_id=container.id,
                target_type=measurement_data.get('target_type', 'A'),
                pitch_deg=measurement_data.get('pitch', 0.0),
                roll_deg=measurement_data.get('roll', 0.0),
                basis=measurement_data.get('basis', 'imu'),
                session_id=session_id,
                roi_json=measurement_data.get('roi_json'),
                roi_center=measurement_data.get('roi', {}).get('center'),
                roi_size=measurement_data.get('roi', {}).get('size'),
                distance_m=measurement_data.get('distance'),
                point_count=measurement_data.get('point_count'),
                inlier_ratio=measurement_data.get('quality', {}).get('inlier_ratio'),
                residual_rms=measurement_data.get('quality', {}).get('residual_rms'),
                quality_score=measurement_data.get('quality', {}).get('quality_score'),
                imu_data_json=measurement_data.get('imu'),
                measurement_note=data.get('note'),
                operator=data.get('operator', 'operator')
            )
            
            # 成功レスポンス
            await websocket.send_json({
                "type": "save_response",
                "status": "saved",
                "measurement_id": measurement.id,
                "container_id": container.id,
                "message": "計測結果を保存しました",
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"✅ 計測結果を保存: ID={measurement.id}, 容器ID={container.id}")
            
        except ValueError as e:
            await websocket.send_json({
                "type": "error",
                "code": "VALIDATION_ERROR",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            })
        except RuntimeError as e:
            await websocket.send_json({
                "type": "error",
                "code": "DATABASE_ERROR",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            })
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ 保存処理エラー: {e}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "code": "PROCESSING_ERROR",
            "message": f"保存処理エラー: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })


@app.get("/api/health")
async def health_check():
    """ヘルスチェック"""
    db_status = "connected" if check_database_connection() else "disconnected"
    
    return {
        "status": "healthy",
        "version": "1.0.0",
        "connected_clients": len(connected_clients),
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================
# Pydanticモデル（リクエスト/レスポンス）
# ============================================================

class ContainerCreate(BaseModel):
    container_number: str = Field(..., min_length=1, max_length=50)
    processed_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')
    description: Optional[str] = None
    location: Optional[str] = None
    drawing_pdf_id: Optional[int] = None
    operator: Optional[str] = None


class MeasurementCreate(BaseModel):
    container_id: int
    session_id: Optional[int] = None
    target_type: str = Field(..., pattern=r'^[ABCD]$')
    pitch_deg: float = Field(..., ge=-180.0, le=180.0)
    roll_deg: float = Field(..., ge=-180.0, le=180.0)
    basis: str = Field(..., pattern=r'^(imu|plane)$')
    roi_json: Optional[dict] = None
    roi_center: Optional[dict] = None
    roi_size: Optional[dict] = None
    distance_m: Optional[float] = Field(None, gt=0.0, le=10.0)
    point_count: Optional[int] = None
    inlier_ratio: Optional[float] = Field(None, ge=0.0, le=1.0)
    residual_rms: Optional[float] = None
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    imu_data_json: Optional[dict] = None
    measurement_note: Optional[str] = None
    operator: Optional[str] = None


class SessionCreate(BaseModel):
    container_id: int
    session_name: Optional[str] = None
    operator: Optional[str] = None
    notes: Optional[str] = None


# ============================================================
# REST API エンドポイント
# ============================================================

@app.get("/api/containers")
async def api_list_containers(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    db: SessionLocal = Depends(get_db)
):
    """容器一覧取得"""
    try:
        result = list_containers(db, status=status, page=page, limit=limit)
        return {
            "success": True,
            "data": {
                "items": [
                    {
                        "id": c.id,
                        "container_number": c.container_number,
                        "processed_date": c.processed_date.isoformat(),
                        "description": c.description,
                        "location": c.location,
                        "status": c.status,
                        "created_at": c.created_at.isoformat() if c.created_at else None
                    }
                    for c in result["items"]
                ],
                "total": result["total"],
                "page": result["page"],
                "limit": result["limit"],
                "pages": result["pages"]
            }
        }
    except Exception as e:
        logger.error(f"容器一覧取得エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/containers")
async def api_create_container(
    container: ContainerCreate,
    db: SessionLocal = Depends(get_db)
):
    """容器登録"""
    try:
        processed_date = parse_date(container.processed_date)
        c = get_or_create_container(
            db=db,
            container_number=container.container_number,
            processed_date=processed_date,
            description=container.description,
            location=container.location,
            drawing_pdf_id=container.drawing_pdf_id,
            operator=container.operator
        )
        return {
            "success": True,
            "data": {
                "id": c.id,
                "container_number": c.container_number,
                "processed_date": c.processed_date.isoformat(),
                "status": c.status
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/containers/{container_id}")
async def api_get_container(
    container_id: int,
    db: SessionLocal = Depends(get_db)
):
    """容器詳細取得"""
    container = get_container(db, container_id)
    if not container:
        raise HTTPException(status_code=404, detail="容器が見つかりません")
    
    return {
        "success": True,
        "data": {
            "id": container.id,
            "container_number": container.container_number,
            "processed_date": container.processed_date.isoformat(),
            "description": container.description,
            "location": container.location,
            "status": container.status,
            "created_at": container.created_at.isoformat() if container.created_at else None
        }
    }


@app.get("/api/measurements")
async def api_list_measurements(
    container_id: Optional[int] = None,
    session_id: Optional[int] = None,
    target_type: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    db: SessionLocal = Depends(get_db)
):
    """計測結果一覧取得"""
    try:
        result = list_measurements(
            db,
            container_id=container_id,
            session_id=session_id,
            target_type=target_type,
            page=page,
            limit=limit
        )
        return {
            "success": True,
            "data": {
                "items": [
                    {
                        "id": m.id,
                        "container_id": m.container_id,
                        "session_id": m.session_id,
                        "target_type": m.target_type,
                        "pitch_deg": m.pitch_deg,
                        "roll_deg": m.roll_deg,
                        "basis": m.basis,
                        "distance_m": m.distance_m,
                        "quality_score": m.quality_score,
                        "created_at": m.created_at.isoformat() if m.created_at else None
                    }
                    for m in result["items"]
                ],
                "total": result["total"],
                "page": result["page"],
                "limit": result["limit"],
                "pages": result["pages"]
            }
        }
    except Exception as e:
        logger.error(f"計測結果一覧取得エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/measurements")
async def api_create_measurement(
    measurement: MeasurementCreate,
    db: SessionLocal = Depends(get_db)
):
    """計測結果保存"""
    try:
        m = save_measurement(
            db=db,
            container_id=measurement.container_id,
            target_type=measurement.target_type,
            pitch_deg=measurement.pitch_deg,
            roll_deg=measurement.roll_deg,
            basis=measurement.basis,
            session_id=measurement.session_id,
            roi_json=measurement.roi_json,
            roi_center=measurement.roi_center,
            roi_size=measurement.roi_size,
            distance_m=measurement.distance_m,
            point_count=measurement.point_count,
            inlier_ratio=measurement.inlier_ratio,
            residual_rms=measurement.residual_rms,
            quality_score=measurement.quality_score,
            imu_data_json=measurement.imu_data_json,
            measurement_note=measurement.measurement_note,
            operator=measurement.operator
        )
        return {
            "success": True,
            "data": {
                "id": m.id,
                "container_id": m.container_id,
                "target_type": m.target_type,
                "pitch_deg": m.pitch_deg,
                "roll_deg": m.roll_deg
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/measurements/{measurement_id}")
async def api_get_measurement(
    measurement_id: int,
    db: SessionLocal = Depends(get_db)
):
    """計測結果詳細取得"""
    measurement = get_measurement(db, measurement_id)
    if not measurement:
        raise HTTPException(status_code=404, detail="計測結果が見つかりません")
    
    return {
        "success": True,
        "data": {
            "id": measurement.id,
            "container_id": measurement.container_id,
            "session_id": measurement.session_id,
            "target_type": measurement.target_type,
            "pitch_deg": measurement.pitch_deg,
            "roll_deg": measurement.roll_deg,
            "basis": measurement.basis,
            "roi_json": measurement.roi_json,
            "distance_m": measurement.distance_m,
            "point_count": measurement.point_count,
            "inlier_ratio": measurement.inlier_ratio,
            "residual_rms": measurement.residual_rms,
            "quality_score": measurement.quality_score,
            "created_at": measurement.created_at.isoformat() if measurement.created_at else None
        }
    }


@app.delete("/api/measurements/{measurement_id}")
async def api_delete_measurement(
    measurement_id: int,
    db: SessionLocal = Depends(get_db)
):
    """計測結果削除"""
    if delete_measurement(db, measurement_id):
        return {"success": True, "message": "計測結果を削除しました"}
    else:
        raise HTTPException(status_code=404, detail="計測結果が見つかりません")


@app.post("/api/sessions")
async def api_create_session(
    session: SessionCreate,
    db: SessionLocal = Depends(get_db)
):
    """計測セッション作成"""
    try:
        s = create_session(
            db=db,
            container_id=session.container_id,
            session_name=session.session_name,
            operator=session.operator,
            notes=session.notes
        )
        return {
            "success": True,
            "data": {
                "id": s.id,
                "container_id": s.container_id,
                "session_name": s.session_name,
                "status": s.status
            }
        }
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}")
async def api_get_session(
    session_id: int,
    db: SessionLocal = Depends(get_db)
):
    """計測セッション詳細取得"""
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    
    return {
        "success": True,
        "data": {
            "id": session.id,
            "container_id": session.container_id,
            "session_name": session.session_name,
            "status": session.status,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None
        }
    }


if __name__ == "__main__":
    # SSL証明書確認（サーバーディレクトリからの相対パス）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    default_cert = os.path.join(project_root, "certs", "cert.pem")
    default_key = os.path.join(project_root, "certs", "key.pem")
    
    cert_file = os.getenv("SSL_CERT_FILE", default_cert)
    key_file = os.getenv("SSL_KEY_FILE", default_key)
    
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", 3000))
    
    if os.path.exists(cert_file) and os.path.exists(key_file):
        logger.info("HTTPS証明書が見つかりました。HTTPSモードで起動します...")
        uvicorn.run(
            app,
            host=host,
            port=port,
            ssl_keyfile=key_file,
            ssl_certfile=cert_file
        )
    else:
        logger.warning("HTTPS証明書が見つかりません。HTTPモードで起動します...")
        logger.warning(f"証明書ファイル: {cert_file}, {key_file}")
        uvicorn.run(
            app,
            host=host,
            port=port
        )

