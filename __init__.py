"""心理测评室（neko_assessment）

心理测评 + 人格测评 + 趣味测评，集成在一个面板里：
- 科学量表用**公共领域 / 公开可复现**的条目（Mini-IPIP、PHQ-9、GAD-7、UCLA 简版）；
- 类型类与趣味量表是**本插件原创条目**；
- 全部数据**只存本机 data/，不上传、不联网**；
- 只作自我了解与反思，**不是医学诊断**。
"""

from __future__ import annotations

import random
import time
import traceback
from pathlib import Path
from typing import Optional


def _mark(step: str) -> None:
    """每一步都往 %TEMP% 追加一行：进程被直接杀掉也能看出死在哪一步。"""
    import tempfile

    try:
        with open(Path(tempfile.gettempdir()) / "neko_assessment_step.txt", "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {step}\n")
    except Exception:
        pass


def _dump_crash(stage: str) -> None:
    """宿主日志只有 start_plugin failed 时的救命稻草：把异常写进 %TEMP%。"""
    import tempfile
    import traceback

    try:
        crash = Path(tempfile.gettempdir()) / f"neko_assessment_crash_{stage}.txt"
        crash.write_text(traceback.format_exc(), encoding="utf-8")
    except Exception:
        pass

try:
    from plugin.sdk.plugin import (
        Err,
        NekoPluginBase,
        Ok,
        lifecycle,
        llm_tool,
        message,
        )

    from ._engine import score
    from ._panel import PanelServer, find_open_port, guess_mime
    from ._scales import CATEGORIES, CRISIS_LINES, get_scale, list_scales
    from ._store import RecordStore, load_prefs, save_prefs
except Exception:
    _dump_crash("import")
    raise

_PLUGIN_ID = "neko_assessment"
_PANEL_PORT = 15800

_PREFS_DEFAULT = {
    "ui_font": "system",
    "ui_font_size": "m",
    "ui_trail": "on",
    "bg_mode": "default",
    "bg_dim": "medium",
}


_mark('before-class')


