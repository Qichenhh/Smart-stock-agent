"""Session Memory — 当前会话上下文（内存 dict，会话结束即释放）"""

import uuid
from typing import Optional, List
from datetime import datetime


class Session:
    """单个会话的短记忆"""

    def __init__(self):
        self.session_id = str(uuid.uuid4())[:8]
        self.created_at = datetime.now().isoformat()
        self.data = {
            "current_symbol": None,
            "current_name": None,
            "current_task": None,           # comprehensive / compare / quick_check / risk_audit
            "current_step": 0,              # 0=idle, 1-4=agent steps
            "step_results": {},             # {1: "技术面...", 2: "基本面..."}
            "task_history": [],             # [{"action":"analyze","symbol":"000001"}]
            "user_intent": None,            # long_term / short_term / risk_check
            "last_report_id": None,
            "preferences_hint": {},         # 本次临时偏好覆盖
        }

    def set_stock(self, symbol: str, name: str = ""):
        self.data["current_symbol"] = symbol
        self.data["current_name"] = name

    def set_task(self, task: str):
        self.data["current_task"] = task

    def set_step(self, step: int, result: str = ""):
        self.data["current_step"] = step
        if result:
            self.data["step_results"][step] = result

    def record_action(self, action: str, **kwargs):
        self.data["task_history"].append({"action": action, **kwargs, "ts": datetime.now().isoformat()})

    def set_preference_hint(self, key: str, value: str):
        self.data["preferences_hint"][key] = value

    def get_current_symbol(self) -> Optional[str]:
        return self.data.get("current_symbol")

    def get_current_task(self) -> Optional[str]:
        return self.data.get("current_task")

    def get_context_text(self) -> str:
        """生成会话上下文文本，注入 Agent query"""
        sym = self.data.get("current_symbol")
        task = self.data.get("current_task")
        intent = self.data.get("user_intent")
        hints = self.data.get("preferences_hint", {})
        history_count = len(self.data.get("task_history", []))

        parts = []
        if sym:
            parts.append(f"正在分析: {sym}")
        if task:
            parts.append(f"当前任务: {task}")
        if intent:
            parts.append(f"推断意图: {intent}")
        if hints:
            parts.append(f"临时偏好: {', '.join(f'{k}={v}' for k, v in hints.items())}")
        if history_count > 1:
            parts.append(f"本次会话已执行 {history_count} 次操作")

        return "\n".join(parts) if parts else ""


# 全局会话池（key = session_id）
_sessions: dict = {}


def create_session() -> Session:
    s = Session()
    _sessions[s.session_id] = s
    return s


def get_session(session_id: str) -> Optional[Session]:
    return _sessions.get(session_id)


def destroy_session(session_id: str):
    _sessions.pop(session_id, None)
