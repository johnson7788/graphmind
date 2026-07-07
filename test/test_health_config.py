"""健康检查与配置接口测试。

覆盖:
    GET  /api/health
    GET  /api/config/status
"""

from __future__ import annotations

import requests


class TestHealth:
    def test_health(self, api):
        r = requests.get(f"{api}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestConfig:
    def test_config_status(self, api):
        r = requests.get(f"{api}/config/status")
        assert r.status_code == 200
        data = r.json()
        assert "configured" in data
        assert "model" in data
