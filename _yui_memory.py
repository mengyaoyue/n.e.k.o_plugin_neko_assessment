#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""猫娘记忆桥 —— 让测评室里的默契测试真的是「YUI 在做题」。

为什么必须有这个
----------------
默契测试原先只给模型发了一句通用猫娘话术 + 10 道题：**没有人设、没有关于主人的
记忆、没有对话历史**。于是「她自己想选什么」其实是模型随手挑的，而且这一轮
**从没进过她的记忆**——她根本不知道自己答过。

这里把 N.E.K.O 已经攒下的记忆（N.E.K.O/memory/YUI/）接进来：

  读（注入 prompt，让她以自己作答）
    persona.json    -> 她是谁 / 主人是谁 / 两人的关系
    facts.json      -> 长期事实，按题目做关键词检索
    time_indexed.db -> 近期真实对话

  写（让这一轮真的成为她的经历）
    outbox.ndjson   -> 追加一条 extract_facts，宿主会消费它、抽成长期事实。
                       这是宿主**既有**的入队通道，不是新造的。

事实纪律
--------
- 只注入库里**真的存在**的条目；查不到就是查不到，不编、不填模板。
- 记忆读失败（缺失/损坏/被占用）**必须静默降级**成"没有记忆"，
  绝不能因此让默契测试开不了局——她可以失忆，不能罢工。

来源：除路径解析（default_yui_dir）与文末新增的 compat_context / push_experience
外，全部逐行沿用 neko_maid_bridge/_memory.py（那里已过真机验证）。
Minecraft 专用的 maid_turns / record_turn 一并保留但测评室不会用到——
裁剪容易引入召回偏差，宁可留几段不走的代码。"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
import uuid

# ---------------------------------------------------------------- 路径

def default_yui_dir() -> str:
    """定位她的记忆目录：环境变量 -> 从插件自身位置上溯 -> 已知绝对路径。

    原版把路径写死成 D:/neko/N.E.K.O/memory/YUI（那是外部桥进程的唯一选择）；
    测评室是宿主内的插件，自己就能从安装位置上溯找到 <N.E.K.O>，所以两种布局都试：
        <N.E.K.O>/.neko-plugin-installations/plugins/<id>/   （上溯 2 层）
        <N.E.K.O>/plugins/<id>/                              （上溯 1 层）
    判据是目录里真的有人设或事实文件，避免认错地方。
    """
    env = os.environ.get("NEKO_YUI_MEMORY_DIR")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    candidates: list[str] = []
    for up in (0, 1, 2, 3, 4):
        parts = [here] + [".."] * up
        candidates.append(os.path.normpath(os.path.join(*parts, "memory", "YUI")))
    candidates.append(os.path.normpath("D:/neko/N.E.K.O/memory/YUI"))

    def looks_right(d: str) -> bool:
        return (os.path.isfile(os.path.join(d, "persona.json"))
                or os.path.isfile(os.path.join(d, "facts.json")))

    for c in candidates:
        if looks_right(c):
            return c
    for c in candidates:
        if os.path.isdir(c):
            return c
    return candidates[-1]


# ---------------------------------------------------------------- 文本工具

_CJK = re.compile(r"[\u4e00-\u9fff]")
_LATIN = re.compile(r"[A-Za-z0-9_]+")

# 中文双字滑窗会产生大量"的猫""了主""这是"这种噪声 token，不剔掉的话
# 随便问一句都能命中一堆无关事实，反而把 prompt 污染成浆糊。
#
# 注意 token 是**双字**的，所以光列单字不够：两字都是停用字的组合（这是/的了/个都…）
# 也要一起丢掉，否则停用词表形同虚设。
_STOP_CHARS = set(
    "的了是在和与及就都也很太还又再有没不别要会能可说做去来上下里这那你我他她它们个些吗呢吧啊哦嗯一")
_STOP_WORDS = set("""
什么 怎么 为什么 一个 一下 不是 没有 可以 自己 现在 时候 因为 所以 但是 然后 如果
已经 还是 这样 那样 知道 觉得 需要 应该 我们 你们 他们 这个 那个 的话 就是 可是
""".split())

