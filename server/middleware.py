"""
安全中間件和工具函數
"""
from functools import wraps
from flask import request, jsonify
import time
from collections import defaultdict
import threading

# 簡單的速率限制器（防止 API 濫用）
class RateLimiter:
    def __init__(self, max_requests=60, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
        self.lock = threading.Lock()
    
    def is_allowed(self, identifier):
        """檢查是否允許請求"""
        now = time.time()
        
        with self.lock:
            # 清理過期的請求記錄
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier]
                if now - req_time < self.window_seconds
            ]
            
            # 檢查是否超過限制
            if len(self.requests[identifier]) >= self.max_requests:
                return False
            
            # 記錄新請求
            self.requests[identifier].append(now)
            return True

# 全局速率限制器實例
# API 查詢：每分鐘 60 次
api_limiter = RateLimiter(max_requests=60, window_seconds=60)
# AI 查詢：每分鐘 10 次（LLM 較昂貴）
ai_limiter = RateLimiter(max_requests=10, window_seconds=60)

def rate_limit(limiter=api_limiter):
    """速率限制裝飾器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 使用 IP 地址作為識別符
            identifier = request.remote_addr
            
            if not limiter.is_allowed(identifier):
                return jsonify({
                    "ok": False,
                    "msg": "請求過於頻繁，請稍後再試"
                }), 429
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_input(required_fields):
    """輸入驗證裝飾器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            data = request.get_json(force=True)
            
            # 檢查必要欄位
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return jsonify({
                    "ok": False,
                    "msg": f"缺少必要欄位: {', '.join(missing_fields)}"
                }), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def sanitize_error_message(error):
    """清理錯誤訊息，避免洩露敏感資訊"""
    error_str = str(error).lower()
    
    # 檢查是否包含敏感資訊
    sensitive_keywords = ['password', 'connection', 'database', 'mysql', 'sqlalchemy', 'traceback']
    
    for keyword in sensitive_keywords:
        if keyword in error_str:
            return "系統發生錯誤，請稍後再試"
    
    return str(error)
