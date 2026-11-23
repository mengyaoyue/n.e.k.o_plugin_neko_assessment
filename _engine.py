"""评分引擎：把答案算成维度分 / 类型 / 解读。

两类量表：
- Likert 型（有 options + reverse）：加总，反向题翻转，得到维度分与百分比；
- 选择型（每题选项带权重）：累加权重，得到维度分或"哪个维度最高"的类型。
"""

from __future__ import annotations

from typing import Any

from ._bank import DIM_DETAIL
from ._scales import CRISIS_LINES, PRO_DIM_DETAIL, art_for, get_scale, profile_for
from ._scales_ui import ENNEA_META


def _band_for(value: float, bands: list) -> tuple[str, str] | tuple[None, None]:
    """按切点表取分级：(低, 高, 标签, 建议)。切点用百分比。"""
    for band in bands or []:
        try:
            low, high, label, advice = band
        except Exception:
            continue
        if low <= value <= high:
            return label, advice
    return None, None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return default
            return int(float(text))
    except Exception:
        return default
    return default


def score(scale_id: str, answers: list, items: list | None = None, official: bool = False) -> dict:
    """answers：Likert 型是分值数组；选择型是选项下标数组。

    items 给定时用它计分（题库抽样后只对抽到的题计分）。
    """
    scale = get_scale(scale_id)
    if scale is None:
        return {"ok": False, "error": f"没有这份量表：{scale_id}"}

    items = list(items) if items else scale["items"]
    answers = list(answers or [])
    if len(answers) < len(items):
        return {"ok": False, "error": f"还有 {len(items) - len(answers)} 题没答"}

    dim_scores: dict[str, float] = {}
    dim_max: dict[str, float] = {}
    # 分面（facet）：大五 30 面这类「大维度下再分小面」的量表用
    facet_scores: dict[str, float] = {}
    facet_max: dict[str, float] = {}
    raw_sum = 0
    risk = False

    # ① Likert 型（统一选项）
    if scale.get("options"):
        max_value = max(o["value"] for o in scale["options"])
        min_value = min(o["value"] for o in scale["options"])
        for item, value in zip(items, answers):
            raw = _safe_int(value, min_value)
            raw = max(min_value, min(max_value, raw))
            if item.get("reverse"):
                raw = max_value + min_value - raw
            key = item.get("dim", "score")
            dim_scores[key] = dim_scores.get(key, 0) + raw
            dim_max[key] = dim_max.get(key, 0) + max_value
            facet_key = item.get("facet")
            if facet_key:
                facet_scores[facet_key] = facet_scores.get(facet_key, 0) + raw
                facet_max[facet_key] = facet_max.get(facet_key, 0) + max_value
            raw_sum += raw
            if item.get("risk") and _safe_int(value, 0) > 0:
                risk = True
    else:
        # ② 选择型：选项带权重
        for item, index in zip(items, answers):
            options = item["options"]
            pick = _safe_int(index, 0)
            pick = max(0, min(len(options) - 1, pick))
            for key, weight in options[pick].get("weights", {}).items():
                dim_scores[key] = dim_scores.get(key, 0) + weight
                # 权重型没有天然上限，用"每题最多可能加多少"估算
                best = max(o.get("weights", {}).get(key, 0) for o in options)
                dim_max[key] = dim_max.get(key, 0) + max(best, 0)
            if item.get("risk") and pick > 0:
                risk = True
        raw_sum = sum(dim_scores.values())

    # ③ 输出维度
    #    Likert 型：percent = 该维度得分 / 该维度满分
    #    强迫选择型：percent = 该维度得分 / 所有维度正分之和（就是「占比」）
    #    强迫选择量表用满分百分比会失真（没被选到的维度恒为 0、被选中就 100），
    #    所以这里两种口径分开算，字段名也区分开。
    is_forced = not scale.get("options")
    positive_total = sum(max(0.0, float(v)) for v in dim_scores.values()) or 1.0
    dims_out = []
    for key, value in dim_scores.items():
        if is_forced:
            percent = round(max(0.0, float(value)) / positive_total * 100)
        else:
            ceiling = dim_max.get(key, 0) or 1
            percent = round(max(0.0, min(1.0, value / ceiling)) * 100)
        dims_out.append({
            "key": key,
            "score": round(value, 2),
            "percent": percent,
            "percent_kind": "share" if is_forced else "level",
        })
    # 补齐没被答到（0 分）的维度：二分型量表要显示「两侧」，只列胜方会让人以为另一侧不存在
    for meta in scale.get("dimensions") or []:
        if meta["key"] not in dim_scores:
            dims_out.append({"key": meta["key"], "score": 0, "percent": 0,
                             "percent_kind": "share" if is_forced else "level",
                             "name": meta.get("name", meta["key"]), "tip": meta.get("tip", "")})
    dims_out.sort(key=lambda d: -d["score"])

    result: dict = {
        "ok": True,
        "scale_id": scale_id,
        "name": scale["name"],
        "kind": scale.get("kind"),
        "total": round(raw_sum, 2),
        "dims": dims_out,
        "risk": risk,
        # 方向语义：negative = 分越高越糟（压力/失眠那类），前端据此决定箭头颜色
        "direction": scale.get("direction", ""),
        # 刻度盘版式要用：分级带与满分
        "bands": scale.get("bands") or [],
        "max_total": max_value * len(items) if scale.get("options") else None,
    }

    # ③.5 候选排行：类型类量表把每个候选的中文名/说明/百分比都带上，
    #      结果页就能解释「为什么是它」而不是甩几个英文 key
    labels = {d["key"]: d for d in (scale.get("dimensions") or [])}
    if labels:
        total = sum(max(0.0, float(d["score"])) for d in dims_out) or 1.0
        result["candidates"] = [
            {
                "key": d["key"],
                "name": labels.get(d["key"], {}).get("name", d["key"]),
                "tip": labels.get(d["key"], {}).get("tip", ""),
                "score": d["score"],
                "percent": round(max(0.0, float(d["score"])) / total * 100),
            }
            for d in dims_out
        ]
        for d in dims_out:
            meta = labels.get(d["key"])
            if meta:
                d["name"] = meta.get("name", d["key"])
                d["tip"] = meta.get("tip", "")

    # ③.6 双极轴：类型量表每对二分给一条「左 62% / 右 38%」的轴
    #      （16personalities 那种条：不是只看选了哪个字母，还看偏向有多强）
    if scale.get("dichotomies"):
        dim_meta = {d["key"]: d for d in (scale.get("dimensions") or [])}
        axes = []
        for pair in scale["dichotomies"]:
            left_key, right_key = pair["left"], pair["right"]
            left_val = float(dim_scores.get(left_key, 0))
            right_val = float(dim_scores.get(right_key, 0))
            total = left_val + right_val
            left_pct = round(left_val / total * 100) if total else 50
            right_pct = 100 - left_pct
            axes.append({
                "key": pair.get("key", left_key + right_key),
                "name": pair.get("name", ""),
                "left": {
                    "key": left_key,
                    "name": dim_meta.get(left_key, {}).get("name", left_key),
                    "tip": dim_meta.get(left_key, {}).get("tip", ""),
                    "percent": left_pct,
                },
                "right": {
                    "key": right_key,
                    "name": dim_meta.get(right_key, {}).get("name", right_key),
                    "tip": dim_meta.get(right_key, {}).get("tip", ""),
                    "percent": right_pct,
                },
                # strength：离 50% 有多远（0 = 完全左右各半，50 = 一边倒）
                "strength": abs(left_pct - 50),
            })
        result["axes"] = axes

    # ③.7 分面：大五 30 面这类量表，把 30 个 facet 的百分比单独列出来
    facets_meta = scale.get("facets") or []
    if facets_meta and facet_scores:
        meta_map = {f["key"]: f for f in facets_meta}
        facet_rows = []
        for key, value in facet_scores.items():
            ceiling = facet_max.get(key, 0) or 1
            info = meta_map.get(key, {})
            percent = round(max(0.0, min(1.0, float(value) / ceiling)) * 100)
            facet_rows.append({
                "key": key,
                "name": info.get("name", key),
                "dim": info.get("dim", ""),
                "desc": info.get("desc", ""),
                "score": round(value, 2),
                "percent": percent,
                "band": "high" if percent >= 60 else ("low" if percent <= 40 else "mid"),
            })
        facet_rows.sort(key=lambda d: -d["percent"])
        result["facets"] = facet_rows

    # ③.8 维度分级：scale["dim_bands"] 里给每个维度自己的切点
    #      默认按百分比切；DASS-21 这类原量表切点是「原始分」，用 dim_bands_on="score" 指定
    dim_bands = scale.get("dim_bands") or {}
    dim_band_basis = scale.get("dim_bands_on", "percent")
    if dim_bands:
        for dim in dims_out:
            bands = dim_bands.get(dim["key"])
            if not bands:
                continue
            basis_value = dim["score"] if dim_band_basis == "score" else dim["percent"]
            label, advice = _band_for(basis_value, bands)
            if label:
                dim["band"] = label
                dim["band_advice"] = advice

    # ④ 类型判定
    kind = scale.get("kind")
    if kind == "type" and scale.get("dichotomies"):
        code = ""
        for pair in scale["dichotomies"]:
            left = dim_scores.get(pair["left"], 0)
            right = dim_scores.get(pair["right"], 0)
            code += pair["left"] if left >= right else pair["right"]
        result["type"] = profile_for(code, scale_id)

        # 依恋：用焦虑/回避两轴定四型（v1.2.0 起是 12 题两轴版）
        if scale_id == "attachment":
            high_anx = round(float(dim_scores.get("anxious", 0)) /
                             (dim_max.get("anxious") or 1) * 100) >= 55
            high_avo = round(float(dim_scores.get("avoidant", 0)) /
                             (dim_max.get("avoidant") or 1) * 100) >= 55
            result["type"] = profile_for(
                "fearful" if high_anx and high_avo else
                ("anxious" if high_anx else ("avoidant" if high_avo else "secure")),
                "attachment",
            )
            # 展示用：不把内部英文键（secure/anxious…）顶在标题上
            if isinstance(result.get("type"), dict):
                result["type"]["code"] = ""
    elif kind == "type":
        top = dims_out[0]["key"] if dims_out else ""
        if scale_id == "attachment" and "anxious" in dim_scores and "avoidant" in dim_scores:
            anxious_pct = round(float(dim_scores.get("anxious", 0)) /
                                (dim_max.get("anxious") or 1) * 100)
            avoidant_pct = round(float(dim_scores.get("avoidant", 0)) /
                                 (dim_max.get("avoidant") or 1) * 100)
            high_anx = anxious_pct >= 55
            high_avo = avoidant_pct >= 55
            if high_anx and high_avo:
                code = "fearful"
            elif high_anx:
                code = "anxious"
            elif high_avo:
                code = "avoidant"
            else:
                code = "secure"
            result["type"] = profile_for(code, "attachment")
            result["quadrant"] = {"x": anxious_pct, "y": avoidant_pct, "code": code}
            # 展示用：不把内部英文键（secure/anxious…）顶在标题上
            result["type"]["code"] = ""
        else:
            result["type"] = profile_for(top, scale_id)
    elif kind == "dimension_type":
        picked = [d for d in dims_out if d["score"] > 0]
        top = picked[0] if picked else None
        letters_only = all(len(d["key"]) == 1 and d["key"].isalpha() for d in dims_out) if dims_out else False
        if letters_only:
            # 霍兰德那类：字母兴趣码才有意义（得分项不足三个就少给几位，不硬凑）
            code = "".join(d["key"] for d in picked[:3]) or (dims_out[0]["key"] if dims_out else "")
            result["code"] = code
            result["type"] = {"code": code, "name": "兴趣码 " + code}
        else:
            # 爱的语言那类：没有「码」，直接给主维度名与说明
            name = (top or {}).get("name") or (dims_out[0]["key"] if dims_out else "")
            tip = (top or {}).get("tip") or ""
            result["code"] = ""
            result["type"] = {"code": "", "name": f"你的主要倾向：{name}", "summary": tip}

    # ④.5 配图：类型结果用该类型的 emoji，维度量表用主视觉
    top_key = ""
    if result.get("ennea"):
        top_key = str(result["ennea"].get("code") or "")      # t8：配图要用内部键
    elif result.get("type") and isinstance(result["type"], dict):
        top_key = str(result["type"].get("code") or "")
    if not top_key and dims_out:
        top_key = dims_out[0]["key"]
    result["art"] = art_for(scale_id, top_key)

    # ④.6 一测一 UI：结果页版式 + 卡片文案（趣味量表）+ 九型结构
    result["layout"] = scale.get("layout", "radar")
    card_map = scale.get("card_extra") or {}
    if card_map:
        result["card"] = card_map.get(top_key) or {}
    if scale_id == "ennea":
        meta = ENNEA_META.get(top_key) or {}
        if meta:
            result["ennea"] = dict(meta)
            result["ennea"]["code"] = top_key
            # 展示用编号：t8 → 8（t8 留给内部维度键）
            if isinstance(result.get("type"), dict) and top_key.startswith("t"):
                result["type"]["code"] = top_key[1:]

    # ④.8 更丰富的解读：维度长文 + 可执行建议（dimension 类）
    detail = (DIM_DETAIL.get(scale_id) or PRO_DIM_DETAIL.get(scale_id) or {})
    notes = []
    advices = []
    for dim in dims_out[:2]:
        info = detail.get(dim["key"])
        if not info:
            continue
        band = "high" if dim["percent"] >= 55 else ("low" if dim["percent"] <= 45 else "")
        if band and info.get(band):
            notes.append({"key": dim["key"], "title": f"{dim.get('name', dim['key'])}", "text": info[band]})
        for tip in info.get("advice", [])[:3]:
            if tip not in advices:
                advices.append(tip)
    result["notes"] = notes
    result["advices"] = advices[:4]
    result["items_used"] = len(items)
    result["bank_size"] = len(scale.get("bank") or items)
    result["method"] = scale.get("method", "")
    result["fixed"] = bool(scale.get("fixed"))

    # ⑤ 临床型：分级 + 危机提示
    if kind == "clinical":
        result["official"] = bool(official)
        if official:
            # 只有用官方原题作答时才套官方分级；扩展题凑出来的分不能当官方结论
            for low, high, label, advice in scale.get("bands", []):
                if low <= raw_sum <= high:
                    result["level"] = label
                    result["advice"] = advice
                    break
        else:
            ceiling = 0
            for item in items:
                ceiling += 3          # 官方量表每题最高 3 分
            pct = round(raw_sum / ceiling * 100) if ceiling else 0
            result["level"] = None
            result["extended"] = True
            result["extended_percent"] = pct
            result["advice"] = "这是扩展自评（不是官方量表计分）：只看同意程度，不套官方分级。"
        if risk:
            result["risk"] = True
            result["crisis"] = CRISIS_LINES

    return result


def dimension_labels(scale_id: str) -> dict[str, dict]:
    scale = get_scale(scale_id) or {}
    return {d["key"]: d for d in scale.get("dimensions", [])}