# 查询侧的同义词扩展：库里记的是 "MC"，但用户会打 "Minecraft"/"我的世界"。
# 只扩查询，不改库里的原文——这是"帮你找到"，不是"替你编"。
_SYNONYMS = {
    "minecraft": ["mc", "我的世界"],
    "我的世界": ["mc", "minecraft"],
    "mc": ["minecraft", "我的世界"],
}


def _tokens(text: str) -> list[str]:
    """中文按 2 字滑窗切（和 _knowledge.py 同一套思路），拉丁按词切，剔除停用词。"""
    s = (text or "").lower()
    out: list[str] = []
    for m in _LATIN.findall(s):
        if len(m) >= 2:
            out.append(m)
    cjk = "".join(_CJK.findall(s))
    for i in range(len(cjk) - 1):
        bigram = cjk[i:i + 2]
        if bigram in _STOP_WORDS:
            continue
        # 两字都是停用字（这是 / 的了 / 个都…）也是噪声
        if bigram[0] in _STOP_CHARS and bigram[1] in _STOP_CHARS:
            continue
        out.append(bigram)
    if len(cjk) == 1 and cjk not in _STOP_CHARS:
        out.append(cjk)
    return out


def _expand(query: str) -> set[str]:
    """查询 token + 同义词扩展后的 token。"""
    toks = set(_tokens(query))
    low = (query or "").lower()
    for key, alts in _SYNONYMS.items():
        if key in low:
            for a in alts:
                toks |= set(_tokens(a))
    return toks


