#!/usr/bin/env python3
"""
データベース接続・操作モジュール
"""

from sqlalchemy import create_engine, pool
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import os
from typing import AsyncGenerator

# データベースURL
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://valve_user:valve_password@localhost:5432/valve_angle_db'
)

# 非同期エンジン用（psycopg2の非同期版を使用する場合は変更が必要）
# 現時点では同期版を使用
# async_postgres_url = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')
# async_engine = create_async_engine(async_postgres_url)

# 同期エンジン（開発初期は同期版を使用）
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # 接続確認
    echo=False  # SQLログ出力（開発時はTrueに設定可能）
)

# セッションファクトリー
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Baseクラス（モデル定義で使用）
Base = declarative_base()


def get_db() -> SessionLocal:
    """
    データベースセッション取得（依存性注入用）
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# モデルインポート（循環参照回避のため）
# 実際の使用時は models.py をインポート

