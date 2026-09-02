# -*- coding: utf-8 -*-
"""
预测结果缓存模块
用于缓存贝叶斯推理+逻辑分析的计算结果，避免每次读取都重新计算
"""

import time
from typing import Dict, Any, Optional

# 全局缓存字典: {game_id: {"data": predictions, "timestamp": float}}
_cache: Dict[int, Dict[str, Any]] = {}

# 缓存有效期（秒），默认5分钟，即使没有行为变化也会定期刷新
CACHE_TTL = 300


def get_cached_predictions(game_id: int) -> Optional[Dict[str, Any]]:
    """
    获取缓存的预测结果
    
    Args:
        game_id: 对局ID
        
    Returns:
        缓存的预测结果，如果缓存不存在或已过期则返回None
    """
    cache_entry = _cache.get(game_id)
    if not cache_entry:
        return None
    
    # 检查缓存是否过期
    if time.time() - cache_entry["timestamp"] > CACHE_TTL:
        # 缓存过期，删除并返回None
        del _cache[game_id]
        return None
    
    return cache_entry["data"]


def set_cached_predictions(game_id: int, predictions: Dict[str, Any]) -> None:
    """
    设置缓存的预测结果
    
    Args:
        game_id: 对局ID
        predictions: 预测结果数据
    """
    _cache[game_id] = {
        "data": predictions,
        "timestamp": time.time()
    }


def invalidate_cache(game_id: int) -> None:
    """
    使某个对局的预测缓存失效（在行为记录增删改时调用）
    
    Args:
        game_id: 对局ID
    """
    if game_id in _cache:
        del _cache[game_id]


def clear_all_cache() -> None:
    """清除所有缓存（系统重启或维护时使用）"""
    _cache.clear()


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息（用于调试）"""
    return {
        "cached_games": len(_cache),
        "game_ids": list(_cache.keys()),
        "cache_ttl": CACHE_TTL
    }
