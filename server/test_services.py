#!/usr/bin/env python3
"""
サービス層の単体テスト
"""

import sys
import os
import unittest
from datetime import date, datetime
from sqlalchemy.orm import Session

# サーバーディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, Base, engine
import models
import services


class TestServices(unittest.TestCase):
    """Servicesの単体テスト"""
    
    @classmethod
    def setUpClass(cls):
        """テストクラス全体の初期化"""
        # データベーステーブルを作成
        Base.metadata.create_all(bind=engine)
    
    def setUp(self):
        """各テスト前処理"""
        self.db = SessionLocal()
        # テスト用のデータをクリーンアップ
        self._cleanup_test_data()
    
    def tearDown(self):
        """各テスト後処理"""
        self.db.rollback()
        self.db.close()
    
    def _cleanup_test_data(self):
        """テストデータのクリーンアップ"""
        # テスト用コンテナに関連する計測を削除
        test_containers = self.db.query(models.Container).filter(
            models.Container.container_number.like('TEST-%')
        ).all()
        for container in test_containers:
            self.db.query(models.Measurement).filter(
                models.Measurement.container_id == container.id
            ).delete(synchronize_session=False)
        # テスト用コンテナを削除
        self.db.query(models.Container).filter(
            models.Container.container_number.like('TEST-%')
        ).delete(synchronize_session=False)
        self.db.commit()
    
    def test_get_or_create_container_new(self):
        """コンテナ取得/作成: 新規作成"""
        container = services.get_or_create_container(
            db=self.db,
            container_number='TEST-001',
            processed_date=date.today(),
            description='テストコンテナ',
            operator='test_user'
        )
        
        self.assertIsNotNone(container)
        self.assertEqual(container.container_number, 'TEST-001')
        self.assertEqual(container.status, 'active')
    
    def test_get_or_create_container_existing(self):
        """コンテナ取得/作成: 既存取得"""
        # 最初に作成
        container1 = services.get_or_create_container(
            db=self.db,
            container_number='TEST-002',
            processed_date=date.today(),
            operator='test_user'
        )
        container_id = container1.id
        
        # 再度取得（同じ容器番号 + 処理日）
        container2 = services.get_or_create_container(
            db=self.db,
            container_number='TEST-002',
            processed_date=date.today(),
            operator='test_user'
        )
        
        self.assertEqual(container1.id, container2.id)
        self.assertEqual(container_id, container2.id)
    
    def test_get_container(self):
        """コンテナ取得: ID指定"""
        # コンテナを作成
        container = services.get_or_create_container(
            db=self.db,
            container_number='TEST-003',
            processed_date=date.today()
        )
        container_id = container.id
        
        # IDで取得
        retrieved = services.get_container(self.db, container_id)
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, container_id)
        self.assertEqual(retrieved.container_number, 'TEST-003')
    
    def test_list_containers(self):
        """コンテナ一覧取得"""
        # テスト用コンテナを作成
        for i in range(5):
            services.get_or_create_container(
                db=self.db,
                container_number=f'TEST-LIST-{i:03d}',
                processed_date=date.today()
            )
        
        result = services.list_containers(self.db, page=1, limit=10)
        
        self.assertIn('items', result)
        self.assertIn('total', result)
        self.assertIn('page', result)
        self.assertIsInstance(result['items'], list)
        self.assertGreaterEqual(len(result['items']), 0)
    
    def test_parse_date(self):
        """日付文字列パース"""
        # 正常ケース
        date_str = '2025-01-15'
        parsed = services.parse_date(date_str)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.year, 2025)
        self.assertEqual(parsed.month, 1)
        self.assertEqual(parsed.day, 15)
        
        # 不正な形式（例外が発生することを確認）
        with self.assertRaises(ValueError):
            services.parse_date('invalid-date')


if __name__ == '__main__':
    unittest.main(verbosity=2)

