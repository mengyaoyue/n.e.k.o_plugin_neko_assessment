"""图片素材（v1.3.0）：把「狐狐」和表情包接进面板。

素材来源：用户自己给的两套图（狐狐.zip 26 张插画 / 表情.zip 25 张表情），
统一转成 webp 后放在 `static/art/`：

- `art/fox/NN.webp`（长边 760）与 `NN_s.webp`（长边 220，给卡片/头像）；
- `art/sticker/<表情名>.webp`（长边 220，已裁掉底部文件名水印）。

命名与用途：
- 每份量表配一张「主角图」，结果页顶部用它替掉原来的 emoji；
- 表情包按情绪命名（think / hug / tea / laugh…），用在群聊、加载、空状态、报错这些地方。
"""

from __future__ import annotations

FOX_COUNT = 26

# 量表 → 用哪张狐狐（按内容的语气挑，不是随机）
SCALE_FOX = {
    "big5": 5, "big5f": 5, "tipi": 6,
    "type16": 4, "ennea": 8,
    "riasec": 3, "workvalues": 22,
    "attachment": 16, "love": 11, "social": 21,
    "eq": 18, "resilience": 14, "procrastination": 12,
    "via": 6,
    "phq9": 24, "gad7": 24, "pss10": 24, "dass21": 24, "isi": 12,
    "who5": 14, "swls": 22, "rses": 24, "gses": 18,
    "bsmas": 21, "bscs": 18, "ffmq15": 25, "erq": 8, "minispin": 26,
    "groupie": 9, "piggy": 7, "boba": 21, "worker": 12,
    "house": 4, "spirit": 23,
}

# 没有单独指定时按分类兜底
CATEGORY_FOX = {
    "人格": 5, "情绪健康": 24, "职业": 3, "关系": 16, "优势": 6, "趣味": 7,
}

# 表情包：键就是情绪名，前端按语义取
STICKERS = {
    "ask", "think", "shout", "wow", "hug", "sleepy", "dizzy", "tea", "sparkle",
    "boba", "dots", "zzz", "star", "nya", "hmm", "scribble", "laugh", "angry",
    "wink", "blush", "calm", "sing", "wink2", "huh", "shock",
}

# 各版式在结果页右上角配一张表情（不抢主图）
LAYOUT_STICKER = {
    "radar": "calm", "facet": "think", "axes": "wink", "wheel9": "hmm",
    "hexagon": "star", "quadrant": "hug", "quadrant4": "think", "donut": "blush",
    "rank": "sparkle", "battery": "sleepy", "clock": "zzz", "bands": "calm",
    "bands3": "think", "duo": "calm", "gauge": "calm", "chat": "laugh",
    "badge": "wink2", "cup": "tea", "idcard": "sleepy", "crest": "shout",
    "animal": "nya",
}


def fox_prefix(index: int) -> str:
    idx = int(index or 1)
    if idx < 1 or idx > FOX_COUNT:
        idx = 1
    return f"art/fox/{idx:02d}"


def fox_for(scale_id: str, category: str = "") -> dict:
    """返回 {img, thumb}：大图给结果页，小图给卡片/头像。"""
    index = SCALE_FOX.get(scale_id) or CATEGORY_FOX.get(category) or 1
    prefix = fox_prefix(index)
    return {"img": prefix + ".webp", "thumb": prefix + "_s.webp"}


def sticker(name: str) -> str:
    key = name if name in STICKERS else "calm"
    return f"art/sticker/{key}.webp"
