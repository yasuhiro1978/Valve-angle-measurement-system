#!/usr/bin/env python3
"""
WebSocket接続テストスクリプト
"""

import asyncio
import websockets
import json
import numpy as np
from datetime import datetime

async def test_websocket_connection():
    """WebSocket接続テスト"""
    print("=" * 60)
    print("WebSocket接続テスト")
    print("=" * 60)
    
    uri = "ws://localhost:3000/ws/lidar"
    print(f"接続中: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket接続成功")
            
            # 接続確認メッセージを待機
            response = await websocket.recv()
            data = json.loads(response)
            print(f"✅ 接続確認メッセージ受信: {data.get('message', 'N/A')}")
            
            # テスト1: Ping/Pong
            print("\n--- テスト1: Ping/Pong ---")
            ping_message = {
                "type": "ping",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(ping_message))
            print("📤 Ping送信")
            
            response = await websocket.recv()
            data = json.loads(response)
            if data.get('type') == 'pong':
                print("✅ Pong受信: 成功")
            else:
                print(f"⚠️  予期しないレスポンス: {data}")
            
            # テスト2: 点群データ送信（シミュレーション）
            print("\n--- テスト2: 点群データ送信 ---")
            
            # テスト用の点群データ生成（平面）
            num_points = 100
            points = []
            for i in range(num_points):
                x = np.random.uniform(-0.5, 0.5)
                y = np.random.uniform(-0.5, 0.5)
                z = 1.0  # 固定Z座標（平面）
                points.append({"x": float(x), "y": float(y), "z": float(z)})
            
            lidar_message = {
                "type": "lidar_data",
                "points": points,
                "roi": {
                    "center": {"x": 0.0, "y": 0.0, "z": 1.0},
                    "size": {"width": 1.0, "height": 1.0, "depth": 0.5}
                },
                "imu": {
                    "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},
                    "attitude": {
                        "pitch": 0.0,
                        "roll": 0.0,
                        "yaw": 0.0
                    },
                    "timestamp": datetime.now().isoformat()
                },
                "target_type": "A",
                "basis": "imu",
                "timestamp": datetime.now().isoformat()
            }
            
            await websocket.send(json.dumps(lidar_message))
            print(f"📤 点群データ送信: {len(points)}点")
            
            # 応答を待機（タイムアウト: 10秒）
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                
                if data.get('type') == 'angle_result':
                    print("✅ 角度計算結果受信:")
                    print(f"   ピッチ: {data.get('pitch', 'N/A')}°")
                    print(f"   ロール: {data.get('roll', 'N/A')}°")
                    print(f"   基準: {data.get('basis', 'N/A')}")
                    print(f"   品質スコア: {data.get('quality', {}).get('quality_score', 'N/A')}")
                elif data.get('type') == 'error':
                    print(f"⚠️  エラー: {data.get('message', 'N/A')}")
                else:
                    print(f"⚠️  予期しないレスポンス: {data.get('type', 'N/A')}")
                    
            except asyncio.TimeoutError:
                print("❌ タイムアウト: 応答がありませんでした")
            
            # テスト3: 保存リクエスト（計測結果がある場合）
            print("\n--- テスト3: 保存リクエスト ---")
            # 注意: 実際の保存には計測結果データが必要
            print("ℹ️  保存テストは計測結果取得後に実行可能")
            
            print("\n✅ WebSocket接続テスト完了")
            return True
            
    except websockets.exceptions.ConnectionRefused:
        print("❌ 接続拒否: サーバーが起動していません")
        print("   ヒント: サーバーを起動してください")
        return False
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """メイン処理"""
    result = await test_websocket_connection()
    
    print("\n" + "=" * 60)
    if result:
        print("✅ テスト成功")
    else:
        print("❌ テスト失敗")
    print("=" * 60)
    
    return result


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⚠️  テストが中断されました")
        exit(1)

