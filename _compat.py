"""默契测试核心逻辑：抽题、计分、回合状态机（纯函数 + JSON 存储）。

## 玩法（复刻双人秘密作答的机制，题目与实现全部自写）

一轮 10 题。每题两个人各答两问：**自己选什么** + **猜对方选什么**。
双方都交卷前，任何接口都不返回对方的答案；都交卷后同时揭晓：

- 选择一致 a/10：两人自己选的相同（心意相通）
- 你猜中她 b/10：你猜的就是她实际选的
- 她猜中你 c/10：她猜的就是你实际选的
- 综合默契分 = (a+b+c)/30 × 100，口径就这三项，没有黑箱。

## YUI 的答案从哪来（诚实第一）

- 模型在线：LLM 后台线程现场作答（source="llm"），那才是"她自己想的"；
- 模型不可用：用 ``_compat_data`` 里每题的出厂档案兜底（source="archive"），
  面板明确标注"离线档案"，绝不装作实时作答；
- 档案/模型都没有的极端情况：接口直接报错，不编答案。

## 存储

``data/compat.json``，``threading.Lock`` + ``.tmp`` 原子写（与塔罗、切水果同一套纪律）。
与测评记录（records.json）、切水果战绩（games.json）完全分开。
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
from pathlib import Path
from typing import Any, Optional

from ._compat_data import CATEGORIES, QUESTION_BY_ID, QUESTIONS

ROUND_SIZE = 10
MAX_ROUNDS = 30
VALID_STATUS = ("answering", "ready", "revealed", "abandoned")


def question_public(question_id: str) -> Optional[dict]:
    """出题给前端：只带文本与选项，绝不带档案答案。"""
    q = QUESTION_BY_ID.get(str(question_id))
    if q is None:
        return None
    return {
        "id": q["id"],
        "cat": q["cat"],
        "cat_name": CATEGORIES.get(q["cat"], q["cat"]),
        "text": q["text"],
        "options": list(q["options"]),
    }


def sample_questions(count: int = ROUND_SIZE, rng: Optional[random.Random] = None) -> list[str]:
    """从 60 题里不放回抽 count 题（类别尽量铺开：每类先各拿一题再补满）。"""
    roller = rng or random
    want = max(1, min(len(QUESTIONS), int(count)))
    by_cat: dict[str, list[dict]] = {}
    for q in QUESTIONS:
        by_cat.setdefault(q["cat"], []).append(q)
    picked: list[dict] = []
    for cat in CATEGORIES:                       # 每个类别先来一题，覆盖面优先
        pool = list(by_cat.get(cat) or [])
        if pool and len(picked) < want:
            picked.append(roller.choice(pool))
    rest = [q for q in QUESTIONS if q not in picked]
    roller.shuffle(rest)
    picked.extend(rest[: want - len(picked)])
    roller.shuffle(picked)
    return [q["id"] for q in picked[:want]]


def archive_answers(question_ids: list[str]) -> dict[str, list[int]]:
    """YUI 离线档案答案：她档案里的自选 + 她对主人的档案猜测。"""
    own: list[int] = []
    guess: list[int] = []
    for qid in question_ids:
        q = QUESTION_BY_ID.get(str(qid))
        own.append(int(q["own"]) if q else 0)
        guess.append(int(q["guess"]) if q else 0)
    return {"own": own, "guess": guess}


def validate_answers(question_ids: list[str], answers: Any) -> Optional[dict[str, list[int]]]:
    """校验用户提交：长度对齐、每题 own/guess 都是合法选项序号。不合法返回 None。"""
    if not isinstance(answers, list) or len(answers) != len(question_ids):
        return None
    own: list[int] = []
    guess: list[int] = []
    for qid, item in zip(question_ids, answers):
        q = QUESTION_BY_ID.get(str(qid))
        if q is None or not isinstance(item, dict):
            return None
        try:
            o = int(item.get("own"))
            g = int(item.get("guess"))
        except Exception:
            return None
        if not (0 <= o < len(q["options"]) and 0 <= g < len(q["options"])):
            return None
        own.append(o)
        guess.append(g)
    return {"own": own, "guess": guess}


def classify_round(question_ids: list[str], self_a: dict, yui_a: dict) -> dict:
    """揭晓计分：逐题对照 + 三项汇总 + 综合默契分。纯计算，方便测试。"""
    rows = []
    same = self_hit = yui_hit = 0
    for i, qid in enumerate(question_ids):
        q = QUESTION_BY_ID.get(str(qid)) or {}
        so = int(self_a["own"][i])
        sg = int(self_a["guess"][i])
        yo = int(yui_a["own"][i])
        yg = int(yui_a["guess"][i])
        tags = []
        if so == yo:
            same += 1
            tags.append("心意相通")
        if sg == yo:
            self_hit += 1
            tags.append("你懂她")
        if yg == so:
            yui_hit += 1
            tags.append("她懂你")
        if not tags:
            tags.append("擦肩而过")
        rows.append({
            "id": qid,
            "cat": q.get("cat"),
            "cat_name": CATEGORIES.get(q.get("cat"), q.get("cat")),
            "text": q.get("text", ""),
            "options": list(q.get("options") or []),
            "self_own": so, "self_guess": sg,
            "yui_own": yo, "yui_guess": yg,
            "tags": tags,
        })
    total = len(question_ids) or 1
    score = round((same + self_hit + yui_hit) / (3 * total) * 100)
    return {
        "same": same,
        "self_hit": self_hit,
        "yui_hit": yui_hit,
        "total": len(question_ids),
        "score": score,
        "rows": rows,
    }


class CompatStore:
    """回合状态机 + data/compat.json（lock + 原子写）。

    状态：answering（等双方交卷）→ ready（双方齐了等揭晓）→ revealed；
    开新回合时旧的未完成回合直接标 abandoned（界面一次只玩一轮）。
    """

    def __init__(self, path: Path, *, logger: Any = None) -> None:
        self.path = Path(path)
        self.logger = logger
        self._lock = threading.Lock()

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    def _rounds(self, state: dict) -> list:
        rounds = state.setdefault("rounds", [])
        if not isinstance(rounds, list):
            rounds = []
            state["rounds"] = rounds
        return rounds

    # ── 回合操作（都持锁读写）──────────────────────────────
    def start_round(self, round_id: str, question_ids: list[str]) -> dict:
        with self._lock:
            state = self._read()
            rounds = self._rounds(state)
            for old in rounds:                   # 一次只玩一轮：旧回合没交卷就作废
                if isinstance(old, dict) and old.get("status") in ("answering", "ready"):
                    old["status"] = "abandoned"
            entry = {
                "id": str(round_id),
                "ts": int(time.time()),
                "question_ids": [str(q) for q in question_ids],
                "status": "answering",
                "self": None,
                "yui": None,
                "yui_source": "",
                "result": None,
            }
            rounds.insert(0, entry)
            del rounds[MAX_ROUNDS:]
            try:
                self._write(state)
            except Exception as exc:
                if self.logger is not None:
                    self.logger.warning("[assessment] 默契回合创建失败：{}", exc)
        return dict(entry)

    def set_self(self, round_id: str, answers: dict) -> Optional[dict]:
        return self._fill(round_id, "self", answers)

    def set_yui(self, round_id: str, answers: dict, source: str) -> Optional[dict]:
        return self._fill(round_id, "yui", answers, source=source)

    def _fill(self, round_id: str, side: str, answers: dict, source: str = "") -> Optional[dict]:
        with self._lock:
            state = self._read()
            entry = self._find(state, round_id)
            if entry is None or entry.get("status") not in ("answering", "ready"):
                return None
            entry[side] = {"own": list(answers["own"]), "guess": list(answers["guess"])}
            if side == "yui":
                entry["yui_source"] = str(source or "")
            if entry.get("self") and entry.get("yui"):
                entry["status"] = "ready"
            try:
                self._write(state)
            except Exception as exc:
                if self.logger is not None:
                    self.logger.warning("[assessment] 默契回合写入失败：{}", exc)
            return dict(entry)

    def reveal(self, round_id: str) -> Optional[dict]:
        """双方齐了就计分落盘并返回完整对照；没齐返回带 status 的条目（不泄露答案）。"""
        with self._lock:
            state = self._read()
            entry = self._find(state, round_id)
            if entry is None:
                return None
            if entry.get("status") == "revealed" and isinstance(entry.get("result"), dict):
                return dict(entry)
            if entry.get("status") != "ready":
                return dict(entry)
            result = classify_round(entry["question_ids"], entry["self"], entry["yui"])
            entry["result"] = result
            entry["status"] = "revealed"
            entry["revealed_ts"] = int(time.time())
            try:
                self._write(state)
            except Exception as exc:
                if self.logger is not None:
                    self.logger.warning("[assessment] 默契回合揭晓写入失败：{}", exc)
            return dict(entry)

    def get(self, round_id: str) -> Optional[dict]:
        entry = self._find(self._read(), round_id)
        return dict(entry) if entry else None

    def _find(self, state: dict, round_id: str) -> Optional[dict]:
        for entry in self._rounds(state):
            if isinstance(entry, dict) and entry.get("id") == str(round_id):
                return entry
        return None

    def history(self, limit: int = 12) -> list[dict]:
        """已揭晓的回合摘要（首页展示用，不带逐题答案）。"""
        rows = []
        for entry in self._rounds(self._read()):
            if not isinstance(entry, dict) or entry.get("status") != "revealed":
                continue
            result = entry.get("result") or {}
            rows.append({
                "id": entry.get("id"),
                "ts": entry.get("ts"),
                "score": result.get("score", 0),
                "same": result.get("same", 0),
                "self_hit": result.get("self_hit", 0),
                "yui_hit": result.get("yui_hit", 0),
                "total": result.get("total", 0),
                "yui_source": entry.get("yui_source", ""),
            })
            if len(rows) >= limit:
                break
        return rows


__all__ = [
    "CATEGORIES",
    "QUESTIONS",
    "ROUND_SIZE",
    "CompatStore",
    "archive_answers",
    "classify_round",
    "question_public",
    "sample_questions",
    "validate_answers",
]
