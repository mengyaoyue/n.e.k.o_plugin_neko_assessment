"""把她请到对话里自己答题，再把她的回答读回来。

为什么不用「把她的记忆注入 prompt 让模型替她答」
------------------------------------------------
那样答话的是**插件**，只是套了她的人设和记忆——不是她。她既不知道自己在答题，
答题时也没有她自己真实的对话上下文（最近聊了什么、什么语气、什么关系）。

正确的做法是**宿主本来就有能力做的**：
  1. 插件把题目 `push_message` 进对话（`ai_behavior="respond"`），
     由宿主用**她本人**的人设、记忆、上下文生成回复——屏幕上就是她在说话；
  2. 再把她那条新回复读回来，解析出答案。

这样「答案是她自己下的」，而且她天然就记得——因为那就是她真实的对话。

读回有两条通道（实测教训）
--------------------------
**主通道：宿主记忆服务的实时对话流**
`http://127.0.0.1:<MEMORY_SERVER_PORT>/new_dialog/<她的名字>` 返回已经渲染好的
对话文本，形如 ``梦瑶月 | …`` / ``YUI | …``（多行回复会续行）。这是宿主自己
维护的服务，**不依赖任何文件路径**，也不必猜目录。

**备用通道：`<她的记忆目录>/time_indexed.db`**
但必须**按 `id` 锚点读，不能按 `timestamp` 读**：该库是「快照式」写入，
一次快照把这一轮新增的多行**写成同一个时间戳**（实测同一批 ai/human 三行
时间戳完全相同）。用 `timestamp > since` 去轮询会读到用户自己那条、读漏她那条。
`id` 是自增的，实测 2314 行里 `id` 与 `timestamp` **零冲突**，才是可靠的游标。

路径不许写死
------------
不同人装在不同地方。按可靠性依次取：
  1. 环境变量 `NEKO_YUI_MEMORY_DIR`（测试/手动指定）
  2. 插件配置 `yui_memory_dir`
  3. **问宿主**：`config_manager.memory_dir` + 角色名（宿主自己就是这么拼的）
  4. 从插件自己的数据目录/安装位置上溯找 `memory/<角色名>`
找不到就如实回报「读不到」，绝不猜一个路径硬用。

依赖：json / os / re / sqlite3 / time / urllib。读失败一律降级，绝不抛给调用方。
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# 角色名兜底（正常都能从宿主 config_manager 拿到）
_DEFAULT_CHARACTER = "YUI"
# 主人昵称的兜底。**只是给"已知名字"多一个认法**——对话流的说话人判据是形状，
# 不依赖这个值，所以不同人改了昵称也不会解析错。
_MASTER_FALLBACK = "梦瑶月"

# 本地服务一律绕开系统代理：本机的沙箱/公司代理会拦 127.0.0.1（踩过）
_NO_PROXY = urllib.request.ProxyHandler({})


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


# ── 主通道：宿主记忆服务的实时对话流 ──────────────────────────
_BASE_CACHE: dict[str, str] = {}
# 宿主把记忆服务固定跑在 127.0.0.1 上；端口正常从 config 拿，拿不到就按这个顺序探。
_FALLBACK_PORTS = (48912, 48911, 48913, 48910, 48914, 48915, 48916, 48917)


def candidate_ports() -> list[int]:
    """记忆服务可能监听的端口，按可信度排序（去重）。"""
    out: list[int] = []
    env = str(os.environ.get("NEKO_MEMORY_SERVER_PORT") or "").strip()
    if env.isdigit():
        out.append(int(env))
    try:
        from config import MEMORY_SERVER_PORT  # type: ignore

        out.append(int(MEMORY_SERVER_PORT))
    except Exception:
        pass
    out.extend(_FALLBACK_PORTS)
    seen: set[int] = set()
    uniq: list[int] = []
    for port in out:
        if port not in seen:
            seen.add(port)
            uniq.append(port)
    return uniq


def _open(url: str, timeout: float = 2.0, data: bytes | None = None) -> str:
    """读一个本地 http 服务。失败抛异常，由调用方降级。"""
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    opener = urllib.request.build_opener(_NO_PROXY)
    with opener.open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def memory_server_base(name: str = "", *, refresh: bool = False) -> str:
    """定位宿主的记忆服务。返回 ``http://127.0.0.1:<port>``；找不到返回空串。"""
    if not refresh and _BASE_CACHE.get("base"):
        return _BASE_CACHE["base"]
    who = str(name or _DEFAULT_CHARACTER).strip() or _DEFAULT_CHARACTER
    for port in candidate_ports():
        base = "http://127.0.0.1:%d" % port
        try:
            body = _open("%s/new_dialog/%s?render_language=zh-CN" % (base, who), timeout=1.2)
        except Exception:
            continue
        if body.strip():
            _BASE_CACHE["base"] = base
            return base
    return ""


