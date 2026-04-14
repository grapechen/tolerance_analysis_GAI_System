"""
progress_tracker.py - 進度跟踪與 SSE (Server-Sent Events) 管理
================================================================
提供實時進度更新功能，支援多個並行操作
"""

import json
from collections import defaultdict
from datetime import datetime
from threading import Lock

# 全局進度狀態存儲
_progress_states = {}  # session_id → progress_data
_state_lock = Lock()


class ProgressTracker:
    """進度跟踪器，用於跟踪長時間操作的進度"""

    def __init__(self, session_id, operation="processing"):
        self.session_id = session_id
        self.operation = operation
        self.current_step = 0
        self.total_steps = 1
        self.message = "準備中..."
        self.status = "running"  # running, completed, error
        self.start_time = datetime.now()

    def update(self, current_step, total_steps=None, message=""):
        """更新進度"""
        with _state_lock:
            self.current_step = current_step
            if total_steps is not None:
                self.total_steps = total_steps
            if message:
                self.message = message

            # 計算進度百分比
            percentage = (self.current_step / max(self.total_steps, 1)) * 100

            _progress_states[self.session_id] = {
                "operation": self.operation,
                "current": self.current_step,
                "total": self.total_steps,
                "percentage": min(percentage, 100),
                "message": self.message,
                "status": self.status,
                "elapsed": (datetime.now() - self.start_time).total_seconds()
            }

    def complete(self, message="完成"):
        """標記為完成"""
        with _state_lock:
            self.status = "completed"
            self.message = message
            _progress_states[self.session_id] = {
                "operation": self.operation,
                "current": self.total_steps,
                "total": self.total_steps,
                "percentage": 100,
                "message": message,
                "status": "completed",
                "elapsed": (datetime.now() - self.start_time).total_seconds()
            }

    def error(self, message="發生錯誤"):
        """標記為錯誤"""
        with _state_lock:
            self.status = "error"
            self.message = message
            _progress_states[self.session_id] = {
                "operation": self.operation,
                "current": self.current_step,
                "total": self.total_steps,
                "percentage": (self.current_step / max(self.total_steps, 1)) * 100,
                "message": message,
                "status": "error",
                "elapsed": (datetime.now() - self.start_time).total_seconds()
            }


def get_progress(session_id):
    """獲取指定 session 的進度"""
    with _state_lock:
        return _progress_states.get(session_id, {
            "operation": "unknown",
            "current": 0,
            "total": 0,
            "percentage": 0,
            "message": "無進度",
            "status": "unknown"
        })


def clear_progress(session_id):
    """清除進度"""
    with _state_lock:
        if session_id in _progress_states:
            del _progress_states[session_id]


def get_all_progress():
    """獲取所有進度"""
    with _state_lock:
        return dict(_progress_states)


def generate_sse_stream():
    """生成 SSE 流（用於持續推送）"""
    import time
    while True:
        all_progress = get_all_progress()
        if all_progress:
            yield f"data: {json.dumps(all_progress)}\n\n"
        time.sleep(0.5)  # 每 500ms 推送一次
