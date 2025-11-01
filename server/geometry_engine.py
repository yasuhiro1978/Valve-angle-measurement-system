#!/usr/bin/env python3
"""
幾何フィットエンジン: バルブ角度計測システム
RANSACを使用した平面・円柱・直線フィットと角度計算
"""

import numpy as np
import open3d as o3d
from typing import Literal, Optional, Dict, Tuple
from dataclasses import dataclass
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class FitResult:
    """フィット結果データクラス"""
    kind: Literal['plane', 'line', 'circle']
    direction: np.ndarray  # plane: normal, line: axis
    point: np.ndarray      # 任意の代表点
    inlier_ratio: float
    residual_rms: float
    iters: int
    inlier_indices: np.ndarray


class GeometryFitEngine:
    """幾何フィットエンジン"""
    
    def __init__(self):
        # RANSACパラメータ（初期値）
        self.plane_distance_threshold = 0.01  # 1cm
        self.line_distance_threshold = 0.01   # 1cm
        self.plane_ransac_n = 3
        self.line_ransac_n = 2
        self.plane_num_iterations = 1000
        self.line_num_iterations = 2000
        
        # 品質閾値
        self.min_inlier_ratio = 0.6
        self.max_residual_rms = 0.01  # 1cm
        
    def preprocess_points(self, points: np.ndarray) -> Tuple[o3d.geometry.PointCloud, int]:
        """
        前処理: 外れ値除去
        
        Args:
            points: 入力点群 [N, 3]
            
        Returns:
            (processed_pcd, original_count): 処理後点群、元の点数
        """
        original_count = len(points)
        
        if original_count < 100:
            logger.warning(f"点数不足: {original_count}点（最小100点必要）")
            return None, original_count
        
        # NumPy配列をOpen3D PointCloudに変換
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        
        # 統計的外れ値除去
        pcd, inlier_indices = pcd.remove_statistical_outlier(
            nb_neighbors=20,
            std_ratio=2.0
        )
        
        processed_count = len(pcd.points)
        outlier_ratio = 1.0 - (processed_count / original_count)
        
        logger.info(f"前処理完了: {original_count}点 → {processed_count}点 (外れ値率: {outlier_ratio:.2%})")
        
        return pcd, original_count
    
    def fit_plane(self, points: np.ndarray, distance_threshold: Optional[float] = None, 
                  num_iterations: Optional[int] = None) -> Optional[FitResult]:
        """
        平面フィット（RANSAC + 最小二乗リファイン）
        
        Args:
            points: 入力点群 [N, 3]
            distance_threshold: 距離閾値（デフォルト: self.plane_distance_threshold）
            num_iterations: 反復回数（デフォルト: self.plane_num_iterations）
            
        Returns:
            FitResult または None（失敗時）
        """
        start_time = time.time()
        
        # 前処理
        pcd, original_count = self.preprocess_points(points)
        if pcd is None:
            return None
        
        processed_points = np.asarray(pcd.points)
        if len(processed_points) < 10:
            logger.error("前処理後も点数不足")
            return None
        
        # RANSAC平面フィット
        distance_threshold = distance_threshold or self.plane_distance_threshold
        num_iterations = num_iterations or self.plane_num_iterations
        
        try:
            plane_model, inlier_indices = pcd.segment_plane(
                distance_threshold=distance_threshold,
                ransac_n=self.plane_ransac_n,
                num_iterations=num_iterations
            )
            
            if len(inlier_indices) == 0:
                logger.error("平面フィット: インライアが0点")
                return None
            
            # 平面パラメータ [a, b, c, d] (ax + by + cz + d = 0)
            a, b, c, d = plane_model
            
            # 法線ベクトル（正規化）
            normal = np.array([a, b, c])
            normal_norm = np.linalg.norm(normal)
            if normal_norm < 1e-6:
                logger.error("平面法線がゼロベクトル")
                return None
            normal = normal / normal_norm
            
            # 平面上の代表点（重心に最も近いインライア点）
            inlier_points = processed_points[inlier_indices]
            centroid = np.mean(inlier_points, axis=0)
            
            # 平面上に投影
            t = -(a * centroid[0] + b * centroid[1] + c * centroid[2] + d) / (a*a + b*b + c*c)
            p0 = centroid + t * normal
            
            # 残差RMS計算
            distances = np.abs(
                a * inlier_points[:, 0] + 
                b * inlier_points[:, 1] + 
                c * inlier_points[:, 2] + d
            ) / normal_norm
            residual_rms = np.sqrt(np.mean(distances ** 2))
            
            # インライア比率
            inlier_ratio = len(inlier_indices) / original_count
            
            elapsed_time = (time.time() - start_time) * 1000
            
            logger.info(f"平面フィット完了: インライア率={inlier_ratio:.2%}, RMS={residual_rms:.4f}m, 時間={elapsed_time:.1f}ms")
            
            return FitResult(
                kind='plane',
                direction=normal,
                point=p0,
                inlier_ratio=inlier_ratio,
                residual_rms=residual_rms,
                iters=num_iterations,
                inlier_indices=inlier_indices
            )
            
        except Exception as e:
            logger.error(f"平面フィットエラー: {e}")
            return None
    
    def fit_line(self, points: np.ndarray, distance_threshold: Optional[float] = None,
                 num_iterations: Optional[int] = None) -> Optional[FitResult]:
        """
        直線（軸）フィット（RANSAC）
        
        Args:
            points: 入力点群 [N, 3]
            distance_threshold: 距離閾値（デフォルト: self.line_distance_threshold）
            num_iterations: 反復回数（デフォルト: self.line_num_iterations）
            
        Returns:
            FitResult または None（失敗時）
        """
        start_time = time.time()
        
        # 前処理
        pcd, original_count = self.preprocess_points(points)
        if pcd is None:
            return None
        
        processed_points = np.asarray(pcd.points)
        if len(processed_points) < 10:
            logger.error("前処理後も点数不足")
            return None
        
        # RANSAC直線フィット（Open3Dには直接的なAPIがないため、手動実装）
        distance_threshold = distance_threshold or self.line_distance_threshold
        num_iterations = num_iterations or self.line_num_iterations
        
        best_inlier_indices = None
        best_axis = None
        best_point = None
        max_inliers = 0
        
        try:
            # RANSACループ
            for _ in range(num_iterations):
                # 2点をランダムに選択
                indices = np.random.choice(len(processed_points), size=2, replace=False)
                p1 = processed_points[indices[0]]
                p2 = processed_points[indices[1]]
                
                # 軸方向ベクトル
                axis = p2 - p1
                axis_norm = np.linalg.norm(axis)
                if axis_norm < 1e-6:
                    continue
                axis = axis / axis_norm
                
                # 直線上の代表点（p1）
                line_point = p1
                
                # 全点から直線への距離を計算
                vectors = processed_points - line_point
                distances = np.linalg.norm(
                    vectors - np.outer(np.dot(vectors, axis), axis),
                    axis=1
                )
                
                # インライア判定
                inlier_mask = distances < distance_threshold
                inlier_count = np.sum(inlier_mask)
                
                if inlier_count > max_inliers:
                    max_inliers = inlier_count
                    best_inlier_indices = np.where(inlier_mask)[0]
                    best_axis = axis
                    best_point = line_point
            
            if best_inlier_indices is None or len(best_inlier_indices) == 0:
                logger.error("直線フィット: インライアが0点")
                return None
            
            # インライア点で最小二乗リファイン
            inlier_points = processed_points[best_inlier_indices]
            centroid = np.mean(inlier_points, axis=0)
            
            # 主成分分析で軸方向を精密化
            centered = inlier_points - centroid
            cov = np.cov(centered.T)
            eigenvalues, eigenvectors = np.linalg.eig(cov)
            main_axis_idx = np.argmax(eigenvalues)
            refined_axis = eigenvectors[:, main_axis_idx]
            
            # 方向を統一（正負どちらでも良いが、慣例的にZ軸正方向を優先）
            if refined_axis[2] < 0:
                refined_axis = -refined_axis
            
            # 残差RMS計算
            vectors_refined = inlier_points - centroid
            distances_refined = np.linalg.norm(
                vectors_refined - np.outer(np.dot(vectors_refined, refined_axis), refined_axis),
                axis=1
            )
            residual_rms = np.sqrt(np.mean(distances_refined ** 2))
            
            # インライア比率
            inlier_ratio = len(best_inlier_indices) / original_count
            
            elapsed_time = (time.time() - start_time) * 1000
            
            logger.info(f"直線フィット完了: インライア率={inlier_ratio:.2%}, RMS={residual_rms:.4f}m, 時間={elapsed_time:.1f}ms")
            
            return FitResult(
                kind='line',
                direction=refined_axis,
                point=centroid,
                inlier_ratio=inlier_ratio,
                residual_rms=residual_rms,
                iters=num_iterations,
                inlier_indices=best_inlier_indices
            )
            
        except Exception as e:
            logger.error(f"直線フィットエラー: {e}")
            return None
    
    def align_vector_to_z(self, vec: np.ndarray) -> np.ndarray:
        """
        ベクトルをZ軸(0,0,1)に一致させる回転行列を生成
        
        Args:
            vec: 単位ベクトル
            
        Returns:
            3x3回転行列
        """
        vec = vec / np.linalg.norm(vec)
        z_axis = np.array([0, 0, 1])
        
        # 既にZ軸方向の場合
        if np.allclose(vec, z_axis):
            return np.eye(3)
        if np.allclose(vec, -z_axis):
            # 180度回転
            return np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1]])
        
        # 回転軸（外積）
        rotation_axis = np.cross(vec, z_axis)
        rotation_axis = rotation_axis / np.linalg.norm(rotation_axis)
        
        # 回転角（内積）
        cos_angle = np.dot(vec, z_axis)
        angle = np.arccos(np.clip(cos_angle, -1, 1))
        
        # ロドリゲスの回転公式
        K = np.array([
            [0, -rotation_axis[2], rotation_axis[1]],
            [rotation_axis[2], 0, -rotation_axis[0]],
            [-rotation_axis[1], rotation_axis[0], 0]
        ])
        R = np.eye(3) + np.sin(angle) * K + (1 - cos_angle) * (K @ K)
        
        return R
    
    def compute_pitch_roll(self, vec: np.ndarray, basis: Literal['imu', 'plane'],
                          imu: Optional[Dict] = None, ground_normal: Optional[np.ndarray] = None) -> Tuple[float, float, str]:
        """
        ピッチ・ロール角度計算
        
        Args:
            vec: 対象ベクトル（平面法線または軸方向）
            basis: 基準方式（'imu' または 'plane'）
            imu: IMUデータ {'gravity': [x,y,z], 'attitude': {...}}
            ground_normal: 地面法線（basis='plane'時）
            
        Returns:
            (pitch, roll, basis_used): 角度（度、小数1桁）、使用した基準
        """
        vec = vec / np.linalg.norm(vec)  # 正規化
        
        # 参照ベクトル決定
        if basis == 'imu' and imu and 'gravity' in imu:
            gravity = np.array(imu['gravity'])
            # 重力ベクトルを正規化（上向きを正とするため反転）
            if np.linalg.norm(gravity) > 1e-6:
                reference = -gravity / np.linalg.norm(gravity)
                basis_used = 'imu'
            else:
                # IMUが利用できない場合、フォールバック
                if ground_normal is not None:
                    reference = ground_normal / np.linalg.norm(ground_normal)
                    basis_used = 'plane'
                else:
                    # デフォルト: Z軸上向き
                    reference = np.array([0, 0, 1])
                    basis_used = 'imu_fallback'
                    logger.warning("IMU重力データが無効、デフォルト参照を使用")
        elif basis == 'plane' and ground_normal is not None:
            reference = ground_normal / np.linalg.norm(ground_normal)
            basis_used = 'plane'
        else:
            # フォールバック: Z軸上向き
            reference = np.array([0, 0, 1])
            basis_used = 'default'
            logger.warning("参照ベクトルが取得できず、デフォルト参照を使用")
        
        # 参照ベクトルをZ軸に一致させる回転行列
        R = self.align_vector_to_z(reference)
        
        # 対象ベクトルを回転
        vec_rotated = R @ vec
        
        # ピッチ・ロール計算（atan2使用）
        pitch_rad = np.arctan2(vec_rotated[0], vec_rotated[2])
        roll_rad = np.arctan2(vec_rotated[1], vec_rotated[2])
        
        # 度に変換（小数1桁、四捨五入）
        pitch_deg = np.round(np.degrees(pitch_rad), 1)
        roll_deg = np.round(np.degrees(roll_rad), 1)
        
        return pitch_deg, roll_deg, basis_used
    
    def estimate_angle(self, points: np.ndarray, target_type: Literal['A', 'B', 'C', 'D'],
                      basis: Literal['imu', 'plane'], imu: Optional[Dict] = None,
                      ground_points: Optional[np.ndarray] = None) -> Dict:
        """
        統合入口: 対象タイプに応じて幾何フィットを実行し、角度を計算
        
        Args:
            points: 入力点群 [N, 3]
            target_type: 対象タイプ（'A':ステム軸, 'B':ハンドル面, 'C':フランジ面, 'D':配管軸）
            basis: 基準方式（'imu' または 'plane'）
            imu: IMUデータ
            ground_points: 地面点群（basis='plane'時、オプション）
            
        Returns:
            結果辞書:
            {
                'pitch': float,
                'roll': float,
                'basis_used': str,
                'quality': {
                    'inlier_ratio': float,
                    'residual_rms': float,
                    'quality_score': float
                },
                'processing_time_ms': float,
                'success': bool,
                'error_message': str (失敗時)
            }
        """
        start_time = time.time()
        
        # 点数チェック
        if len(points) < 100:
            return {
                'pitch': 0.0,
                'roll': 0.0,
                'basis_used': basis,
                'quality': {
                    'inlier_ratio': 0.0,
                    'residual_rms': 0.0,
                    'quality_score': 0.0
                },
                'processing_time_ms': 0,
                'success': False,
                'error_message': f'点数不足: {len(points)}点（最小100点必要）'
            }
        
        # 地面法線推定（basis='plane'時、またはフォールバック用）
        ground_normal = None
        if ground_points is not None and len(ground_points) > 10:
            ground_fit = self.fit_plane(ground_points, distance_threshold=0.02, num_iterations=500)
            if ground_fit:
                ground_normal = ground_fit.direction
        
        # 対象タイプに応じたフィット
        fit_result = None
        
        if target_type == 'A' or target_type == 'D':
            # ステム軸・配管軸: 直線フィット
            fit_result = self.fit_line(points)
        elif target_type == 'B' or target_type == 'C':
            # ハンドル面・フランジ面: 平面フィット
            fit_result = self.fit_plane(points)
        else:
            return {
                'pitch': 0.0,
                'roll': 0.0,
                'basis_used': basis,
                'quality': {
                    'inlier_ratio': 0.0,
                    'residual_rms': 0.0,
                    'quality_score': 0.0
                },
                'processing_time_ms': 0,
                'success': False,
                'error_message': f'未知の対象タイプ: {target_type}'
            }
        
        if fit_result is None:
            return {
                'pitch': 0.0,
                'roll': 0.0,
                'basis_used': basis,
                'quality': {
                    'inlier_ratio': 0.0,
                    'residual_rms': 0.0,
                    'quality_score': 0.0
                },
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'success': False,
                'error_message': '幾何フィットに失敗しました'
            }
        
        # 品質チェック
        if fit_result.inlier_ratio < self.min_inlier_ratio:
            return {
                'pitch': 0.0,
                'roll': 0.0,
                'basis_used': basis,
                'quality': {
                    'inlier_ratio': fit_result.inlier_ratio,
                    'residual_rms': fit_result.residual_rms,
                    'quality_score': fit_result.inlier_ratio
                },
                'processing_time_ms': int((time.time() - start_time) * 1000),
                'success': False,
                'error_message': f'品質不足: インライア率={fit_result.inlier_ratio:.2%} < {self.min_inlier_ratio:.2%}'
            }
        
        if fit_result.residual_rms > self.max_residual_rms:
            logger.warning(f'残差RMSが閾値を超えています: {fit_result.residual_rms:.4f}m > {self.max_residual_rms:.4f}m')
        
        # 角度計算
        pitch, roll, basis_used = self.compute_pitch_roll(
            fit_result.direction,
            basis,
            imu,
            ground_normal
        )
        
        # 品質スコア（0.0-1.0）
        quality_score = min(1.0, fit_result.inlier_ratio * (1.0 - fit_result.residual_rms / self.max_residual_rms))
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"角度計算完了: ピッチ={pitch}°, ロール={roll}°, 品質スコア={quality_score:.2f}")
        
        return {
            'pitch': float(pitch),
            'roll': float(roll),
            'basis_used': basis_used,
            'quality': {
                'inlier_ratio': float(fit_result.inlier_ratio),
                'residual_rms': float(fit_result.residual_rms),
                'quality_score': float(quality_score)
            },
            'processing_time_ms': processing_time_ms,
            'success': True,
            'error_message': None
        }

