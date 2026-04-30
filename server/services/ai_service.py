"""ai_service.py - AI 模型偵測與選擇業務邏輯

負責查詢本地 Ollama 模型清單，並從 config.yaml 合併雲端模型，
回傳排序後的可用模型列表與預設模型。
"""

import re
import os
from typing import Optional, Tuple, List


# 雲端模型名稱前綴（比對時使用 lowercase）
_CLOUD_PREFIXES = [
    'gpt-oss', 'qwen3-vl', 'qwen3-v1', 'ministral-3', 'qwen3-coder',
    'glm-5', 'glm-4.7', 'glm-4.6', 'glm-4', 'deepseek-v3.2',
    'deepseek-v3.1', 'deepseek3.1', 'deepseek-v3', 'minimax-m2',
    'minimax', 'gemini-3', 'kimi', 'qwen3.5', 'nemotron-3',
]

_MANUAL_CLOUD_MODELS = [
    'gpt-oss:120b-cloud', 'deepseek3.1:671b-cloud', 'qwen3-coder:480b-cloud',
    'ministral-3:8b-cloud', 'glm-4.7:cloud', 'minimax-m2:cloud',
]

_PREFERRED_DEFAULTS = [
    'gemma3:4b', 'gemma3:12b', 'minimax-m2:cloud',
    'gpt-oss:120b-cloud', 'ministral-3:8b-cloud', 'qwen3-coder:480b-cloud',
]


def _is_cloud(name: str) -> bool:
    n = name.lower()
    if '-cloud' in n or ':cloud' in n:
        return True
    return any(n.startswith(p) for p in _CLOUD_PREFIXES)


def _sort_key(name: str):
    return (0, name.lower()) if _is_cloud(name) else (1, name.lower())


class AIService:
    def get_available_models(self) -> Tuple[List, str]:
        """
        回傳 (model_names, current_model)。
        model_names 雲端模型排在前、本地排在後，每個 family 去重。
        """
        try:
            import ollama
            client = ollama.Client(host='http://localhost:11434')
            raw    = [self._extract_name(m) for m in client.list().models]
            raw    = [n for n in raw if n]
        except Exception as e:
            print(f'[WARN] 取得 Ollama 模型失敗: {e}')
            raw = ['llama3.1:8b']

        model_dict: dict[str, str] = {}
        for m in raw + _MANUAL_CLOUD_MODELS:
            m_lower = m.lower()
            if 'gemini' in m_lower:
                continue                         # 過濾 Gemini
            base = self._base_family(m_lower)
            key  = base if _is_cloud(m) else m   # 本地不去重，雲端按 family 去重
            if key not in model_dict:
                model_dict[key] = m
            else:
                curr = model_dict[key]
                if _is_cloud(m) and not _is_cloud(curr):
                    model_dict[key] = m
                elif _is_cloud(m) == _is_cloud(curr) and len(m) > len(curr):
                    model_dict[key] = m

        names = sorted(model_dict.values(), key=_sort_key)

        current = next(
            (p for p in _PREFERRED_DEFAULTS if any(str(m) == p for m in names)),
            None,
        )
        if not current:
            current = next(
                (m for m in names if m.startswith('gemma3:') or m.startswith('llama3')),
                None,
            )
        if not current:
            current = names[0] if names else 'llama3.1:8b'

        return names, current

    @staticmethod
    def _extract_name(m) -> Optional[str]:
        if hasattr(m, 'model'):  return m.model
        if hasattr(m, 'name'):   return m.name
        if isinstance(m, dict):  return m.get('model') or m.get('name')
        return None

    @staticmethod
    def _base_family(name_lower: str) -> str:
        match = re.match(r'^([a-z\-]+)(?:[\d\.\-v]*)(?:[:\-].*)?$', name_lower)
        if match:
            b = match.group(1).strip('-')
            if b.startswith('deepseek'): return 'deepseek'
            if b.startswith('qwen'):     return 'qwen'
            if b.startswith('glm'):      return 'glm'
            if b.startswith('gpt'):      return 'gpt'
            return b
        return name_lower.split(':')[0]
