"""
Lab Provisioner Layer (v0.4.0)
- OnPremFirecrackerProvisioner: 온프레미스 리눅스 KVM + Firecracker MicroVM 제어 어댑터
- LocalSimShellProvisioner: 시나리오의 선언적 command_rules를 해석하는 범용 상태 전이 쉘 엔진
"""
import copy
import subprocess
from typing import Dict, Any, Tuple, List


class BaseProvisioner:
    def allocate(self, session_id: str, scenario: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def execute_command(self, session_state: Dict[str, Any], command: str) -> Tuple[str, Dict[str, Any]]:
        raise NotImplementedError

    def destroy(self, session_id: str) -> None:
        raise NotImplementedError


class OnPremFirecrackerProvisioner(BaseProvisioner):
    """온프레미스 베어메탈(KVM + Firecracker) 환경용 프로비저너."""

    def __init__(self, launcher_script: str = "/opt/linux-lab/infra/onprem/firecracker-launcher.sh"):
        self.launcher_script = launcher_script

    def allocate(self, session_id: str, scenario: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "provider": "onprem-firecracker",
            "session_id": session_id,
            "scenario_id": scenario["id"],
            "state": copy.deepcopy(scenario.get("initial_state", {})),
            "metrics": copy.deepcopy(scenario.get("metrics", {"cpu": 10, "memory": 20, "disk": 30})),
            "command_rules": scenario.get("command_rules", []),
        }

    def execute_command(self, session_state: Dict[str, Any], command: str) -> Tuple[str, Dict[str, Any]]:
        raise NotImplementedError("On-Prem Firecracker execution requires KVM host environment.")

    def destroy(self, session_id: str) -> None:
        subprocess.run([self.launcher_script, "destroy", session_id], check=False)


class LocalSimShellProvisioner(BaseProvisioner):
    """Scenario-as-Code의 선언적 command_rules를 평가하여 동작하는 범용 리눅스 쉘 시뮬레이터."""

    def allocate(self, session_id: str, scenario: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "provider": "local-sim-shell",
            "session_id": session_id,
            "scenario_id": scenario["id"],
            "state": copy.deepcopy(scenario.get("initial_state", {})),
            "metrics": copy.deepcopy(scenario.get("metrics", {"cpu": 10, "memory": 20, "disk": 30})),
            "command_rules": copy.deepcopy(scenario.get("command_rules", [])),
            "command_history": [],
        }

    @staticmethod
    def _matches_rule(cmd: str, rule: Dict[str, Any], current_state: Dict[str, Any]) -> bool:
        match_all: List[str] = rule.get("match_all", [])
        if match_all and not all(token in cmd for token in match_all):
            return False

        match_any: List[str] = rule.get("match_any", [])
        if match_any and not any(token in cmd for token in match_any):
            return False

        if not match_all and not match_any:
            return False

        req_state: Dict[str, Any] = rule.get("require_state", {})
        for key, expected in req_state.items():
            if current_state.get(key) != expected:
                return False

        return True

    def execute_command(self, session_state: Dict[str, Any], command: str) -> Tuple[str, Dict[str, Any]]:
        cmd = command.strip()
        if not cmd:
            return "", session_state

        session_state.setdefault("command_history", []).append(cmd)
        current_state = session_state["state"]
        metrics = session_state["metrics"]
        rules: List[Dict[str, Any]] = session_state.get("command_rules", [])

        if cmd in ("help", "?"):
            sample_tokens = []
            for r in rules:
                sample_tokens.extend(r.get("match_all", [])[:1])
                sample_tokens.extend(r.get("match_any", [])[:1])
            uniq = list(dict.fromkeys(sample_tokens))
            return (
                f"이 시나리오 주요 명령어 힌트: {', '.join(uniq) if uniq else 'ls, ps, systemctl'}\n"
                "막힐 경우 좌측 '# incident-alerts' 패널의 [AI 동료 힌트] 버튼을 활용하세요.",
                session_state,
            )

        for rule in rules:
            if self._matches_rule(cmd, rule, current_state):
                for k, v in rule.get("set_state", {}).items():
                    current_state[k] = v
                for mk, mv in rule.get("set_metrics", {}).items():
                    metrics[mk] = mv
                return rule.get("output", "OK"), session_state

        return f"bash: executed '{cmd}' (no target state transition)", session_state

    def destroy(self, session_id: str) -> None:
        return None