class AssessmentPlugin(NekoPluginBase):
    _mark('class-enter')
    def __init__(self, ctx):
        try:
            super().__init__(ctx)
            self.file_logger = self.enable_file_logging(log_level="INFO")
            self.logger = self.file_logger
            self.data_dir = Path(self.data_path())
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self._panel_port: int = _PANEL_PORT
            self._panel_server: Optional[PanelServer] = None
            self._prefs: Optional[dict] = None
            self._store: Optional[RecordStore] = None
        except Exception:
            _dump_crash("init")
            raise
    # ── 路径 ─────────────────────────────────────────────────
    def _data_dir(self) -> Path:
        return self.data_dir

    def _records_path(self) -> Path:
        return self._data_dir() / "records.json"

    def _prefs_path(self) -> Path:
        return self._data_dir() / "panel_prefs.json"

    def _bg_dir(self) -> Path:
        path = self._data_dir() / "backgrounds"
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return path

    def _bg_file(self) -> Optional[Path]:
        prefs = self._prefs_payload()
        name = str(prefs.get("bg_file") or "").strip()
        if name:
            candidate = (self._bg_dir() / Path(name).name).resolve()
            if candidate.is_file():
                return candidate
        for suffix in (".png", ".jpg", ".webp", ".gif"):
            candidate = self._bg_dir() / f"custom{suffix}"
            if candidate.is_file():
                return candidate
        return None

    # ── 生命周期 ─────────────────────────────────────────────
    @lifecycle(id="startup")
    async def startup(self, **_):
        try:
            self._store = RecordStore(self._records_path(), logger=self.logger)
            self._prefs = load_prefs(self._prefs_path())
            self._start_panel()
            count = len(list_scales())
            self.logger.info("[assessment] 心理测评室已就绪：{} 份量表", count)
            return Ok("started")
        except Exception:
            self.logger.warning("[assessment] startup 异常：{}", traceback.format_exc())
            _dump_crash("startup")
            return Err("startup failed")

    @lifecycle(id="shutdown")
    def shutdown(self, **_):
        if self._panel_server:
            self._panel_server.stop()
            self._panel_server = None
        return Ok("stopped")

    # ── 面板 ─────────────────────────────────────────────────
    def _panel_html(self) -> str:
        page = Path(__file__).parent / "static" / "index.html"
        try:
            return page.read_text(encoding="utf-8")
        except Exception:
            return "<h1>面板页缺失（static/index.html）</h1>"

    def _start_panel(self) -> None:
        endpoints = {
            ("GET", "/api/scales"): self._api_scales,
            ("POST", "/api/scale"): self._api_scale,
            ("POST", "/api/submit"): self._api_submit,
            ("GET", "/api/records"): self._api_records,
            ("POST", "/api/records"): self._api_records,
            ("POST", "/api/records/delete"): self._api_delete,
            ("POST", "/api/records/clear"): self._api_clear,
            ("POST", "/api/history"): self._api_history,
            ("GET", "/api/prefs"): self._api_prefs,
            ("POST", "/api/prefs"): self._api_prefs,
            ("POST", "/api/export"): self._api_export,
            ("POST", "/api/card"): self._api_card,
        }
        port = find_open_port(self._panel_port)
        server = PanelServer(
            port,
            self._panel_html,
            endpoints,
            static_dir=Path(__file__).parent / "static",
            asset_provider=self._bg_asset_for,
        )
        if server.start():
            self._panel_server = server
            self._panel_port = port
            self.logger.info("[assessment] 面板已启动: http://127.0.0.1:{}", port)
            try:
                self.register_static_ui("static")
            except Exception as exc:
                self.logger.warning("[assessment] static UI 注册失败: {}", exc)
        else:
            self.logger.warning("[assessment] 面板启动失败")

    # ── 接口 ─────────────────────────────────────────────────
    def _api_scales(self, _body: dict) -> dict:
        counts = self._store.counts() if self._store else {}
        rows = list_scales()
        for row in rows:
            row["done"] = counts.get(row["id"], 0)
            scale = get_scale(row["id"]) or {}
            row["bank_size"] = len(scale.get("bank") or scale.get("items") or [])
            row["default_items"] = int(scale.get("default_items") or row["count"])
            row["min_items"] = int(scale.get("min_items") or row["count"])
            row["fixed"] = bool(scale.get("fixed"))
            row["official_count"] = int(scale.get("official_count") or 0)
        return {"ok": True, "scales": rows, "categories": CATEGORIES}

    def _api_scale(self, body: dict) -> dict:
        """取本次要答的题：从题库里随机抽 count 题（官方量表固定题量，不抽样）。"""
        payload = body or {}
        scale_id = str(payload.get("id") or "").strip()
        scale = get_scale(scale_id)
        if scale is None:
            return {"ok": False, "error": f"没有这份量表：{scale_id}"}

        bank = list(scale.get("bank") or scale["items"])
        total = len(bank)
        fixed = bool(scale.get("fixed"))
        try:
            want = int(payload.get("count") or 0)
        except Exception:
            want = 0
        official_count = int(scale.get("official_count") or 0)
        official = False
        if official_count and want == official_count:
            official = True                       # 官方题数：按原量表顺序出官方原题
            ids = list(range(official_count))
        elif want <= 0 or want >= total:
            ids = list(range(total))
        else:
            want = max(1, min(total, want))   # 用户自己定题数就得听用户的，只做上下界保护
            ids = sorted(random.sample(range(total), want))

        return {
            "ok": True,
            "scale": {
                "id": scale["id"],
                "name": scale["name"],
                "kind": scale.get("kind"),
                "intro": scale["intro"],
                "source": scale["source"],
                "options": scale.get("options"),
                "dimensions": scale.get("dimensions", []),
                "dichotomies": scale.get("dichotomies", []),
                "items": [bank[i] for i in ids],
                "ids": ids,
                "count": len(ids),
                "bank_size": total,
                "min_items": int(scale.get("min_items") or 6),
                "default_items": int(scale.get("default_items") or len(ids)),
                "fixed": fixed,
                "official_count": official_count,
                "official": official,
                "method": scale.get("method", ""),
            },
        }

    def _api_submit(self, body: dict) -> dict:
        payload = body or {}
        scale_id = str(payload.get("scale_id") or "").strip()
        answers = payload.get("answers") or []
        ids = payload.get("ids") or []
        if not isinstance(answers, list):
            return {"ok": False, "error": "答案格式不对。"}
        scale = get_scale(scale_id)
        items = None
        if scale and isinstance(ids, list) and ids:
            bank = list(scale.get("bank") or scale["items"])
            try:
                items = [bank[int(i)] for i in ids if 0 <= int(i) < len(bank)]
            except Exception:
                items = None
        official = False
        if scale and items is not None:
            official_count = int(scale.get("official_count") or 0)
            official = bool(official_count) and len(items) == official_count
        result = score(scale_id, answers, items=items, official=official) if items else score(scale_id, answers)
        if not result.get("ok"):
            return result
        scale = get_scale(scale_id) or {}
        record = None
        if self._store:
            record = self._store.add(
                scale_id, scale.get("name", scale_id), scale.get("kind", ""), result, answers
            )
        result["record"] = {k: v for k, v in (record or {}).items() if k != "answers"}
        result["crisis_lines"] = CRISIS_LINES if result.get("risk") else []
        return result

    def _api_records(self, body: dict) -> dict:
        if not self._store:
            return {"ok": True, "records": []}
        scale_id = str((body or {}).get("scale_id") or "").strip()
        rows = self._store.list()
        if scale_id:
            rows = [row for row in rows if row.get("scale_id") == scale_id]
        rows = sorted(rows, key=lambda row: row.get("ts", 0), reverse=True)
        return {"ok": True, "records": rows}

    def _api_delete(self, body: dict) -> dict:
        if not self._store:
            return {"ok": False, "error": "存储未就绪。"}
        record_id = str((body or {}).get("id") or "").strip()
        return {"ok": self._store.delete(record_id)}

    def _api_clear(self, _body: dict) -> dict:
        if not self._store:
            return {"ok": False, "error": "存储未就绪。"}
        return {"ok": True, "removed": self._store.clear()}

    def _api_history(self, body: dict) -> dict:
        if not self._store:
            return {"ok": True, "history": []}
        scale_id = str((body or {}).get("scale_id") or "").strip()
        return {"ok": True, "history": self._store.history_for(scale_id)}

    def _api_card(self, body: dict) -> dict:
        """把面板生成的分享卡（PNG base64）存到磁盘——内嵌 webview 里 <a download> 经常被吞掉。"""
        import base64
        import re as _re

        payload = body or {}
        raw = str(payload.get("image") or "").strip()
        if not raw:
            return {"ok": False, "error": "没有收到图片数据。"}
        if raw.startswith("data:"):
            raw = raw.split(",", 1)[-1]
        try:
            blob = base64.b64decode(raw)
        except Exception:
            return {"ok": False, "error": "图片数据解不开。"}
        if not blob:
            return {"ok": False, "error": "图片是空的。"}
        if len(blob) > 12 * 1024 * 1024:
            return {"ok": False, "error": "图片太大。"}

        name = _re.sub(r"[^\w\u4e00-\u9fff-]+", "_", str(payload.get("name") or "result"))[:40]
        stamp = time.strftime("%Y%m%d-%H%M%S")

        # 首选：用户「图片」文件夹（方便直接发出去）；不行就退回插件 data/
        saved_dir = None
        try:
            home = Path.home()
            for candidate in (home / "Pictures", home / "图片", home / "OneDrive" / "Pictures"):
                if candidate.is_dir():
                    saved_dir = candidate / "心理测评室"
                    saved_dir.mkdir(parents=True, exist_ok=True)
                    break
        except Exception:
            saved_dir = None
        if saved_dir is None:
            saved_dir = self._data_dir() / "share_cards"
            try:
                saved_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                return {"ok": False, "error": f"创建目录失败：{exc}"}

        target = saved_dir / f"{stamp}-{name}.png"
        try:
            target.write_bytes(blob)
        except Exception as exc:
            return {"ok": False, "error": f"写入失败：{exc}"}
        self.logger.info("[assessment] 分享卡已保存：{}", target)
        return {"ok": True, "path": str(target), "dir": str(saved_dir), "bytes": len(blob)}

    def _api_export(self, _body: dict) -> dict:
        """导出全部记录（纯文本，便于自己留存或交给专业人士看）。"""
        if not self._store:
            return {"ok": False, "error": "存储未就绪。"}
        rows = self._store.list()
        lines = ["# 心理测评室 · 记录导出", f"# 生成时间：{time.strftime('%Y-%m-%d %H:%M')}", ""]
        for row in rows:
            lines.append(f"[{row.get('time')}] {row.get('name')}")
            if row.get("level"):
                lines.append(f"  等级：{row['level']}（总分 {row.get('total')}）")
            if row.get("type") and isinstance(row["type"], dict):
                lines.append(f"  类型：{row['type'].get('name')}（{row['type'].get('code')}）")
            for dim in row.get("dims", []):
                lines.append(f"  - {dim.get('key')}: {dim.get('score')}（{dim.get('percent')}%）")
            lines.append("")
        lines.append("# 本结果仅供自我了解，不构成医学诊断。")
        return {"ok": True, "text": "\n".join(lines), "count": len(rows)}

    def _prefs_payload(self) -> dict:
        merged = dict(_PREFS_DEFAULT)
        saved = self._prefs if isinstance(self._prefs, dict) else {}
        for key in _PREFS_DEFAULT:
            value = str(saved.get(key) or "").strip()
            if value:
                merged[key] = value[:32]
        return merged

    def _api_prefs(self, body: dict) -> dict:
        prefs = self._prefs_payload()
        payload = body if isinstance(body, dict) else {}
        changed = False
        for key in _PREFS_DEFAULT:
            value = str(payload.get(key) or "").strip()
            if value and value != prefs[key]:
                prefs[key] = value[:32]
                changed = True
        if changed:
            self._prefs = prefs
            save_prefs(self._prefs_path(), prefs)
        background = self._background_state()
        return {"ok": True, "prefs": prefs, "background": background}

    def _background_state(self) -> dict:
        prefs = self._prefs_payload()
        mode = prefs.get("bg_mode", "default")
        if mode not in ("default", "custom", "plain"):
            mode = "default"
        custom = self._bg_file()
        if mode == "custom" and custom is None:
            mode = "default"
        return {
            "mode": mode,
            "dim": prefs.get("bg_dim", "medium"),
            "has_custom": custom is not None,
            "custom_path": "/bg/custom",
        }

    def _bg_asset(self) -> Optional[tuple[bytes, str]]:
        path = self._bg_file()
        if path is None:
            return None
        try:
            return path.read_bytes(), guess_mime(path.name)
        except Exception:
            return None

    def _bg_asset_for(self, rel: str) -> Optional[tuple[bytes, str]]:
        rel = (rel or "").strip().lstrip("/").split("?", 1)[0]
        if rel in ("bg/custom", "bg/custom.jpg", "bg/custom.png"):
            return self._bg_asset()
        return None

    # ── 聊天入口（轻量，方便在对话框里唤起）────────────────────
    @message(id="assessment_chat", source="chat")
    def on_chat_message(self, **kwargs) -> dict:
        """对话框里发「/测评」就把量表清单回给主人（同步方法，与内置插件一致）。"""
        try:
            content = str(kwargs.get("text") or kwargs.get("content") or kwargs.get("message") or "").strip()
            lowered = content.lower()
            triggers = ("/测评", "/心理测评", "/人格测评", "/测试")
            if not any(lowered.startswith(t) or lowered == t for t in triggers):
                return {"ok": True}
            rows = list_scales()
            lines = ["心理测评室 · 可用量表："]
            for row in rows:
                lines.append(f"· {row['name']}（{row['category']}，{row['count']} 题 / 约 {row['minutes']} 分钟）")
            lines.append("")
            lines.append("打开插件面板就能做，结果只存在你本机。")
            lines.append("提醒：这些只作自我了解，不是医学诊断哦～")
            return Ok("\n".join(lines))
        except Exception:
            self.logger.warning("[assessment] 聊天入口异常：{}", traceback.format_exc())
            return {"ok": True}

    @llm_tool(
        name="list_assessments",
        description="列出本机可用的心理 / 人格 / 趣味测评及其简介、题数与来源。",
        parameters={"type": "object", "properties": {}},
        timeout=10.0,
    )
    async def llm_list_assessments(self, **_) -> dict:
        return {"ok": True, "scales": list_scales()}



    def warning(self, *_a, **_k):
        pass


__all__ = ["AssessmentPlugin"]
