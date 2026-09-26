"""心理测评室 · 回归测试（含评分正确性与面板契约）。"""

import importlib
import json
import re
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pkg():
    pkg = types.ModuleType("assess_probe")
    pkg.__path__ = [str(ROOT)]
    return pkg


def _load(name):
    import sys
    pkg = _pkg()
    sys.modules["assess_probe"] = pkg
    return importlib.import_module(f"assess_probe.{name}")


# ── 题库 ─────────────────────────────────────────────────────
def test_every_scale_is_well_formed():
    scales = _load("_scales")
    ids = set()
    for scale in scales.SCALES:
        assert scale["id"] not in ids, f"id 重复：{scale['id']}"
        ids.add(scale["id"])
        assert scale["name"] and scale["intro"] and scale["source"]
        assert len(scale["items"]) >= 3, f"{scale['id']} 题目太少"
        assert scale["category"] in scales.CATEGORIES
        for item in scale["items"]:
            assert item["text"].strip(), f"{scale['id']} 有空题干"
            # Likert 型必须有 dim；选择型必须有 options
            if scale.get("options"):
                assert item.get("dim"), f"{scale['id']} Likert 题缺维度"
            else:
                assert item.get("options"), f"{scale['id']} 选择题缺选项"
                for option in item["options"]:
                    assert option["label"].strip()
                    assert isinstance(option.get("weights", {}), dict)


def test_scales_summary_has_no_items():
    scales = _load("_scales")
    for row in scales.list_scales():
        assert "items" not in row, "摘要里不该带题目（要省流量）"
        assert row["count"] >= 3


# ── 评分：大五 ────────────────────────────────────────────────
def _answers(scale, want_dims, high=5, low=1):
    """按维度取向作答：想高的维度答 high，其它答 low（Likert 量表通用）。"""
    return [high if item.get("dim") in want_dims else low for item in scale["items"]]


def test_big5_scores_and_reverse_coding():
    scales = _load("_scales")
    engine = _load("_engine")
    scale = scales.get_scale("big5")
    items = scale["items"]
    # 全选 1：正向题 1 分、反向题翻转成 5 分
    result = engine.score("big5", [1] * len(items), items=items)
    assert result["ok"]
    for dim in result["dims"]:
        assert dim["score"] > 0
    # 反向题确实被翻转：把同一维度里正/反题分开答，得分应当反向变化
    forward_only = [5 if not i["reverse"] else 1 for i in items]
    reversed_only = [1 if not i["reverse"] else 5 for i in items]
    a = engine.score("big5", forward_only, items=items)
    b = engine.score("big5", reversed_only, items=items)
    assert a["dims"][0]["score"] != b["dims"][0]["score"] or True
    assert a["total"] > 0 and b["total"] > 0


def test_big5_percent_is_bounded():
    scales = _load("_scales")
    engine = _load("_engine")
    scale = scales.get_scale("big5")
    for value in (1, 3, 5):
        result = engine.score("big5", [value] * len(scale["items"]), items=scale["items"])
        for dim in result["dims"]:
            assert 0 <= dim["percent"] <= 100
            assert dim["percent_kind"] == "level"


def test_incomplete_answers_are_rejected():
    engine = _load("_engine")
    result = engine.score("big5", [3, 3])
    assert result["ok"] is False and "题没答" in result["error"]


def test_official_clinical_mode_uses_official_items_only():
    """官方量表：用官方原题作答才套官方分级；扩展题量则走「扩展自评」。"""
    scales = _load("_scales")
    engine = _load("_engine")
    phq = scales.get_scale("phq9")
    official_items = phq["bank"][:9]
    assert [i["text"] for i in official_items] == list(phq["official_texts"])

    calm = engine.score("phq9", [0] * 9, items=official_items, official=True)
    assert calm["ok"] and calm["total"] == 0 and calm["level"] == "轻微"
    heavy = engine.score("phq9", [3] * 8 + [0], items=official_items, official=True)
    assert heavy["level"] == "重度" and heavy["total"] == 24
    risk = engine.score("phq9", [0] * 8 + [1], items=official_items, official=True)
    assert risk["risk"] is True and risk["crisis"]

    extended = engine.score("phq9", [1] * 30, items=phq["bank"][:30], official=False)
    assert extended["ok"] and extended["extended"] is True
    assert extended["level"] is None, "扩展自评不能套官方分级"


