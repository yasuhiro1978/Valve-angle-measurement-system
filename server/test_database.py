#!/usr/bin/env python3
"""
データベース接続モジュールの単体テスト
"""

import sys
import os
import unittest
from sqlalchemy import text

# サーバーディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(__file__))

from database import engine, SessionLocal, Base, get_db, DATABASE_URL


class TestDatabase(unittest.TestCase):
    """Databaseモジュールの単体テスト"""
    
    def test_database_url_exists(self):
        """DATABASE_URLが設定されているか"""
        self.assertIsNotNone(DATABASE_URL)
        self.assertIn('postgresql://', DATABASE_URL)
    
    def test_engine_created(self):
        """エンジンが作成されているか"""
        self.assertIsNotNone(engine)
    
    def test_session_local_exists(self):
        """SessionLocalが作成されているか"""
        self.assertIsNotNone(SessionLocal)
    
    def test_get_db_context_manager(self):
        """get_dbがコンテキストマネージャーとして動作するか"""
        db_gen = get_db()
        db = next(db_gen)
        
        self.assertIsNotNone(db)
        
        # クリーンアップ
        try:
            next(db_gen)
        except StopIteration:
            pass
    
    def test_database_connection(self):
        """データベース接続テスト"""
        try:
            db = SessionLocal()
            # シンプルなクエリを実行
            result = db.execute(text("SELECT 1"))
            row = result.fetchone()
            self.assertEqual(row[0], 1)
            db.close()
        except Exception as e:
            self.fail(f"データベース接続に失敗: {e}")
    
    def test_database_schema_exists(self):
        """データベーステーブルが存在するか確認"""
        try:
            db = SessionLocal()
            # テーブル一覧を取得
            result = db.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result]
            
            # 主要なテーブルが存在するか確認
            expected_tables = ['containers', 'measurements', 'measurement_sessions']
            for table in expected_tables:
                self.assertIn(table, tables, f"テーブル {table} が見つかりません")
            
            db.close()
        except Exception as e:
            self.fail(f"スキーマ確認に失敗: {e}")


if __name__ == '__main__':
    unittest.main(verbosity=2)

