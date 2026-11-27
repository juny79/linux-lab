"""
End-to-End Automated Test Suite for linux-lab v0.4.0
- 4 Curriculum Tracks & 12 Progressive Scenarios Verification
- Declarative Rule Engine, Track Promotion Badge, and 6 Competency Axes Verification
"""
import json
import sqlite3
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

import server  # noqa: E402


class LinuxLabV040E2ETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        server.init_db()
        # 테스트 일관성을 위해 기존 완료 이력 초기화
        conn = sqlite3.connect(server.DB_PATH)
        conn.execute("DELETE FROM completions")
        conn.execute("UPDATE users SET tier = 'Executive', completed_count = 0 WHERE id = 'demo-user'")
        conn.commit()
        conn.close()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.LinuxLabHandler)
        cls.port = cls.httpd.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        conn = sqlite3.connect(server.DB_PATH)
        conn.execute("DELETE FROM completions")
        conn.execute("UPDATE users SET tier = 'Executive', completed_count = 0 WHERE id = 'demo-user'")
        conn.commit()
        conn.close()

    def _req(self, method: str, path: str, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def _run_terminal_scenario(self, scenario_id: str, commands: list[str], postmortem: str):
        status, sess = self._req("POST", "/api/sessions", {"scenario_id": scenario_id})
        self.assertEqual(status, 201)
        sid = sess["session_id"]
        for cmd in commands:
            st_code, _ = self._req("POST", f"/api/sessions/{sid}/exec", {"command": cmd})
            self.assertEqual(st_code, 200)
        status, ev = self._req("POST", f"/api/sessions/{sid}/evaluate", {"postmortem": postmortem})
        self.assertEqual(status, 200)
        self.assertTrue(ev["passed"], f"Scenario {scenario_id} failed: {ev}")
        return ev

    def test_01_health_curriculum_and_12_scenarios(self):
        status, data = self._req("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["version"], "0.4.0")

        status, sc_data = self._req("GET", "/api/scenarios")
        self.assertEqual(status, 200)
        self.assertEqual(len(sc_data["scenarios"]), 12)

        status, curr = self._req("GET", "/api/curriculum")
        self.assertEqual(status, 200)
        self.assertEqual(len(curr["tracks"]), 4)
        self.assertEqual(len(curr["competency_profile"]), 6)

    def test_02_b2c_tier_access_control(self):
        self._req("POST", "/api/user/tier", {"tier": "Free"})
        # Free 티어는 Junior(Free) 허용, Mid(Pro) 및 C-Level(Executive) 차단
        status_ok, _ = self._req("POST", "/api/sessions", {"scenario_id": "j02-systemd-unit-typo"})
        self.assertEqual(status_ok, 201)

        status_mid, _ = self._req("POST", "/api/sessions", {"scenario_id": "m02-lvm-online-extend"})
        self.assertEqual(status_mid, 403)

        status_exec, _ = self._req("POST", "/api/sessions", {"scenario_id": "c01-region-dr"})
        self.assertEqual(status_exec, 403)

        self._req("POST", "/api/user/tier", {"tier": "Executive"})

    def test_03_junior_track_full_completion_and_promotion(self):
        self._run_terminal_scenario(
            "j01-disk-full",
            ["df -h", "truncate -s 0 /var/log/app-debug.log", "systemctl restart postgresql"],
            "디스크 로그 폭증으로 인한 장애. logrotate 및 모니터링 알람 설정.",
        )
        self._run_terminal_scenario(
            "j02-systemd-unit-typo",
            [
                "journalctl -u payment-api",
                "sed -i 's/paymnt-api/payment-api/g' /etc/systemd/system/payment-api.service",
                "systemctl daemon-reload",
                "systemctl restart payment-api",
            ],
            "systemd ExecStart 오타 수정 및 daemon-reload 후 배포 자동화 적용.",
        )
        self._run_terminal_scenario(
            "j03-permission-firewall",
            ["chmod 755 /var/www/campaign", "ufw allow 443/tcp"],
            "디렉토리 권한 chmod 755 복구 및 ufw 방화벽 443 포트 개방.",
        )

        _, curr = self._req("GET", "/api/curriculum")
        junior_track = curr["tracks"][0]
        self.assertTrue(junior_track["promoted"])
        self.assertIn("🌱 Junior Operator", curr["earned_badges"])

    def test_04_mid_and_senior_progressive_scenarios(self):
        # Mid Step 1~3
        self._run_terminal_scenario(
            "m01-haproxy-failover",
            ["sed -i 's/wrong-health/healthz/g' /etc/haproxy/haproxy.cfg", "systemctl reload haproxy"],
            "haproxy 헬스체크 healthz 경로 수정 및 ci/cd 검증 추가.",
        )
        self._run_terminal_scenario(
            "m02-lvm-online-extend",
            ["vgs", "lvextend -L +20G /dev/vg_data/lv_db", "xfs_growfs /data"],
            "lvm lvextend 및 xfs_growfs 온라인 용량 증설 완료.",
        )
        self._run_terminal_scenario(
            "m03-ansible-sysctl-tuning",
            ["ss -s", "ansible-playbook site-sysctl.yml"],
            "time_wait 포트 고갈 해결을 위해 sysctl tcp_tw_reuse를 ansible로 일괄 배포.",
        )

        # Senior Step 1~3
        self._run_terminal_scenario(
            "s01-oom-killer",
            ["dmesg", "kill -9 9021", "systemctl set-property analytics-batch.service MemoryMax=512M"],
            "oom 메모리 누수 프로세스 종료 및 cgroup MemoryMax 격리.",
        )
        self._run_terminal_scenario(
            "s02-ebpf-io-latency",
            ["biosnoop", "ionice -c 3 -p 7741"],
            "ebpf biosnoop으로 fsync 병목 추적 후 ionice 격리로 p99 지연 해소.",
        )
        self._run_terminal_scenario(
            "s03-incident-forensics",
            ["ss -tunp", "crontab -r", "kill -9 6613", "sed -i 's/PermitRootLogin yes/PermitRootLogin no/g' /etc/ssh/sshd_config"],
            "침해 사고 포렌식으로 crontab 백도어 제거 및 ssh PermitRootLogin 차단.",
        )

        _, curr = self._req("GET", "/api/curriculum")
        self.assertTrue(curr["tracks"][1]["promoted"])
        self.assertTrue(curr["tracks"][2]["promoted"])

    def test_05_clevel_track_full_completion(self):
        clevel_runs = [
            ("c01-region-dr", [(1, "opt_dr_now"), (2, "opt_transparent")]),
            ("c02-ransomware-governance", [(1, "opt_isolate_all"), (2, "opt_report_law")]),
            ("c03-hybrid-finops-sre", [(1, "opt_hybrid_onprem"), (2, "opt_error_budget")]),
        ]
        for sc_id, choices in clevel_runs:
            status, sess = self._req("POST", "/api/sessions", {"scenario_id": sc_id})
            self.assertEqual(status, 201)
            sid = sess["session_id"]
            for stage_id, opt_id in choices:
                st_code, res = self._req("POST", f"/api/sessions/{sid}/decision", {"stage_id": stage_id, "option_id": opt_id})
                self.assertEqual(st_code, 200)
            self.assertTrue(res["completed"])

        _, curr = self._req("GET", "/api/curriculum")
        self.assertEqual(len(curr["earned_badges"]), 4)
        # 12개 시나리오 모두 고득점 완료 시 모든 역량 축이 80% 이상 달성됨을 검증
        for comp in curr["competency_profile"]:
            self.assertGreaterEqual(comp["score"], 80)


if __name__ == "__main__":
    unittest.main(verbosity=2)
