"""
linux-lab Backend API Server (v0.4.0 - Python 3.13 Standard Library)
- 레벨별 표준 커리큘럼(Junior ~ C-Level), 선수 과목(Prerequisites), 승급 배지 및 6대 역량 산출 API
- 선언적 Scenario-as-Code 로더, 터미널 세션 실행, 자동 채점, C레벨 의사결정 시뮬레이터 API
"""
import json
import os
import sqlite3
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Any, List
from urllib.parse import urlparse

from evaluator import evaluate_terminal_session, get_ai_mentor_hint
from provisioner import LocalSimShellProvisioner

ROOT_DIR = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = ROOT_DIR / "scenarios"
CURRICULUM_PATH = ROOT_DIR / "curriculum" / "curriculum.json"
FRONTEND_DIR = ROOT_DIR / "frontend"
DB_PATH = ROOT_DIR / "backend" / "linux_lab.db"

TIER_RANK = {"Free": 0, "Pro": 1, "Executive": 2}
LEVEL_ORDER = {"Junior": 1, "Mid-level": 2, "Senior": 3, "C-Level": 4}

PROVISIONER = LocalSimShellProvisioner()
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tier TEXT NOT NULL DEFAULT 'Pro',
            streak_days INTEGER NOT NULL DEFAULT 3,
            completed_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS completions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            scenario_id TEXT NOT NULL,
            score INTEGER NOT NULL,
            mttr_seconds INTEGER NOT NULL,
            completed_at REAL NOT NULL
        )
        """
    )
    cur.execute(
        "INSERT OR IGNORE INTO users (id, name, tier, streak_days, completed_count) VALUES (?, ?, ?, ?, ?)",
        ("demo-user", "홍길동 (Linux Engineer)", "Executive", 5, 0),
    )
    conn.commit()
    conn.close()


def load_scenarios() -> Dict[str, Dict[str, Any]]:
    scenarios: Dict[str, Dict[str, Any]] = {}
    for path in sorted(SCENARIOS_DIR.glob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            scenarios[data["id"]] = data
    return dict(
        sorted(
            scenarios.items(),
            key=lambda item: (LEVEL_ORDER.get(item[1].get("level", ""), 99), item[1].get("step", 1)),
        )
    )


def load_curriculum() -> Dict[str, Any]:
    with open(CURRICULUM_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_best_scores(user_id: str = "demo-user") -> Dict[str, int]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT scenario_id, MAX(score) as best_score FROM completions WHERE user_id = ? GROUP BY scenario_id",
        (user_id,),
    ).fetchall()
    conn.close()
    return {r[0]: int(r[1]) for r in rows}


def get_user(user_id: str = "demo-user") -> Dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    completions = conn.execute(
        "SELECT scenario_id, score, mttr_seconds FROM completions WHERE user_id = ? ORDER BY completed_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    best_scores = get_best_scores(user_id)
    user = dict(row) if row else {"id": user_id, "name": "Guest", "tier": "Free", "streak_days": 0, "completed_count": 0}
    user["completed_count"] = len(best_scores)
    user["best_scores"] = best_scores
    user["completions"] = [dict(c) for c in completions]
    return user


def build_curriculum_progress(user_id: str = "demo-user") -> Dict[str, Any]:
    curriculum = load_curriculum()
    scenarios = load_scenarios()
    best_scores = get_best_scores(user_id)

    # 6대 역량 누적 점수 계산 (각 역량 최대치 대비 달성 비율 0~100)
    axis_earned: Dict[str, float] = {ax["key"]: 0.0 for ax in curriculum["competency_axes"]}
    axis_max: Dict[str, float] = {ax["key"]: 0.0 for ax in curriculum["competency_axes"]}

    for sid, sc in scenarios.items():
        for k, weight in sc.get("skill_weights", {}).items():
            if k in axis_max:
                axis_max[k] += weight
                if sid in best_scores:
                    axis_earned[k] += weight * (best_scores[sid] / 100.0)

    competency_profile = []
    for ax in curriculum["competency_axes"]:
        k = ax["key"]
        pct = int(round((axis_earned[k] / axis_max[k]) * 100)) if axis_max[k] > 0 else 0
        competency_profile.append({"key": k, "label": ax["label"], "score": pct})

    enriched_tracks: List[Dict[str, Any]] = []
    earned_badges: List[str] = []

    for track in curriculum["tracks"]:
        req_ids = track["promotion_criteria"]["required_scenarios"]
        min_avg = track["promotion_criteria"]["min_avg_score"]

        done_scores = [best_scores[sid] for sid in req_ids if sid in best_scores]
        avg_score = int(sum(done_scores) / len(done_scores)) if done_scores else 0
        all_done = len(done_scores) == len(req_ids)
        promoted = all_done and avg_score >= min_avg
        if promoted:
            earned_badges.append(track["badge"])

        enriched_modules = []
        for mod in track["modules"]:
            sid = mod["scenario_id"]
            sc = scenarios.get(sid, {})
            prereqs = sc.get("prerequisites", [])
            prereqs_met = all(p in best_scores for p in prereqs)
            enriched_modules.append(
                {
                    **mod,
                    "scenario": sc,
                    "completed": sid in best_scores,
                    "best_score": best_scores.get(sid),
                    "prerequisites": prereqs,
                    "prerequisites_met": prereqs_met,
                }
            )

        enriched_tracks.append(
            {
                **track,
                "completed_steps": len(done_scores),
                "total_steps": len(req_ids),
                "avg_score": avg_score,
                "promoted": promoted,
                "modules": enriched_modules,
            }
        )

    return {
        "version": curriculum["version"],
        "title": curriculum["title"],
        "competency_profile": competency_profile,
        "earned_badges": earned_badges,
        "tracks": enriched_tracks,
    }


def record_completion(user_id: str, scenario_id: str, score: int, mttr_seconds: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO completions (id, user_id, scenario_id, score, mttr_seconds, completed_at) VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), user_id, scenario_id, score, mttr_seconds, time.time()),
    )
    distinct_cnt = conn.execute(
        "SELECT COUNT(DISTINCT scenario_id) FROM completions WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.execute("UPDATE users SET completed_count = ? WHERE id = ?", (distinct_cnt, user_id))
    conn.commit()
    conn.close()


class LinuxLabHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _serve_static(self, rel_path: str) -> None:
        if rel_path in ("", "/"):
            rel_path = "index.html"
        file_path = (FRONTEND_DIR / rel_path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(FRONTEND_DIR.resolve())) or not file_path.is_file():
            self._send_json(404, {"error": "Not Found"})
            return
        ext = file_path.suffix.lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
        }.get(ext, "application/octet-stream")
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            self._send_json(200, {"status": "ok", "service": "linux-lab-api", "version": "0.4.0"})
            return

        if path == "/api/user":
            self._send_json(200, get_user())
            return

        if path == "/api/scenarios":
            scenarios = load_scenarios()
            self._send_json(200, {"scenarios": list(scenarios.values())})
            return

        if path == "/api/curriculum":
            self._send_json(200, build_curriculum_progress())
            return

        self._serve_static(path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json()

        if path == "/api/user/tier":
            tier = body.get("tier", "Free")
            if tier not in TIER_RANK:
                self._send_json(400, {"error": "Invalid tier"})
                return
            conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE users SET tier = ? WHERE id = ?", (tier, "demo-user"))
            conn.commit()
            conn.close()
            self._send_json(200, get_user())
            return

        if path == "/api/sessions":
            scenario_id = body.get("scenario_id")
            scenarios = load_scenarios()
            if scenario_id not in scenarios:
                self._send_json(404, {"error": "Scenario not found"})
                return
            scenario = scenarios[scenario_id]
            user = get_user()
            if TIER_RANK.get(user["tier"], 0) < TIER_RANK.get(scenario["required_tier"], 0):
                self._send_json(403, {"error": f"Requires {scenario['required_tier']} tier subscription."})
                return

            session_id = str(uuid.uuid4())[:8]
            lab_state = PROVISIONER.allocate(session_id, scenario)
            ACTIVE_SESSIONS[session_id] = {
                "session_id": session_id,
                "scenario": scenario,
                "lab_state": lab_state,
                "started_at": time.time(),
                "hint_index": 0,
                "kpis": dict(scenario.get("initial_kpis", {})),
            }
            self._send_json(201, {"session_id": session_id, "scenario": scenario, "metrics": lab_state["metrics"]})
            return

        if path.startswith("/api/sessions/") and path.endswith("/exec"):
            session_id = path.split("/")[3]
            sess = ACTIVE_SESSIONS.get(session_id)
            if not sess:
                self._send_json(404, {"error": "Session not found"})
                return
            cmd = body.get("command", "")
            output, new_state = PROVISIONER.execute_command(sess["lab_state"], cmd)
            sess["lab_state"] = new_state
            self._send_json(200, {"output": output, "metrics": new_state["metrics"]})
            return

        if path.startswith("/api/sessions/") and path.endswith("/hint"):
            session_id = path.split("/")[3]
            sess = ACTIVE_SESSIONS.get(session_id)
            if not sess:
                self._send_json(404, {"error": "Session not found"})
                return
            res = get_ai_mentor_hint(sess["scenario"], sess["hint_index"])
            sess["hint_index"] = res["next_index"]
            self._send_json(200, res)
            return

        if path.startswith("/api/sessions/") and path.endswith("/evaluate"):
            session_id = path.split("/")[3]
            sess = ACTIVE_SESSIONS.get(session_id)
            if not sess:
                self._send_json(404, {"error": "Session not found"})
                return
            postmortem = body.get("postmortem", "")
            result = evaluate_terminal_session(sess["scenario"], sess["lab_state"], sess["started_at"], postmortem)
            if result["passed"]:
                record_completion("demo-user", sess["scenario"]["id"], result["total_score"], result["mttr_seconds"])
            self._send_json(200, result)
            return

        if path.startswith("/api/sessions/") and path.endswith("/decision"):
            session_id = path.split("/")[3]
            sess = ACTIVE_SESSIONS.get(session_id)
            if not sess:
                self._send_json(404, {"error": "Session not found"})
                return
            stage_id = body.get("stage_id")
            option_id = body.get("option_id")
            stages = sess["scenario"].get("stages", [])
            stage = next((s for s in stages if s["stage_id"] == stage_id), None)
            if not stage:
                self._send_json(400, {"error": "Invalid stage"})
                return
            option = next((o for o in stage["options"] if o["id"] == option_id), None)
            if not option:
                self._send_json(400, {"error": "Invalid option"})
                return
            for k, delta in option["impact"].items():
                sess["kpis"][k] = max(0, min(100, sess["kpis"].get(k, 50) + delta))
            is_last = stage_id == stages[-1]["stage_id"]
            if is_last:
                avg_score = int(sum(sess["kpis"].values()) / max(1, len(sess["kpis"])))
                record_completion("demo-user", sess["scenario"]["id"], avg_score, int(time.time() - sess["started_at"]))
            self._send_json(200, {"kpis": sess["kpis"], "feedback": option["feedback"], "completed": is_last})
            return

        self._send_json(404, {"error": "Endpoint not found"})


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    init_db()
    server = ThreadingHTTPServer((host, port), LinuxLabHandler)
    print(f"[linux-lab] Server running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server(os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", "8080")))