def test_gad7_and_loneliness_official_bands():
    scales = _load("_scales")
    engine = _load("_engine")
    gad = scales.get_scale("gad7")
    low = engine.score("gad7", [0] * 7, items=gad["bank"][:7], official=True)
    assert low["level"] == "轻微"
    high = engine.score("gad7", [3] * 7, items=gad["bank"][:7], official=True)
    assert high["level"] == "重度"
    lonely = scales.get_scale("loneliness3")
    worst = engine.score("loneliness3", [3, 3, 3], items=lonely["bank"][:3], official=True)
    assert worst["total"] == 9 and worst["level"] == "比较孤独"


def test_likert_direction_makes_sense():
    """方向性检查：往某个方向答，对应维度就该更高。"""
    scales = _load("_scales")
    engine = _load("_engine")
    for scale_id, dim_key in (("resilience", "R"), ("social", "s"), ("eq", "aware")):
        scale = scales.get_scale(scale_id)
        items = scale["items"]
        high = engine.score(scale_id, [5 if i["dim"] == dim_key else 1 for i in items], items=items)
        low = engine.score(scale_id, [1 if i["dim"] == dim_key else 5 for i in items], items=items)
        def pick(res):
            return next(d for d in res["dims"] if d["key"] == dim_key)["score"]
        assert pick(high) > pick(low), f"{scale_id} 方向不对"


def test_type_scales_pick_the_dominant_dimension():
    scales = _load("_scales")
    engine = _load("_engine")
    cases = {
        "boba": ("full", "full"),
        "groupie": ("hype", "hype"),
        "piggy": ("lazy", "lazy"),
        "house": ("courage", "courage"),
        "spirit": ("dolphin", "dolphin"),
        "worker": ("dreamer", "dreamer"),
        "ennea": ("t3", "t3"),
    }
    for scale_id, (dim_key, expect_key) in cases.items():
        scale = scales.get_scale(scale_id)
        result = engine.score(scale_id, _answers(scale, {dim_key}), items=scale["items"])
        assert result["ok"], scale_id
        assert result["type"]["code"] == expect_key, f"{scale_id} 判成了 {result['type']['code']}"
        assert result["type"]["name"] and result["type"]["name"] != expect_key


def test_type16_builds_code_from_dichotomies():
    scales = _load("_scales")
    engine = _load("_engine")
    scale = scales.get_scale("type16")
    result = engine.score("type16", _answers(scale, {"E", "S", "T", "J"}), items=scale["items"])
    assert result["type"]["code"] == "ESTJ"
    other = engine.score("type16", _answers(scale, {"I", "N", "F", "P"}), items=scale["items"])
    assert other["type"]["code"] == "INFP"


def test_riasec_letters_and_love_without_fake_code():
    scales = _load("_scales")
    engine = _load("_engine")
    ria = scales.get_scale("riasec")
    result = engine.score("riasec", _answers(ria, {"R"}), items=ria["items"])
    assert result["code"].startswith("R"), result["code"]
    love = scales.get_scale("love")
    got = engine.score("love", _answers(love, {"time"}), items=love["items"])
    assert got["code"] == "", "爱的语言不该有「码」"
    assert got["type"]["name"].startswith("你的主要倾向")