def _flatten_content(content) -> str:
    """TLM / N.E.K.O 的消息体有两种形态：纯字符串，或 [{'type':'text','text':...}]。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                t = p.get("text") or p.get("content")
                if isinstance(t, str):
                    parts.append(t)
        return "\n".join(parts)
    if isinstance(content, dict):
        t = content.get("text") or content.get("content")
        return t if isinstance(t, str) else ""
    return ""


def _clip(s: str, n: int) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n - 1] + "…"


def _is_misplaced_card_field(section: str, text: str) -> bool:
    """识别角色卡字段被填错段的录入错误。

    实测：master 段里有一条 "性别: 猫娘1"——那是 YUI 自己的性别字段被填到了
    主人段里。把这种脏数据注入 system 会让模型以为"主人的性别是猫娘"。
    只针对这一处明确错误，不做泛化的主观过滤。
    """
    if section != "master":
        return False
    return bool(re.match(r"^性别\s*[:：]\s*猫娘", text))


# ---------------------------------------------------------------- 记忆主体

class YuiMemory:
    """读 N.E.K.O 的猫娘记忆 + 维护 Minecraft 侧的短期记忆。"""

    def __init__(self, yui_dir: str | None = None, local_dir: str | None = None):
        self.yui_dir = yui_dir or default_yui_dir()
        here = os.path.dirname(os.path.abspath(__file__))
        self.local_dir = local_dir or os.path.join(here, "data")
        self._lock = threading.Lock()

        self._facts_cache: list[dict] | None = None
        self._facts_mtime = 0.0
        self._persona_cache: dict | None = None
        self._persona_mtime = 0.0
        self._pushed = 0          # 已经推给宿主抽事实的轮数（避免每轮都刷）
        self._enabled = True

    # ------------------------------------------------ 低层读取（全部可失败降级）

    def _read_json(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _facts(self) -> list[dict]:
        """带 mtime 缓存地读 facts.json（412 条长期事实）。"""
        path = os.path.join(self.yui_dir, "facts.json")
        try:
            mt = os.path.getmtime(path)
        except Exception:
            return self._facts_cache or []
        if self._facts_cache is not None and mt <= self._facts_mtime:
            return self._facts_cache
        data = self._read_json(path)
        if isinstance(data, list):
            with self._lock:
                self._facts_cache = data
                self._facts_mtime = mt
            return data
        return self._facts_cache or []

    def _persona(self) -> dict:
        """带 mtime 缓存地读 persona.json（neko / master / relationship 三段）。"""
        path = os.path.join(self.yui_dir, "persona.json")
        try:
            mt = os.path.getmtime(path)
        except Exception:
            return self._persona_cache or {}
        if self._persona_cache is not None and mt <= self._persona_mtime:
            return self._persona_cache
        data = self._read_json(path)
        if isinstance(data, dict):
            with self._lock:
                self._persona_cache = data
                self._persona_mtime = mt
            return data
        return self._persona_cache or {}

    # ------------------------------------------------ 人设：她是谁 / 你是谁 / 你们什么关系

    def persona_block(self, limit: int = 6) -> str:
        """从 persona.json 抽三段人设。按 reinforcement 排序，跳过被压制的条目。"""
        p = self._persona()
        if not p:
            return ""

        titles = {
            "neko": "你是谁（你自己的设定）",
            "master": "你记得的主人",
            "relationship": "你和主人的关系",
        }
        blocks = []
        for sec in ("neko", "master", "relationship"):
            facts = (p.get(sec) or {}).get("facts") or []
            rows = []
            for f in facts:
                if not isinstance(f, dict):
                    continue
                if f.get("suppress"):
                    continue
                text = _clip(str(f.get("text") or ""), 120)
                if not text:
                    continue
                if _is_misplaced_card_field(sec, text):
                    # 角色卡录入时把 YUI 自己的字段错填进了 master 段（"性别: 猫娘1"），
                    # 那是录入错误不是事实，注入进去只会让她把主人认成猫娘。
                    continue
                rows.append((float(f.get("reinforcement") or 0.0),
                             bool(f.get("protected")), text))
            if not rows:
                continue
            # protected 的永远在前，其余按 reinforcement 降序
            rows.sort(key=lambda r: (r[1], r[0]), reverse=True)
            lines = ["- " + r[2] for r in rows[:limit]]
            blocks.append("【%s】\n%s" % (titles[sec], "\n".join(lines)))
        return "\n".join(blocks)

    # ------------------------------------------------ 长期事实检索

    def recall(self, query: str, k: int = 6) -> list[str]:
        """按当前这句话检索相关的长期事实。命中不到就返回空——不许编。"""
        facts = self._facts()
        if not facts:
            return []
        q = _expand(query)
        if not q:
            return []

        # 拉丁专名（mc / minecraft / deepseek）比中文双字有价值得多：
        # "MC" 命中一条就是强相关，而"的世"命中一条多半是噪声。分开计权。
        q_lat = {t for t in q if _LATIN.fullmatch(t)}
        q_cjk = q - q_lat

        scored = []
        for f in facts:
            if not isinstance(f, dict):
                continue
            text = str(f.get("text") or "")
            if not text:
                continue
            ft = set(_tokens(text))
            ft_lat = {t for t in ft if _LATIN.fullmatch(t)}
            ft_cjk = ft - ft_lat

            hit_cjk = len(q_cjk & ft_cjk)
            hit_lat = len(q_lat & ft_lat)
            hit = hit_cjk + hit_lat * 2
            # 门槛：只命中 1 个中文双字基本是噪声。宁可检索不到，也不塞不相干的。
            if hit < 2 and len(q) > 2:
                continue
            if hit == 0:
                continue
            imp = float(f.get("importance") or 0)
            # 命中率为主 + 命中数，重要性只做小幅加权（不让它压过相关性）
            rate = hit / max(len(q_cjk) + len(q_lat) * 2, 1)
            scored.append((hit + rate * 2 + imp * 0.05, imp, text))

        if not scored:
            return []
        scored.sort(key=lambda r: (r[0], r[1]), reverse=True)
        return [_clip(t, 110) for _s, _i, t in scored[:k]]

    # ------------------------------------------------ 桌面端最近的共同经历

    def recent_dialog(self, k: int = 6) -> list[str]:
        """time_indexed.db 里最近几条真实对话（这是"记忆结晶"的原料）。"""
        db = os.path.join(self.yui_dir, "time_indexed.db")
        if not os.path.exists(db):
            return []
        out: list[str] = []
        try:
            conn = sqlite3.connect("file:%s?mode=ro" % db.replace("\\", "/"), uri=True)
            try:
                rows = conn.execute(
                    "select message, timestamp from time_indexed_original "
                    "order by id desc limit ?", (k * 3,)
                ).fetchall()
            finally:
                conn.close()
        except Exception:
            return []

        for msg, ts in rows:
            try:
                obj = json.loads(msg)
            except Exception:
                continue
            who = "主人" if obj.get("type") == "human" else "你"
            text = _clip(_flatten_content((obj.get("data") or {}).get("content")), 90)
            if not text:
                continue
            # 抹掉 N.E.K.O 注入的时间戳前缀，避免模型以为"现在"是那个时间
            text = re.sub(r"^\[\d{8}\s+\w{3}\s+\d{2}:\d{2}\]\s*", "", text)
            out.append("%s：%s" % (who, text))
            if len(out) >= k:
                break
        out.reverse()
        return out

    # ------------------------------------------------ Minecraft 侧短期记忆

    def _turns_path(self) -> str:
        return os.path.join(self.local_dir, "maid_turns.json")

    def maid_turns(self, k: int = 12) -> list[str]:
        data = self._read_json(self._turns_path())
        if not isinstance(data, list):
            return []
        rows = []
        for t in data[-k:]:
            if not isinstance(t, dict):
                continue
            who = "主人" if t.get("role") == "user" else "你"
            text = _clip(str(t.get("text") or ""), 90)
            if text:
                rows.append("%s：%s" % (who, text))
        return rows

    def record_turn(self, role: str, text: str, keep: int = 60) -> None:
        """把这一轮对话记进 Minecraft 侧的短期记忆（滚动窗口）。

        整个"读-改-写"必须串行：maid_bridge 每个连接一个线程，两个对话同时进来时，
        不锁的话会互相覆盖，甚至把刚删掉/刚压缩的旧数据"复活"回去（实测踩过）。
        """
        text = _clip(str(text or ""), 400)
        if not text:
            return
        path = self._turns_path()
        try:
            with self._lock:
                os.makedirs(self.local_dir, exist_ok=True)
                data = self._read_json(path)
                if not isinstance(data, list):
                    data = []
                data.append({"role": role, "text": text, "ts": time.time()})
                data = data[-keep:]
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                os.replace(tmp, path)
        except Exception:
            # 短期记忆写不进去不影响她说话
            pass

    # ------------------------------------------------ 回写：让桌面端那只猫娘也记得

    def push_to_host(self, messages: list[dict]) -> bool:
        """往 outbox.ndjson 追加一条 extract_facts，让宿主把这段对话抽成长期事实。

        这是宿主**既有**的入队通道（格式照抄它自己写的那些条目）。
        """
        if not messages:
            return False
        outbox = os.path.join(self.yui_dir, "outbox.ndjson")
        if not os.path.exists(outbox):
            return False
        op = {
            "op_id": str(uuid.uuid4()),
            "type": "extract_facts",
            "payload": {"messages": messages, "render_language": "zh-CN"},
            "status": "pending",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S.", time.localtime()) + "%06d" % int((time.time() % 1) * 1e6),
        }
        try:
            with open(outbox, "a", encoding="utf-8") as f:
                f.write(json.dumps(op, ensure_ascii=False) + "\n")
            return True
        except Exception:
            return False

    def maybe_push_recent(self, every: int = 4) -> bool:
        """每累积 every 轮，把最近这几轮推给宿主抽一次事实。别每轮都刷。"""
        data = self._read_json(self._turns_path())
        if not isinstance(data, list) or not data:
            return False
        if len(data) - self._pushed < every:
            return False
        batch = data[self._pushed:]
        self._pushed = len(data)
        msgs = [{"type": "human" if t.get("role") == "user" else "ai",
                 "data": {"content": [{"type": "text", "text": str(t.get("text") or "")}]}}
                for t in batch[-8:]]
        return self.push_to_host(msgs)

    # ------------------------------------------------ 组装

    def build_context(self, query: str,
                      persona_limit: int = 6,
                      fact_k: int = 6,
                      dialog_k: int = 5,
                      turn_k: int = 10) -> str:
        """拼成要注入 system 的记忆块。没有任何一条记忆时返回空串。"""
        if not self._enabled:
            return ""

        parts: list[str] = []

        persona = self.persona_block(persona_limit)
        if persona:
            parts.append(persona)

        facts = self.recall(query, fact_k)
        if facts:
            parts.append("【你记得的事（只列和此刻有关的）】\n" +
                         "\n".join("- " + t for t in facts))

        dialog = self.recent_dialog(dialog_k)
        if dialog:
            parts.append("【最近你们说过的话】\n" + "\n".join("- " + t for t in dialog))

        turns = self.maid_turns(turn_k)
        if turns:
            parts.append("【刚才在 Minecraft 里发生的】\n" + "\n".join("- " + t for t in turns))

        return "\n\n".join(parts)

    def stats(self) -> dict:
        facts = len(self._facts())
        sections = len([k for k in ("neko", "master", "relationship")
                        if (self._persona().get(k) or {}).get("facts")])
        db_exists = os.path.exists(os.path.join(self.yui_dir, "time_indexed.db"))
        # available = 真的能拿来用（目录在、且里面确实有东西）。调用方据此决定
        # 是"她参考了记忆"还是"她其实什么都没参考"，不许含糊。
        available = bool(os.path.isdir(self.yui_dir) and (facts or sections))
        out = {
            "yui_dir": self.yui_dir,
            "available": available,
            "facts": facts,
            "persona_sections": sections,
            "db_exists": db_exists,
            "maid_turns": len(self._read_json(self._turns_path()) or []),
        }
        if not available:
            out["reason"] = ("记忆目录不存在" if not os.path.isdir(self.yui_dir)
                             else "记忆库里没有可用的人设或事实")
        return out

    # ------------------------------------------------ 默契测试专用：组装 + 回写

    def compat_context(self, queries: list[str], *, persona_limit: int = 6,
                       fact_k: int = 5, dialog_k: int = 4) -> tuple[str, dict]:
        """给默契测试拼上下文，并**如实回报**到底用到了什么。

        `queries` 是若干条检索词（一般是几道题的问句）。之所以是多条而不是一条：
        单条问句往往是假设性问题，和记忆库里的词汇重合很少，只查一条经常一条都捞不到；
        逐条 recall 再取并集，覆盖率明显更好。
        返回 (注入用的文本, 来源统计)。文本为空 = 一条记忆都没有，调用方必须如实说明。
        """
        parts: list[str] = []
        info = {"persona": 0, "facts": 0, "dialog": 0, "available": False}

        persona = self.persona_block(persona_limit)
        if persona:
            parts.append(persona)
            info["persona"] = persona.count("- ")

        picked: list[str] = []
        seen: set[str] = set()
        for q in queries:
            for item in self.recall(q, fact_k):
                if item not in seen:
                    seen.add(item)
                    picked.append(item)
        if picked:
            picked = picked[: fact_k * 2]
            parts.append("【你记得的事（和这次要答的题有关）】\n"
                         + "\n".join("- " + t for t in picked))
            info["facts"] = len(picked)

        dialog = self.recent_dialog(dialog_k)
        if dialog:
            parts.append("【最近你们说过的话】\n" + "\n".join("- " + t for t in dialog))
            info["dialog"] = len(dialog)

        info["available"] = bool(parts)
        return "\n\n".join(parts), info

    def push_experience(self, text: str) -> bool:
        """把这一轮当作「她自己的经历」回写，让宿主抽成长期事实。"""
        text = str(text or "").strip()
        if not text:
            return False
        return self.push_to_host([
            {"type": "ai", "data": {"content": [{"type": "text", "text": text}]}}
        ])


# ---------------------------------------------------------------- 自检

def _selfcheck() -> int:
    m = YuiMemory()
    print("记忆目录:", m.yui_dir)
    print("统计:", json.dumps(m.stats(), ensure_ascii=False))
    print()
    print("=== 人设块 ===")
    print(m.persona_block(4) or "（空）")
    print()
    for q in ("学习", "六级", "Minecraft 女仆", "作息", "随便一句不相关的话"):
        print("=== 检索 %r ===" % q)
        for t in m.recall(q, 3):
            print("  -", t)
        print("  （无命中）" if not m.recall(q, 3) else "")
    print()
    print("=== 最近对话 ===")
    for t in m.recent_dialog(4):
        print("  -", t)
    return 0


if __name__ == "__main__":
    raise SystemExit(_selfcheck())
