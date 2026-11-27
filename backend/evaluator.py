"""
Evaluation & AI Mentor Engine (v0.4.0)
- 선언적 state_checks 기반 상태 검증 (60점)
- 과정 기반 효율성 및 MTTR 분석 (20점)
- 포스트모템 키워드 및 재발 방지 품질 평가 (20점)
"""
import time
from typing import Dict, Any, List


def evaluate_terminal_session(
    scenario: Dict[str, Any],
    session_state: Dict[str, Any],
    started_at: float,
    postmortem: str,
) -> Dict[str, Any]:
    st = session_state.get("state", {})
    history: List[str] = session_state.get("command_history", [])
    mttr_sec = max(1, int(time.time() - started_at))

    # 1. 선언적 state_checks 기반 상태 검증 (60점)
    checks = scenario.get("state_checks", [])
    state_details = []
    for chk in checks:
        passed = st.get(chk["key"]) == chk["expected"]
        state_details.append({"check": chk["description"], "passed": passed})

    state_passed = bool(state_details) and all(d["passed"] for d in state_details)
    passed_count = sum(1 for d in state_details if d["passed"])
    state_score = int((passed_count / max(1, len(state_details))) * 60)

    # 2. 과정 기반 효율성 (20점)
    cmd_count = len(history)
    if cmd_count == 0:
        efficiency_score = 0
    elif cmd_count <= 8:
        efficiency_score = 20
    elif cmd_count <= 15:
        efficiency_score = 14
    else:
        efficiency_score = 8

    # 3. 포스트모템 품질 평가 (20점)
    pm_lower = (postmortem or "").lower()
    keywords = scenario.get("postmortem_keywords", [])
    matched = [kw for kw in keywords if kw.lower() in pm_lower]
    if not pm_lower.strip():
        pm_score = 0
        pm_feedback = "포스트모템이 작성되지 않았습니다. 근본 원인과 재발 방지 대책을 기록해 보세요."
    else:
        ratio = min(1.0, len(matched) / max(1, min(3, len(keywords))))
        pm_score = int(10 + ratio * 10)
        pm_feedback = (
            f"핵심 키워드({', '.join(matched) if matched else '없음'})가 반영되었습니다. "
            "모니터링 임계치 및 재발 방지 자동화 방안을 함께 명시하면 실무 완성도가 더욱 높아집니다."
        )

    total_score = state_score + efficiency_score + pm_score
    return {
        "passed": state_passed,
        "total_score": total_score,
        "breakdown": {
            "state_score": state_score,
            "efficiency_score": efficiency_score,
            "postmortem_score": pm_score,
        },
        "mttr_seconds": mttr_sec,
        "command_count": cmd_count,
        "state_details": state_details,
        "ai_review": pm_feedback,
    }


def get_ai_mentor_hint(scenario: Dict[str, Any], hint_index: int) -> Dict[str, Any]:
    hints = scenario.get("hints", [])
    if not hints:
        return {"sender": "김시니어 (AI 동료)", "hint": "현재 시나리오에 등록된 힌트가 없습니다.", "next_index": 0, "has_more": False}
    idx = min(hint_index, len(hints) - 1)
    return {
        "sender": "김시니어 (AI 동료)",
        "hint": hints[idx],
        "next_index": min(idx + 1, len(hints) - 1),
        "has_more": idx < len(hints) - 1,
    }
