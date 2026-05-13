# -*- coding: utf-8 -*-
"""
GW Monitor — 後端主動檢查案場 GW 狀態，透過 SSE 推送給前端。

流程：
  1. Scheduler 每 30 分鐘全量檢查（保底）
  2. 前端偵測 map bounds → POST /gw_status_refresh 帶入 visible_spot_ids
  3. 後端只查這些 spot，結果寫 Redis cache + SSE 推送給所有連線中的前端
"""

import json
import time
import redis
from datetime import datetime
from flask import current_app, request
from flask_sse import sse
from .. import db, scheduler


def get_redis_client():
    """取得 Redis client，若失敗則回傳 None（不影響功能）"""
    try:
        host = current_app.config.get('REDIS_HOST', 'teaasia-redis')
        port = 6379
        r = redis.Redis(host=host, port=port, db=0, decode_responses=True)
        r.ping()
        return r
    except Exception as e:
        current_app.logger.warning(f"[GWMonitor] Redis unavailable: {e}")
        return None


def _do_check(spot_ids=None):
    """
    核心檢查邏輯。

    Args:
        spot_ids: list of int — 要檢查的 Spot IDs；若為 None 則檢查全部

    Returns:
        list[dict] — 所有检查结果
    """
    from gw_status_checker import GWStatusChecker
    from ..models import Spot
    from .views import get_jwt_token

    token = get_jwt_token()
    if not token:
        current_app.logger.error("[GWMonitor] 無法取得 JWT token，跳過檢查")
        return []

    checker = GWStatusChecker(token=token, max_workers=10)
    r = get_redis_client()

    # 決定要查哪些 Spot
    if spot_ids:
        spots = Spot.query.filter(Spot.id.in_(spot_ids)).all()
    else:
        spots = Spot.query.filter(Spot.gw_list.isnot(None)).all()

    if not spots:
        current_app.logger.info("[GWMonitor] 沒有 Spot，跳過")
        return []

    all_results = []
    start_time = time.time()

    for spot in spots:
        raw = spot.gw_list
        if isinstance(raw, list):
            pids = [p.strip() for p in raw if p and p.strip()]
        elif raw:
            pids = [p.strip() for p in str(raw).split(',') if p.strip()]
        else:
            pids = []

        if not pids:
            continue

        # 平行檢查這個 Spot 的所有 GW（ThreadPoolExecutor）
        spot_results_raw = checker.check_pids(pids, include_devices=True, parallel=True)
        spot_results = [r.to_dict() for r in spot_results_raw]

        # 取最嚴重的顏色 (orange > red > yellow > blue)
        worst_color = 'blue'
        color_priority = {'orange': 0, 'red': 1, 'yellow': 2, 'blue': 3}
        for sr in spot_results:
            c = sr.get('status_color', 'blue')
            if color_priority.get(c, 3) < color_priority.get(worst_color, 3):
                worst_color = c

        # 記錄有錯誤的 PID（平行化後錯誤已包在 result 中）
        for sr in spot_results:
            if sr.get('error'):
                current_app.logger.warning(
                    f"[GWMonitor] Spot={spot.id} PID={sr['pid']} 檢查異常: {sr['error']}"
                )

        # 組裝這個 Spot 的完整結果
        spot_data = {
            'spot_id': spot.id,
            'site_name': spot.site_name or f'案場 {spot.id}',
            'gw_count': len(pids),
            'device_count': sum(
                len(d.get('devices', [])) for d in spot_results if isinstance(d, dict)
            ),
            'status_color': worst_color,
            'checked_at': datetime.utcnow().isoformat(),
            'gateways': spot_results,
        }

        all_results.append(spot_data)

        # 存入 Redis cache (TTL: 10 分鐘，比檢查間隔長一點)
        if r:
            try:
                r.setex(
                    f"gw_status:{spot.id}",
                    600,  # 10 minutes TTL
                    json.dumps(spot_data),
                )
            except Exception as e:
                current_app.logger.error(f"[GWMonitor] Redis write error: {e}")

    elapsed = time.time() - start_time

    # 透過 SSE 推送給所有連線中的前端（輕量版：只推 spot_id + status_color）
    try:
        sse.publish({
            'type': 'gw_status_update',
            'timestamp': datetime.utcnow().isoformat(),
            'elapsed_seconds': round(elapsed, 1),
            'spot_count': len(all_results),
            'spots': all_results,
        }, type='gw_monitor')
        # 輕量版：只推顏色，前端用來更新卡片上的小圓點
        sse.publish({
            'type': 'gw_status_light',
            'updates': [
                {'spot_id': sr['spot_id'], 'status_color': sr['status_color']}
                for sr in all_results
            ],
        }, type='gw_monitor')
    except Exception as e:
        current_app.logger.warning(f"[GWMonitor] SSE publish failed (non-fatal): {e}")

    current_app.logger.info(
        f"[GWMonitor] 完成檢查 {len(all_results)} 個案場"
        f"{f'(spot_ids={spot_ids})' if spot_ids else '(全量)'}, "
        f"耗時 {elapsed:.1f}s"
    )

    return all_results


def check_all_spots():
    """Scheduler job wrapper — 檢查前端回報的 visible spots（無心跳則全量）"""
    # Scheduler 在 app_context 外執行，需要手動進入
    app = scheduler.app
    with app.app_context():
        # 讀取前端心跳回報的 visible spot IDs
        r = get_redis_client()
        spot_ids = None
        if r:
            try:
                data = r.get('gw_monitor:visible_spot_ids')
                if data:
                    spot_ids = json.loads(data)
                    current_app.logger.info(
                        f"[GWMonitor] Scheduler 使用心跳 visible spots: {len(spot_ids)}"
                    )
                else:
                    current_app.logger.info("[GWMonitor] Scheduler 無心跳資料，全量檢查")
            except Exception as e:
                current_app.logger.warning(f"[GWMonitor] Redis heartbeat read error: {e}")

        _do_check(spot_ids=spot_ids)


def get_cached_status(spot_id):
    """從 Redis cache 取得指定 Spot 的 GW 狀態。"""
    r = get_redis_client()
    if not r:
        return None

    try:
        data = r.get(f"gw_status:{spot_id}")
        if data:
            return json.loads(data)
    except Exception as e:
        current_app.logger.error(f"[GWMonitor] Redis read error for spot {spot_id}: {e}")
    return None


def get_all_cached_status():
    """從 Redis cache 取得所有 Spot 的 GW 狀態。"""
    r = get_redis_client()
    if not r:
        return []

    try:
        from ..models import Spot
        spots = Spot.query.filter(Spot.gw_list.isnot(None)).all()

        results = []
        for spot in spots:
            data = get_cached_status(spot.id)
            if data:
                results.append(data)
        return results
    except Exception as e:
        current_app.logger.error(f"[GWMonitor] Redis read all error: {e}")
        return []