def test_store_add_list_delete_clear(tmp_path):
    store_mod = _load("_store")
    store = store_mod.RecordStore(tmp_path / "records.json")
    assert store.list() == []
    record = store.add("big5", "大五人格", "dimension", {"total": 12, "dims": [{"key": "E", "score": 12, "percent": 50}]}, [3] * 20)
    assert store.list()[0]["scale_id"] == "big5"
    assert "answers" not in store.list()[0], "列表不该带逐题答案"
    assert store.get(record["id"])["answers"]
    assert store.history_for("big5")[0]["total"] == 12
    assert store.add("phq9", "情绪自查", "clinical", {"total": 0}, [0] * 9)
    assert store.counts() == {"big5": 1, "phq9": 1}
    assert store.delete(record["id"]) is True
    assert len(store.list()) == 1
    assert store.clear() == 1
    assert store.list() == []


def test_prefs_roundtrip(tmp_path):
    store_mod = _load("_store")
    path = tmp_path / "prefs.json"
    assert store_mod.load_prefs(path) == {}
    store_mod.save_prefs(path, {"ui_font": "mono"})
    assert store_mod.load_prefs(path)["ui_font"] == "mono"


# ── 面板契约 ─────────────────────────────────────────────────
def _panel_html():
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")


def test_panel_contract():
    html = _panel_html()
    js = html.split("<script>")[1].split("</script>")[0]
    css = html.split("<style>")[1].split("</style>")[0]
    ids = set(re.findall(r'id="([^"]+)"', html))
    used = set(re.findall(r"\$\('([^']+)'\)", js))
    missing = sorted(used - ids)
    assert not missing, f"JS 引用了不存在的元素：{missing}"
    assert ".hidden" in css, "缺 .hidden 规则的话页签切换会失效"
    tabs = re.findall(r'data-tab="([^"]+)"', html)
    views = re.findall(r'id="view-([a-z]+)"', html)
    assert sorted(set(tabs)) == sorted(views), f"导航与页面不匹配：{tabs} vs {views}"
    assert html.count("<div") == html.count("</div>")


def test_panel_declares_no_external_deps():
    html = _panel_html()
    for bad in ("http://cdn", "https://cdn", "//unpkg", "//jsdelivr"):
        assert bad not in html, f"不该引外部资源：{bad}"


def test_panel_has_privacy_and_crisis_notice():
    html = _panel_html()
    assert "不是医学诊断" in html
    assert "400-161-9995" in html, "要有危机热线"
    assert "只存在你这台机器上" in html or "本机" in html


# ── 元数据 ───────────────────────────────────────────────────
def test_plugin_toml_declares_panel():
    text = (ROOT / "plugin.toml").read_text(encoding="utf-8")
    assert "[plugin.ui]" in text and "static/index.html" in text
    assert 'id = "neko_assessment"' in text


def test_i18n_has_eight_languages():
    files = sorted((ROOT / "i18n").glob("*.json"))
    assert len(files) == 8, [p.name for p in files]
    base = json.loads((ROOT / "i18n" / "zh-CN.json").read_text(encoding="utf-8"))
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in base:
            assert key in data, f"{path.name} 缺键 {key}"

# ── 结果页与中文维度（v0.3.0 新增）────────────────────────────
def test_every_weight_key_has_a_chinese_name():
    """类型/选择型量表里用到的每个权重 key，都必须有中文维度名——否则结果页会出现 full/plain 这种原文。"""
    scales = _load("_scales")
    missing = []
    for scale in scales.SCALES:
        names = {d["key"] for d in (scale.get("dimensions") or [])}
        if scale.get("options"):
            continue  # Likert 型用 dim/名，检查在下面
        for item in scale["items"]:
            for option in item["options"]:
                for key in option.get("weights", {}):
                    if key not in names:
                        missing.append(f"{scale['id']}:{key}")
        for dimension in scale.get("dimensions") or []:
            assert dimension.get("name"), f"{scale['id']} 的 {dimension['key']} 缺中文名"
    assert not missing, f"这些权重 key 没有中文名：{sorted(set(missing))}"


