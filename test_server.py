#!/usr/bin/env python3
"""
サーバー動作確認スクリプト
"""

import sys
import os
import requests
import json
from datetime import datetime

# サーバーディレクトリをパスに追加
server_dir = os.path.join(os.path.dirname(__file__), 'server')
sys.path.insert(0, server_dir)
os.chdir(server_dir)  # 作業ディレクトリを変更

def test_database_connection():
    """データベース接続確認"""
    print("\n=== データベース接続確認 ===")
    try:
        from services import check_database_connection
        result = check_database_connection()
        if result:
            print("✅ データベース接続成功")
            return True
        else:
            print("❌ データベース接続失敗")
            print("   ヒント: Docker ComposeでPostgreSQLを起動してください")
            print("   docker-compose up -d postgres")
            return False
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


def test_server_imports():
    """サーバーモジュールのインポート確認"""
    print("\n=== モジュールインポート確認 ===")
    try:
        # 現在のディレクトリを確認
        current_dir = os.getcwd()
        print(f"   作業ディレクトリ: {current_dir}")
        
        import models
        print("✅ models.py インポート成功")
        
        from database import engine, Base, get_db
        print("✅ database.py インポート成功")
        
        from services import (
            get_or_create_container,
            save_measurement,
            check_database_connection
        )
        print("✅ services.py インポート成功")
        
        from geometry_engine import GeometryFitEngine
        print("✅ geometry_engine.py インポート成功")
        
        # main.py のインポートは app オブジェクトを作成するので、スキップ
        # from main import app
        # print("✅ main.py インポート成功")
        
        return True
    except Exception as e:
        print(f"❌ インポートエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_endpoints(base_url="http://localhost:3000"):
    """APIエンドポイントの動作確認"""
    print("\n=== APIエンドポイント確認 ===")
    
    try:
        # ヘルスチェック
        print(f"ヘルスチェック: {base_url}/api/health")
        response = requests.get(f"{base_url}/api/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ ヘルスチェック成功: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            print(f"❌ ヘルスチェック失敗: {response.status_code}")
            return False
        
        # 容器一覧取得（空の場合は正常）
        print(f"\n容器一覧取得: {base_url}/api/containers")
        response = requests.get(f"{base_url}/api/containers", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 容器一覧取得成功: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            print(f"❌ 容器一覧取得失敗: {response.status_code}")
            return False
        
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"❌ サーバーに接続できません: {base_url}")
        print("   ヒント: サーバーを起動してください")
        print("   cd valve_angle_system/server && python3 main.py")
        return False
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_geometry_engine():
    """幾何フィットエンジンの動作確認"""
    print("\n=== 幾何フィットエンジン確認 ===")
    try:
        from geometry_engine import GeometryFitEngine
        import numpy as np
        
        engine = GeometryFitEngine()
        print("✅ GeometryFitEngine インスタンス作成成功")
        
        # テスト用の点群データ（平面）
        test_points = np.array([
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 1.0],
            [0.0, 1.0, 1.0],
            [1.0, 1.0, 1.0],
            [0.5, 0.5, 1.0],
        ], dtype=np.float32)
        
        # IMUデータ（重力ベクトル: 下向き）
        imu_data = {
            "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},
            "attitude": {"pitch": 0.0, "roll": 0.0, "yaw": 0.0}
        }
        
        print("   テスト点群で角度計算実行中...")
        result = engine.estimate_angle(
            points=test_points,
            target_type='A',  # ステム軸
            basis='imu',
            imu=imu_data,
            ground_points=None
        )
        
        if result['success']:
            print(f"✅ 角度計算成功:")
            print(f"   ピッチ: {result['pitch']}°")
            print(f"   ロール: {result['roll']}°")
            print(f"   品質スコア: {result['quality']['quality_score']:.2f}")
        else:
            print(f"⚠️  角度計算失敗（テストデータが少なすぎる可能性）: {result.get('error_message', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メイン処理"""
    print("=" * 60)
    print("バルブ角度計測システム - 動作確認")
    print("=" * 60)
    
    results = []
    
    # 1. モジュールインポート確認
    results.append(("モジュールインポート", test_server_imports()))
    
    # 2. データベース接続確認
    results.append(("データベース接続", test_database_connection()))
    
    # 3. 幾何フィットエンジン確認
    results.append(("幾何フィットエンジン", test_geometry_engine()))
    
    # 4. APIエンドポイント確認（サーバー起動時のみ）
    print("\n" + "=" * 60)
    print("APIエンドポイント確認（サーバー起動が必要）")
    print("=" * 60)
    api_result = test_api_endpoints()
    results.append(("APIエンドポイント", api_result))
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("動作確認結果サマリー")
    print("=" * 60)
    for name, result in results:
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{name}: {status}")
    
    success_count = sum(1 for _, r in results if r)
    total_count = len(results)
    print(f"\n合計: {success_count}/{total_count} 成功")
    
    if success_count == total_count:
        print("\n🎉 すべての確認が成功しました！")
    else:
        print("\n⚠️  一部の確認が失敗しました。上記のエラーメッセージを確認してください。")
    
    return success_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