def _parse_feed(text: str, speakers: tuple[str, ...]) -> list[dict]:
    """把渲染好的对话文本拆成 ``[{"role":…, "text":…}]``。

    格式是 ``<说话人> | <正文>``；正文里的换行会续行，直到下一行出现新的
    ``<说话人> | ``。

    说话人**不能写死**（主人的昵称人人不同），所以判据是形状：
    竖线左边是一小段没有冒号、不以 ``-``/``#`` 开头、长度 ≤ 24 的文字。
    抬头的人设/记忆段全是 ``- 键: 值`` / ``### 标题`` 这种形状，自然被排除；
    已知名字（她 / SYSTEM_MESSAGE）无条件认。
    """
    roles = tuple(r for r in speakers if r)
    out: list[dict] = []
    cur: dict | None = None
    for line in text.split("\n"):
        role = ""
        body = ""
        bar = line.find(" | ")
        if bar > 0:
            head = line[:bar]
            looks_like_speaker = (
                bool(head)
                and len(head) <= 24
                and ":" not in head
                and "：" not in head
                and not head.lstrip().startswith(("-", "#", "*", ">"))
            )
            if head in roles or head == "SYSTEM_MESSAGE" or looks_like_speaker:
                role = head
                body = line[bar + 3:]
        if role:
            if cur:
                out.append(cur)
            cur = {"role": role, "text": body.strip()}
        elif cur is not None:
            cur["text"] = (cur["text"] + "\n" + line.rstrip()) if line.strip() else cur["text"] + "\n"
    if cur:
        out.append(cur)
    for item in out:
        item["text"] = item["text"].strip()
    return [t for t in out if t["text"]]


class YuiFeed:
    """宿主对话流（只读）。**这是读回她实地说了什么的第一个来源。**

    它读的是宿主自己的服务，所以不依赖记忆目录能不能定位到。
    """

    def __init__(self, name: str = "", base: str = ""):
        self.name = str(name or _DEFAULT_CHARACTER).strip() or _DEFAULT_CHARACTER
        self.base = str(base or "")

    def _base(self) -> str:
        return self.base or memory_server_base(self.name)

    @property
    def available(self) -> bool:
        return bool(self._base())

    def turns(self) -> list[dict]:
        base = self._base()
        if not base:
            return []
        try:
            body = _open("%s/new_dialog/%s?render_language=zh-CN" % (base, self.name), timeout=4.0)
        except Exception:
            return []
        return _parse_feed(body, (self.name, _DEFAULT_CHARACTER, _MASTER_FALLBACK))

    def her_turns(self) -> list[str]:
        """她说过的话，按时间顺序。"""
        return [t["text"] for t in self.turns() if t["role"] == self.name]

    def snapshot(self) -> dict:
        """推题**之前**记下游标：**整段对话**的条数 + 最后一条的原文。

        记整段（不只她的话）是因为要拿 ``turns[n-1]`` 做位置校验——窗口
        滚动过就靠不上位置了，那时才退回内容定位。
        """
        turns = self.turns()
        return {
            "count": len(turns),
            "tail": turns[-1]["text"] if turns else "",
            "her_n": sum(1 for t in turns if t["role"] == self.name),
        }

    def new_turns(self, snap: dict) -> list[dict]:
        """相对 ``snap`` 新出现的对话轮。

        先按位置认（要求第 ``count`` 条仍是当时那条，否则说明窗口滚过），
        再退回按内容认。**两条都认不出来就返回空——宁可当没答，也不猜。**
        """
        turns = self.turns()
        snap = snap if isinstance(snap, dict) else {}
        try:
            n = int(snap.get("count") or 0)
        except Exception:
            n = 0
        tail = str(snap.get("tail") or "")
        if n and n <= len(turns) and turns[n - 1]["text"] == tail:
            return turns[n:]
        if tail:
            for i in range(len(turns) - 1, -1, -1):
                if turns[i]["text"] == tail:
                    return turns[i + 1:]
        if not tail and not n:
            return turns
        return []

    def new_her_turns(self, snap: dict) -> list[str]:
        """她相对 ``snap`` 新说的话（按时间顺序）。"""
        return [t["text"] for t in self.new_turns(snap) if t["role"] == self.name]

    def stats(self) -> dict:
        base = self._base()
        info: dict[str, Any] = {
            "available": bool(base),
            "source": ("宿主记忆服务对话流（%s）" % base) if base else "",
            "base": base,
            "character": self.name,
        }
        if not base:
            info["reason"] = "连不上宿主记忆服务（%s）" % (
                "/".join(str(p) for p in candidate_ports()[:4]))
            return info
        try:
            turns = self.turns()
        except Exception as exc:
            info["reason"] = str(exc)
            return info
        hers = [t for t in turns if t["role"] == self.name]
        info["messages"] = len(turns)
        info["her_messages"] = len(hers)
        info["latest"] = (turns[-1]["text"][:60] if turns else "")
        return info


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