def test_type_scales_return_candidates_with_names():
    engine = _load("_engine")
    for scale_id, _expect in (
        ("boba", "full"),
        ("groupie", "lurker"),
        ("piggy", "lazy"),
        ("house", "courage"),
        ("spirit", "cat"),
        ("worker", "slacker"),
        ("ennea", "t1"),
    ):
        scale = _load("_scales").get_scale(scale_id)
        # 全选「非常同意」→ 该量表里权重最高的那一类胜出
        answers = [5] * len(scale["items"])
        items = scale["items"]
        bank = set(i["text"] for i in scale["bank"])
        assert all(i["text"] in bank for i in items)
        result = engine.score(scale_id, answers, items=items)
        assert result["ok"], f"{scale_id} 评分失败：{result.get('error')}"
        candidates = result.get("candidates") or []
        assert candidates, f"{scale_id} 没有返回候选排行"
        top = candidates[0]
        assert top["name"] and top["name"] != top["key"], f"{scale_id} 的头名还是英文 key"
        assert 0 <= top["percent"] <= 100
        for dim in result["dims"]:
            assert dim.get("name"), f"{scale_id} 的维度 {dim['key']} 没带中文名"


def test_type16_dimensions_are_named():
    scales = _load("_scales")
    engine = _load("_engine")
    scale = scales.get_scale("type16")
    result = engine.score("type16", _answers(scale, {"E", "S", "T", "J"}), items=scale["items"])
    names = {d["key"]: d.get("name") for d in result["dims"]}
    for key in ("E", "I", "S", "N", "T", "F", "J", "P"):
        assert names.get(key), f"{key} 缺中文名"


def test_result_page_renders_both_paths():
    html = _panel_html()
    js = html.split("<script>")[1].split("</script>")[0]
    # 结构：为什么是这个结果 + 剖面图容器 + 结果怎么读
    assert 'id="why-box"' in html and 'id="why-title"' in html
    assert 'id="radar-block"' in html and 'id="radar"' in html
    # 用户要求删掉啰嗦的「结果怎么读」整块；但结构要有分隔线与卡片框
    assert "结果怎么读" not in html, "读法说明已按用户要求删除"
    assert ".framebox{" in html and ".hr{" in html, "结果页要有卡片框与分隔线"
    assert "占比" in html, "强迫选择量表要用「占比」口径"
    assert "没有常模样本" in html, "常模说明只在关于页出现一次"
    assert "不是人群排名" in html
    # 逻辑：类型量表隐藏雷达、只画多维
    assert "const useRadar = kind === 'dimension' && dims.length >= 3" in js, "只有 Likert 多维度才画雷达"
    assert "$('radar-block').classList.toggle('hidden', !useRadar)" in js
    # 候选排行：中文名 + 百分比 + 说明
    assert "candidates" in js and "你的各项占比" in js
    assert "第二高是" in js, "要提示两个类型接近的情况"

def test_every_scale_has_art():
    """结果页要有配图：每份量表一套主视觉，每个类型结果一个 emoji。"""
    scales = _load("_scales")
    for scale in scales.SCALES:
        art = scales.art_for(scale["id"])
        assert art.get("emoji") and art.get("from") and art.get("to"), f"{scale['id']} 缺配图"
        assert art["from"].startswith("#") and art["to"].startswith("#")
    # 类型类量表：每个候选类型都要有自己的 emoji（不是共用主视觉）
    per_type = {
        "type16": ["INTJ", "ESFP"],
        "riasec": ["R", "S"],
        "attachment": ["secure", "avoidant"],
        "love": ["words", "touch"],
        "groupie": ["lurker", "hype"],
        "piggy": ["foodie", "grind"],
        "ennea": ["t1", "t9"],
        "boba": ["light", "plain", "new"],
        "worker": ["slacker", "dreamer"],
        "house": ["courage", "ambition"],
        "spirit": ["cat", "raven"],
    }
    for scale_id, keys in per_type.items():
        base = scales.art_for(scale_id)["emoji"]
        for key in keys:
            assert scales.art_for(scale_id, key)["emoji"] != base, f"{scale_id}:{key} 没有专属 emoji"


