# -*- coding: utf-8 -*-
"""
GWDeviceLister — 根據 PID 查詢關聯的所有設備名稱及 ID。

使用方式：
    from gw_device_lister import GWDeviceLister

    lister = GWDeviceLister(token="your_jwt_token")

    # 單一 PID
    devices = lister.list_devices("AAF0808E9F65CE7DA")
    for d in devices:
        print(f"  {d.device_id} — {d.name}")

    # 批量查詢多個 PID
    all_results = lister.list_devices_batch(["PID1", "PID2"])
"""

import requests
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DeviceInfo:
    """單一設備資訊"""
    device_id: str
    name: str
    online_status: int = -1       # 0=離線, 1=在線, 5=特殊狀態

    @staticmethod
    def from_api(data: dict) -> 'DeviceInfo':
        return DeviceInfo(
            device_id=data.get('id', data.get('uuid', '')),
            name=data.get('name', data.get('deviceName', '')),
            online_status=data.get('onlineStatus', -1),
        )


@dataclass
class PIDDeviceResult:
    """單一 PID 的設備查詢結果"""
    pid: str
    gw_uuid: Optional[str] = None
    gw_name: str = ''
    devices: List[DeviceInfo] = None

    def __post_init__(self):
        if self.devices is None:
            self.devices = []

    @property
    def device_count(self) -> int:
        return len(self.devices)

    def to_dict(self) -> dict:
        return {
            'pid': self.pid,
            'gw_uuid': self.gw_uuid,
            'gw_name': self.gw_name,
            'device_count': self.device_count,
            'devices': [d.__dict__ for d in self.devices],
        }


class GWDeviceLister:
    """
    根據 PID 查詢關聯設備列表。

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

    def list_devices(self, pid: str) -> PIDDeviceResult:
        """
        查詢單一 PID 下關聯的所有設備。

        Args:
            pid: Gateway 的 Product ID（如 "AAF0808E9F65CE7DA"）

        Returns:
            PIDDeviceResult — 包含 GW UUID、名稱及所有設備列表
        """
        result = PIDDeviceResult(pid=pid)

        # Step 1: 由 PID 取得 GW UUID
        gw_uuid, gw_name = self._resolve_pid_to_uuid(pid)
        if not gw_uuid:
            return result

        result.gw_uuid = gw_uuid
        result.gw_name = gw_name or ''

        # Step 2: 用 UUID 查詢設備列表
        devices = self._fetch_devices(gw_uuid)
        for d in devices:
            result.devices.append(DeviceInfo.from_api(d))

        return result

    def list_devices_batch(self, pids: List[str]) -> List[PIDDeviceResult]:
        """批量查詢多個 PID 的設備列表。"""
        return [self.list_devices(pid) for pid in pids]

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _resolve_pid_to_uuid(self, pid: str) -> tuple:
        """
        由 PID 查詢 GW UUID 和名稱。

        Returns:
            (uuid, name) — uuid 可能為 None
        """
        url = f"{self.base_url}/gateways"
        params = {'uuids': pid, 'type': 'product_id'}

        try:
            r = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
            if r.status_code != 200:
                return (None, None)

            data = r.json().get('data', [])
            if not data:
                return (None, None)

            gw = data[0]
            return (gw.get('uuid'), gw.get('name'))
        except Exception as e:
            print(f"[GWDeviceLister] PID→UUID error for {pid}: {e}")
            return (None, None)

    def _fetch_devices(self, gw_uuid: str) -> list:
        """由 GW UUID 取得設備列表。"""
        url = f"{self.base_url}/gateways/{gw_uuid}/devices"

        try:
            r = requests.get(url, headers=self.headers, timeout=self.timeout)
            if r.status_code != 200:
                return []
            return r.json().get('data', [])
        except Exception as e:
            print(f"[GWDeviceLister] Device fetch error for UUID={gw_uuid}: {e}")
            return []