# ── 解析她的自由回答 ──────────────────────────────────────────
_FW = str.maketrans("０１２３４５６７８９", "0123456789")
# 选项编号用**从 1 开始**（人自然会这么数，面板上的按钮也是这么标的），
# 所以这里只认 1..n，0 一律当没写。她的原话里往往还带"主人""本喵"之类的水词，
# 所以先按「一行里出现多少合法编号」挑行，再取该行最后 want 个编号。
_NUM_SPLIT = re.compile(r"[^0-9]+")


def _normalize_reply(text: str) -> str:
    return _TS_CLEAN.sub("", str(text or "")).translate(_FW)


def _digit_picks(line: str, n_options: int) -> list[int]:
    out = []
    for chunk in _NUM_SPLIT.split(line):
        if not chunk:
            continue
        try:
            value = int(chunk)
        except Exception:
            continue
        if 1 <= value <= n_options:
            out.append(value - 1)
    return out


def _letter_picks(line: str, n_options: int) -> list[int]:
    if n_options > 4:
        return []
    out = []
    for match in re.finditer(r"(?<![A-Za-z])([A-Da-d])(?![A-Za-z])", line):
        out.append(ord(match.group(1).upper()) - ord("A"))
    return [i for i in out if i < n_options]


def parse_picks(
    text: str,
    n_options: int,
    want: int = 2,
    options: list[str] | None = None,
) -> list[int]:
    """从她的一句话里抠出 ``want`` 个选项，返回 **0-based** 下标。

    认的写法，按可信度依次：
      1. 数字编号（含全角）——挑「合法编号最多」的那一行，取该行最后 ``want`` 个；
      2. ``A``-``D`` 字母；
      3. 选项原文（在整段话里定位，按出现顺序取）。

    抠不出正好 ``want`` 个就返回 ``[]``——**绝不猜、绝不补**。少一个数比编一个数强。
    """
    n_options = int(n_options or 0)
    want = max(1, int(want))
    if n_options < 2:
        return []
    body = _normalize_reply(text)
    if not body.strip():
        return []

    lines = [ln for ln in body.split("\n") if ln.strip()]
    best: list[int] = []
    best_key = (0, 0.0)
    for index, line in enumerate(lines):
        for picks in (_digit_picks(line, n_options), _letter_picks(line, n_options)):
            if len(picks) < want:
                continue
            digits = sum(len(c) for c in _NUM_SPLIT.split(line) if c)
            density = digits / max(1, len(line))
            key = (len(picks), density + index * 1e-9)
            if key > best_key:
                best_key = key
                best = picks
    if best:
        return best[-want:]

    if options:
        hits: list[tuple[int, int]] = []
        for idx, label in enumerate(options[:n_options]):
            needle = _normalize_reply(label).strip()
            if not needle:
                continue
            pos = body.find(needle)
            if pos >= 0:
                hits.append((pos, idx))
        hits.sort()
        seen: list[int] = []
        for _, idx in hits:
            if idx not in seen:
                seen.append(idx)
        if len(seen) >= want:
            return seen[-want:]
    return []


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
        """库里最新一条消息的时间戳（任何角色）。找不到返回空串。

        :warning: 时间戳**不能**当游标用——同一批快照写入的多行共享同一时间戳。
        """
        rows = self._query("select max(timestamp) from time_indexed_original", ())
        return str(rows[0][0] or "") if rows else ""

    def mark(self) -> int:
        """当前最大 ``id``。推题前记下，之后 ``id > mark`` 的就是新增行。"""
        rows = self._query("select max(id) from time_indexed_original", ())
        try:
            return int(rows[0][0] or 0) if rows else 0
        except Exception:
            return 0

    def new_replies(self, mark: int, *, limit: int = 20) -> list[dict]:
        """``id`` 大于 ``mark`` 的她(AI)的新发言，按 id 升序。"""
        try:
            after = int(mark)
        except Exception:
            after = 0
        rows = self._query(
            "select id, message, timestamp from time_indexed_original "
            "where id > ? order by id asc limit ?", (after, int(limit)))
        out = []
        for row_id, msg, ts in rows:
            try:
                obj = json.loads(msg)
            except Exception:
                continue
            if str(obj.get("type") or "") != "ai":
                continue
            text = _TS_CLEAN.sub("", _flatten((obj.get("data") or {}).get("content"))).strip()
            if text:
                out.append({"id": int(row_id), "ts": str(ts), "text": text})
        return out

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