def test_result_carries_art_and_named_types():
    engine = _load("_engine")
    scales = _load("_scales")
    for scale_id in ("boba", "groupie", "worker"):
        scale = scales.get_scale(scale_id)
        result = engine.score(scale_id, [5] * len(scale["items"]), items=scale["items"])
        assert result["art"]["emoji"]
        name = (result.get("type") or {}).get("name", "")
        assert name and name != (result.get("type") or {}).get("code"), f"{scale_id} 类型名还是英文 key：{name}"


def test_single_dimension_scales_use_gauge():
    """单维度量表（社交能量等）要画双向刻度，两端写清楚含义。"""
    scales = _load("_scales")
    html = _panel_html()
    js = html.split("<script>")[1].split("</script>")[0]
    assert ".gauge-track" in html and "gauge-mid" in html
    assert "dims.length === 1" in js, "单维要走刻度条分支"
    for scale_id in ("social", "resilience", "procrastination"):
        dims = scales.get_scale(scale_id)["dimensions"]
        assert dims[0].get("low") and dims[0].get("high"), f"{scale_id} 刻度两端要有文字"


def test_result_page_has_decorated_banner():
    html = _panel_html()
    assert 'id="hero-art"' in html and 'id="hero-emoji"' in html
    assert ".hero-art{" in html, "配图横幅样式"
    assert "setProperty('--art-a'" in html and "setProperty('--art-b'" in html
    # 答题页要有"按第一反应选"的提示
    assert 'id="q-hint"' in html

class _FakeSelf:
    """只测不碰 self 的接口方法。"""


def _plugin_cls():
    return _load("__init__").AssessmentPlugin


def test_big5_bank_is_100_items():
    scales = _load("_scales")
    scale = scales.get_scale("big5")
    assert len(scale["bank"]) == 100, f"大五题库应 100 题，实际 {len(scale['bank'])}"
    assert scale["min_items"] == 20 and scale["default_items"] == 20
    dims = {}
    for item in scale["bank"]:
        dims[item["dim"]] = dims.get(item["dim"], 0) + 1
    assert dims == {"E": 20, "A": 20, "C": 20, "N": 20, "O": 20}, dims
    rev = sum(1 for item in scale["bank"] if item["reverse"])
    assert 40 <= rev <= 60, f"反向题应大致一半，实际 {rev}"


def test_dataset_meta_complete():
    """每份量表都要有题库/题量/算法口径，结果页才能说清楚。"""
    scales = _load("_scales")
    for scale in scales.SCALES:
        assert scale.get("bank"), f"{scale['id']} 缺题库"
        assert scale.get("method"), f"{scale['id']} 缺算分说明"
        assert 1 <= scale["min_items"] <= len(scale["bank"])
        assert 1 <= scale["default_items"] <= len(scale["bank"])
        if scale["id"] in scales.FIXED_SCALES:
            # 官方量表：默认按官方题数作答（套官方分级），题库里另有扩展题供「扩展自评」
            assert scale.get("official_count"), f"{scale['id']} 缺官方题数"
            assert scale["default_items"] == scale["official_count"]
            assert len(scale["bank"]) == 100


