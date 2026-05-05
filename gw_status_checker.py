# -*- coding: utf-8 -*-
"""
GWStatusChecker — 獨立模組，用於查詢 NextDrive Gateway 及關聯設備的上下線狀態。

使用方式：
    checker = GWStatusChecker(token="your_jwt_token")
    
    # 單一 PID 檢查（含 Device）
    result = checker.check_pid("AAF0808E9F65CE7DA")
    print(result.status_color)   # 'blue' / 'red' / 'yellow' / 'orange'
    print(result.gw_online)      # True / False
    
    # 批量檢查（多個 PID）
    results = checker.check_pids(["PID1", "PID2", "PID3"])
"""

import requests
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DeviceStatus:
    """單一設備的狀態"""
    device_id: str
    name: str
    online_status: int          # 0=離線, 1=在線, 5=未知/特殊狀態
    is_online: bool             # True = 正常在線

    @staticmethod
    def from_api(data: dict) -> 'DeviceStatus':
        os_val = data.get('onlineStatus', -1)
        return DeviceStatus(
            device_id=data.get('id', data.get('uuid', '')),
            name=data.get('name', data.get('deviceName', '')),
            online_status=os_val,
            is_online=(os_val == 1),
        )


@dataclass
class GWCheckResult:
    """單一 PID 的完整檢查結果"""
    pid: str
    gw_uuid: Optional[str] = None
    gw_name: str = ''
    gw_online_status: int = -1          # API 回傳的 onlineStatus
    gw_online: bool = False             # True = GW 在線 (onlineStatus == 1)
    devices: List[DeviceStatus] = field(default_factory=list)
    any_device_offline: bool = False
    error: Optional[str] = None         # 若有錯誤，記錄原因

    @property
    def status_color(self) -> str:
        """
        回傳狀態顏色（與前端 checkSpotStatus 邏輯一致）：
            orange — API 查詢失敗 / 錯誤
            red    — GW 離線 (onlineStatus == 0)
            yellow — GW 在線但任一 Device 離線
            blue   — 全部正常
        """
        if self.error:
            return 'orange'
        if not self.gw_online:
            return 'red'
        if self.any_device_offline:
            return 'yellow'
        return 'blue'

    def to_dict(self) -> dict:
        return {
            'pid': self.pid,
            'gw_uuid': self.gw_uuid,
            'gw_name': self.gw_name,
            'gw_online_status': self.gw_online_status,
            'gw_online': self.gw_online,
            'devices': [d.__dict__ for d in self.devices],
            'any_device_offline': self.any_device_offline,
            'status_color': self.status_color,
            'error': self.error,
        }


class GWStatusChecker:
    """
    NextDrive Gateway 狀態檢查器。

    Args:
        token: JWT access token（從 Cognito 取得）
        base_url: NextDrive API 基底 URL
        timeout: 每個 API 呼叫的超時秒數
    """

    BASE_URL = "https://ndp-api.nextdrive.io/v1"

    def __init__(self, token: str, base_url: Optional[str] = None, timeout: int = 5):
        self.token = token
        self.base_url = (base_url or self.BASE_URL).rstrip('/')
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def check_pid(self, pid: str, include_devices: bool = True) -> GWCheckResult:
        """
        檢查單一 PID 的 GW 狀態，可選是否同時檢查關聯 Device。

        Args:
            pid: Gateway 的 Product ID（如 "AAF0808E9F65CE7DA"）
            include_devices: 若 True 且 GW 在線，會進一步查詢所有 Device 狀態

        Returns:
            GWCheckResult — 包含 GW 和 Device 的完整狀態
        """
        result = GWCheckResult(pid=pid)

        # Step 1: 查詢 GW 狀態
        gw_data = self._fetch_gw_status(pid)
        if not gw_data:
            result.error = f"GW API returned no data for PID={pid}"
            return result

        gw_info = gw_data[0]
        os_val = gw_info.get('onlineStatus', -1)

        result.gw_uuid = gw_info.get('uuid')
        result.gw_name = gw_info.get('name', '')
        result.gw_online_status = os_val
        result.gw_online = (os_val == 1)

        # Step 2: 若 GW 在線，檢查 Device
        if include_devices and result.gw_online and result.gw_uuid:
            devices = self._fetch_gw_devices(result.gw_uuid)
            for d in devices:
                ds = DeviceStatus.from_api(d)
                result.devices.append(ds)
                if not ds.is_online:
                    result.any_device_offline = True

        return result

    def check_pids(self, pids: List[str], include_devices: bool = True) -> List[GWCheckResult]:
        """批量檢查多個 PID，回傳所有結果。"""
        return [self.check_pid(pid, include_devices) for pid in pids]

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _fetch_gw_status(self, pid: str) -> Optional[list]:
        """呼叫 NextDrive API 取得 GW 狀態，回傳 data list 或 None。"""
        url = f"{self.base_url}/gateways"
        params = {'uuids': pid, 'type': 'product_id'}

        try:
            r = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
            r.raise_for_status()
            data = r.json().get('data', [])
            return data if data else None
        except requests.exceptions.Timeout:
            raise RuntimeError(f"GW API timed out for PID={pid}")
        except requests.exceptions.HTTPError as e:
            try:
                detail = r.json()
            except Exception:
                detail = r.text[:200]
            raise RuntimeError(f"GW API HTTP {r.status_code}: {detail}") from e
        except Exception as e:
            raise RuntimeError(f"GW API error for PID={pid}: {e}")

    def _fetch_gw_devices(self, gw_uuid: str) -> list:
        """呼叫 NextDrive API 取得 GW 下所有 Device，回傳 data list。"""
        url = f"{self.base_url}/gateways/{gw_uuid}/devices"

        try:
            r = requests.get(url, headers=self.headers, timeout=self.timeout)
            if r.status_code != 200:
                return []
            return r.json().get('data', [])
        except Exception as e:
            print(f"[GWStatusChecker] Device fetch error for UUID={gw_uuid}: {e}")
            return []
