"""把她请到对话里自己答题，再把她的回答读回来。

为什么不用「把她的记忆注入 prompt 让模型替她答」
------------------------------------------------
那样答话的是**插件**，只是套了她的人设和记忆——不是她。她既不知道自己在答题，
答题时也没有她自己真实的对话上下文（最近聊了什么、什么语气、什么关系）。

正确的做法是**宿主本来就有能力做的**：
  1. 插件把题目 `push_message` 进对话（`ai_behavior="respond"`），
     由宿主用**她本人**的人设、记忆、上下文生成回复——屏幕上就是她在说话；
  2. 宿主每一轮都会把对话写进 `<她的记忆目录>/time_indexed.db`
     （`time_indexed_original` 表，`type` 为 `human` / `ai`，带时间戳）；
  3. 插件按时间戳把**她那条新回复**读回来，解析出答案。

这样「答案是她自己下的」，而且她天然就记得——因为那就是她真实的对话。

路径不许写死
------------
不同人装在不同地方。按可靠性依次取：
  1. 环境变量 `NEKO_YUI_MEMORY_DIR`（测试/手动指定）
  2. 插件配置 `yui_memory_dir`
  3. **问宿主**：`config_manager.memory_dir` + 角色名（宿主自己就是这么拼的）
  4. 从插件自己的数据目录/安装位置上溯找 `memory/<角色名>`
找不到就如实回报「读不到」，绝不猜一个路径硬用。

依赖：json / os / re / sqlite3 / time。读失败一律降级，绝不抛给调用方。
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

# 角色名兜底（正常都能从宿主 config_manager 拿到）
_DEFAULT_CHARACTER = "YUI"


# ── 角色名 / 根目录：优先问宿主 ────────────────────────────────
def host_config_manager() -> Any:
    """宿主的 config_manager；拿不到返回 None（脱离宿主跑测试时就是这样）。"""
    try:
        from utils.config_manager import get_config_manager

        return get_config_manager()
    except Exception:
        return None


def host_character_name(cm: Any = None) -> str:
    """她叫什么。宿主 `get_character_data()` 的第二个返回值就是。"""
    cm = cm or host_config_manager()
    if cm is None:
        return ""
    try:
        data = cm.get_character_data()
        if isinstance(data, (list, tuple)) and len(data) >= 2:
            name = str(data[1] or "").strip()
            if name:
                return name
    except Exception:
        pass
    return ""


def host_memory_root(cm: Any = None) -> str:
    """宿主放记忆的根目录（`memory_dir` 属性）。"""
    cm = cm or host_config_manager()
    if cm is None:
        return ""
    for attr in ("memory_dir", "memory_root"):
        try:
            value = getattr(cm, attr, None)
        except Exception:
            value = None
        if value:
            return str(value)
    getter = getattr(cm, "get_memory_dir", None)
    if callable(getter):
        try:
            return str(getter() or "")
        except Exception:
            pass
    return ""


def resolve_yui_dir(explicit: str = "", hint_dirs: list[str] | None = None) -> tuple[str, str]:
    """定位她的记忆目录。返回 ``(目录, 来源说明)``；找不到返回 ``("", 原因)``。"""
    env = str(os.environ.get("NEKO_YUI_MEMORY_DIR") or "").strip()
    if env:
        return env, "环境变量 NEKO_YUI_MEMORY_DIR"
    explicit = str(explicit or "").strip()
    if explicit:
        return explicit, "插件配置 yui_memory_dir"

    cm = host_config_manager()
    name = host_character_name(cm) or _DEFAULT_CHARACTER
    root = host_memory_root(cm)
    if root:
        cand = os.path.join(root, name)
        if os.path.isdir(cand):
            return cand, f"宿主 config_manager.memory_dir + 角色名「{name}」"
        # 角色名拿不到时，根目录下唯一带对话库的子目录也认
        try:
            subs = [d for d in os.listdir(root)
                    if os.path.isfile(os.path.join(root, d, "time_indexed.db"))]
        except Exception:
            subs = []
        if len(subs) == 1:
            return os.path.join(root, subs[0]), "宿主 memory_dir 下唯一带对话库的角色目录"
        return "", f"宿主 memory_dir（{root}）里找不到角色「{name}」的目录"

    # 从插件自己的位置/数据目录上溯（插件一般装在 <N.E.K.O>/plugins/<id> 下）
    for hint in list(hint_dirs or []) + [os.path.dirname(os.path.abspath(__file__))]:
        if not hint:
            continue
        base = Path(hint)
        for up in range(0, 5):
            try:
                cand = base.parents[up - 1] if up else base
            except IndexError:
                break
            mem = cand / "memory"
            if not mem.is_dir():
                continue
            direct = mem / name
            if direct.is_dir():
                return str(direct), f"从 {hint} 上溯找到 memory/{name}"
            try:
                subs = [d for d in os.listdir(mem)
                        if (mem / d / "time_indexed.db").is_file()]
            except Exception:
                subs = []
            if len(subs) == 1:
                return str(mem / subs[0]), f"从 {hint} 上溯找到 memory/{subs[0]}"
    return "", "问不到宿主路径，也没能从安装位置上溯找到 memory/<角色名>"


# ── 她的对话库 ────────────────────────────────────────────────
_TS_CLEAN = re.compile(r"^\[\d{8}\s+\w{3}\s+\d{2}:\d{2}\]\s*")


def _json_objects(text: str) -> list[dict]:
    """从一段话里捞出所有**括号配对**的 JSON 对象。

    不能只靠正则：她可能写成多行、或者外面再套一层（`{"answers": {...}}`），
    所以按括号配对切块再逐个尝试解析。
    """
    out: list[dict] = []
    depth = 0
    start = -1
    for i, ch in enumerate(text or ""):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                    except Exception:
                        obj = None
                    if isinstance(obj, dict):
                        out.append(obj)
                    start = -1
    return out


def _pick_answers(objs: list[dict], want: int = 0) -> dict | None:
    """在解析出的对象里找 own/guess 两个序号数组（允许外面套一层）。

    ``want`` 给定时必须是**正好那么多题**——她可能先回一句半截的、
    或者回的题数对不上，那些都不能当成答案。
    """
    def norm(obj: dict) -> dict | None:
        try:
            own = [int(x) for x in (obj.get("own") or [])]
            guess = [int(x) for x in (obj.get("guess") or [])]
        except Exception:
            return None
        if not own or len(own) != len(guess):
            return None
        if want and len(own) != int(want):
            return None
        if any(x < 0 or x > 3 for x in own + guess):
            return None
        return {"own": own, "guess": guess}

    for obj in objs:
        got = norm(obj)
        if got:
            return got
        for value in obj.values():            # 外面还套了一层的情况
            if isinstance(value, dict):
                got = norm(value)
                if got:
                    return got
    return None


def _flatten(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for part in content:
            if isinstance(part, dict):
                out.append(str(part.get("text") or ""))
            else:
                out.append(str(part))
        return "".join(out)
    if isinstance(content, dict):
        return str(content.get("text") or "")
    return ""


class YuiDialog:
    """只读她的对话库：用来把「她刚说的那句」读回来。"""

    def __init__(self, yui_dir: str = "", source: str = ""):
        self.yui_dir = str(yui_dir or "")
        self.source = str(source or "")
        self.db_path = os.path.join(self.yui_dir, "time_indexed.db") if self.yui_dir else ""

    @property
    def available(self) -> bool:
        return bool(self.db_path) and os.path.isfile(self.db_path)

    def _query(self, sql: str, params: tuple) -> list[tuple]:
        if not self.available:
            return []
        try:
            conn = sqlite3.connect("file:%s?mode=ro" % self.db_path.replace("\\", "/"), uri=True,
                                   timeout=2.0)
        except Exception:
            return []
        try:
            return conn.execute(sql, params).fetchall()
        except Exception:
            return []
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def latest_ts(self) -> str:
        """库里最新一条消息的时间戳（任何角色）。找不到返回空串。"""
        rows = self._query("select max(timestamp) from time_indexed_original", ())
        return str(rows[0][0] or "") if rows else ""

    def messages_since(self, since_ts: str, *, role: str = "", limit: int = 40) -> list[dict]:
        """取时间戳晚于 ``since_ts`` 的消息（时间戳是 ISO 字符串，字典序即时间序）。"""
        rows = self._query(
            "select message, timestamp from time_indexed_original "
            "where timestamp > ? order by id asc limit ?", (str(since_ts or ""), int(limit))
        )
        out = []
        for msg, ts in rows:
            try:
                obj = json.loads(msg)
            except Exception:
                continue
            kind = str(obj.get("type") or "")
            if role and kind != role:
                continue
            text = _TS_CLEAN.sub("", _flatten((obj.get("data") or {}).get("content"))).strip()
            if text:
                out.append({"type": kind, "ts": str(ts), "text": text})
        return out

    def latest_reply(self) -> dict | None:
        """最近一条她(AI)说的话。"""
        rows = self._query(
            "select message, timestamp from time_indexed_original "
            "where json_extract(message, '$.type') = 'ai' "
            "order by id desc limit 1", ())
        if not rows:
            # 老版本 sqlite 没有 json_extract 时退回 Python 侧过滤
            items = self.messages_since("", role="ai", limit=100000)
            return items[-1] if items else None
        try:
            obj = json.loads(rows[0][0])
        except Exception:
            return None
        text = _TS_CLEAN.sub("", _flatten((obj.get("data") or {}).get("content"))).strip()
        return {"type": "ai", "ts": str(rows[0][1]), "text": text} if text else None

    def find_answers(self, since_ts: str, want: int = 0) -> dict | None:
        """在 ``since_ts`` 之后她说的话里找含有 own/guess 的那条，解析出答案。

        返回 ``{"own": [...], "guess": [...], "reply": 原文, "ts": ...}``；没找到返回 None。
        """
        for item in self.messages_since(since_ts, role="ai", limit=200):
            got = _pick_answers(_json_objects(item["text"]), want)
            if got:
                got.update({"reply": item["text"], "ts": item["ts"]})
                return got
        return None

    def stats(self) -> dict:
        if not self.yui_dir:
            return {"available": False, "reason": "没定位到她的记忆目录"}
        info: dict[str, Any] = {
            "available": self.available,
            "yui_dir": self.yui_dir,
            "db_path": self.db_path,
            "source": self.source,
        }
        if not self.available:
            info["reason"] = ("对话库不存在（%s）" % self.db_path)
            return info
        rows = self._query("select count(*), max(timestamp) from time_indexed_original limit 1", ())
        if rows:
            info["messages"] = int(rows[0][0] or 0)
            info["latest"] = str(rows[0][1] or "")
        return info