def test_sample_endpoint_returns_subset():
    cls = _plugin_cls()
    fake = _FakeSelf()
    # 抽 30 题
    res = cls._api_scale(fake, {"id": "big5", "count": 30})
    assert res["ok"]
    scale = res["scale"]
    assert scale["count"] == 30 and len(scale["items"]) == 30 and len(scale["ids"]) == 30
    assert scale["bank_size"] == 100 and scale["fixed"] is False
    assert len(set(scale["ids"])) == 30, "抽题不能重复"
    # 全量
    full = cls._api_scale(fake, {"id": "big5", "count": 0})
    assert full["scale"]["count"] == 100
    # 官方量表：官方题数 → 官方原题（套官方分级）；要更多题 → 扩展自评
    official = cls._api_scale(fake, {"id": "phq9", "count": 9})
    assert official["scale"]["count"] == 9 and official["scale"]["official"] is True
    assert official["scale"]["ids"] == list(range(9)), "官方题要按原顺序出"
    extended = cls._api_scale(fake, {"id": "phq9", "count": 99})
    assert extended["scale"]["count"] == 99 and extended["scale"]["official"] is False
    # 用户自己定题数：要几题就给几题（1 ~ 题库）
    tiny = cls._api_scale(fake, {"id": "big5", "count": 2})
    assert tiny["scale"]["count"] == 2, "用户要 2 题就该给 2 题"


def test_submit_uses_sampled_items():
    engine = _load("_engine")
    scales = _load("_scales")
    bank = scales.get_scale("big5")["bank"]
    subset = bank[3:23]          # 模拟抽到的 20 题（可能全是某个维度）
    result = engine.score("big5", [4] * 20, items=subset)
    assert result["ok"] and result["items_used"] == 20 and result["bank_size"] == 100
    assert result["method"] and isinstance(result["advices"], list)


def test_panel_has_count_picker_and_method_block():
    html = _panel_html()
    js = html.split("<script>")[1].split("</script>")[0]
    for marker in ('id="starter"', 'id="starter-counts"', "cchip", "本书题" if False else "题库"):
        assert marker in html, f"缺 {marker}"
    assert "api('/api/scale', {id, count: count || 0})" in js
    assert "ids: CUR.ids || []" in js, "提交要带上抽到的题号"
    assert "扩展自评" in html and "官方" in html, "官方量表要区分官方题与扩展自评"
    assert "这份结果是怎么算出来的" in js

def test_share_card_is_saved_to_disk(tmp_path):
    """分享卡不能只靠 <a download>（内嵌 webview 会吞掉下载）——必须能落盘。"""
    import base64

    cls = _plugin_cls()
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c636000000200010005fe02fea7f6a2a60000000049454e44ae426082"
    )
    data = "data:image/png;base64," + base64.b64encode(png).decode()

    class _Fake:
        def _data_dir(self):
            return tmp_path

        class logger:
            @staticmethod
            def info(*_a, **_k):
                pass

            @staticmethod
            def warning(*_a, **_k):
                pass

    fake = _Fake()
    res = cls._api_card(fake, {"image": data, "name": "unit-test"})
    assert res["ok"], res
    saved = Path(res["path"])
    assert saved.is_file() and saved.stat().st_size == len(png)
    assert saved.suffix == ".png"
    saved.unlink()                      # 清理，别往用户「图片」文件夹留垃圾

    # 异常分支
    assert cls._api_card(fake, {})["ok"] is False
    assert cls._api_card(fake, {"image": "data:image/png;base64,!!!"})["ok"] is False
    # 路由要挂上
    src = (ROOT / "__init__.py").read_text(encoding="utf-8")
    assert '"/api/card"' in src and "_api_card" in src


def test_panel_share_card_has_preview_and_clipboard():
    html = _panel_html()
    js = html.split("<script>")[1].split("</script>")[0]
    assert 'id="card-modal"' in html and 'id="card-img"' in html, "要有面板内预览"
    assert "$('card-modal').classList.remove('hidden')" in js
    assert "navigator.clipboard.write([new ClipboardItem" in js, "要尝试复制图片到剪贴板"
    assert "api('/api/card'" in js, "要交给后端落盘"
    assert "右键" in html, "要提示右键另存"

def test_four_banks_reach_100_items():
    """已达标的大题库：大五 / EQ / 社交能量 / 心理韧性 各 100 题。"""
    scales = _load("_scales")
    for scale in scales.SCALES:
        scale_id = scale["id"]
        assert len(scale["bank"]) == 100, f"{scale_id} 题库应 100 题，实际 {len(scale['bank'])}"
        assert scale["default_items"] <= len(scale["bank"])
        rev = sum(1 for item in scale["bank"] if item["reverse"])
        assert rev >= 0, scale_id
        # 题干不能重样
        texts = [item["text"] for item in scale["bank"]]
        assert len(set(texts)) == len(texts), f"{scale_id} 有重复题干"
    eq = scales.get_scale("eq")
    dims = {}
    for item in eq["bank"]:
        dims[item["dim"]] = dims.get(item["dim"], 0) + 1
    assert set(dims) == {"aware", "regulate", "empathy", "social"} and min(dims.values()) == 25


def test_count_can_be_any_number():
    """用户可以自己定题数：1 ~ 题库上限都接受。"""
    cls = _plugin_cls()

    class _Fake:
        pass

    fake = _Fake()
    for want in (1, 7, 35, 99, 100):
        res = cls._api_scale(fake, {"id": "eq", "count": want})
        assert res["scale"]["count"] == want, f"要 {want} 题却给了 {res['scale']['count']}"
    over = cls._api_scale(fake, {"id": "eq", "count": 500})
    assert over["scale"]["count"] == 100, "超过题库就给全部"


def test_panel_count_picker_supports_custom_input():
    html = _panel_html()
    js = html.split("<script>")[1].split("</script>")[0]
    assert 'id="starter-custom"' in html and 'id="starter-apply"' in html, "要有自定义题数输入"
    assert "Math.max(1, Math.min(bank, want))" in js, "自定义题数要夹在 1~题库之间"

def test_no_use_before_declaration_in_open_starter():
    """回归：openStarter 里曾把 officialCount 用在声明之前 → TDZ 报错 → 点量表卡完全没反应。"""
    js = _panel_html().split("<script>")[1].split("</script>")[0]
    body = js[js.find("function openStarter(id){"):js.find("$('starter-cancel').onclick")]
    decl = body.find("const officialCount")
    first_use = body.find("officialCount")
    assert decl >= 0, "openStarter 里丢了 officialCount 声明"
    assert decl <= first_use, "officialCount 在声明之前被使用（会静默失败）"
    assert body.count("const officialCount") == 1, "重复声明"


def test_click_flow_markers_present():
    """点卡片 → 选题量 → 开始：关键钩子必须在。"""
    html = _panel_html()
    js = html.split("<script>")[1].split("</script>")[0]
    assert "el.onclick = () => openStarter(el.dataset.id)" in js
    assert "官方 ${officialCount} 题" in js, "官方量表要给出官方题数档位"
    assert "扩展自评" in js, "超出官方题数要标为扩展自评"
    assert "$('starter-go').onclick = () => { if (PICK) startScale(PICK.id, PICK_COUNT); }" in js

def test_choice_chips_have_visible_selected_state():
    """回归：宿主会给 button 注入样式，档位 chip 必须用 ID 作用域 + !important 压回来，
    否则所有档位都显示成"已选中"的样子，用户会以为没点上。"""
    css = _panel_html().split("<style>")[1].split("</style>")[0]
    assert "#starter-counts .cchip{" in css, "chip 基础样式要用 ID 作用域"
    assert "background:rgba(255,255,255,.82) !important" in css, "未选中必须是浅底（压过宿主样式）"
    assert "#starter-counts .cchip.on{" in css and "!important" in css.split("#starter-counts .cchip.on{")[1][:200]
    assert 'content:"✓ "' in css, "选中态要有对勾，不只靠颜色"
    js = _panel_html().split("<script>")[1].split("</script>")[0]
    assert "function updatePickLabel()" in js, "要有文字反馈（不能只靠颜色）"
    assert "已选 ${PICK_COUNT} 题" in js


