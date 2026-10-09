"""心理测评室（neko_assessment）

心理测评 + 人格测评 + 趣味测评，集成在一个面板里：
- 人格/职业量表照搬**公开可复现**的开放工具原题（大五人格用 IPIP/Goldberg 公共领域题库、
  16 型用 OEJTS 1.2、职业兴趣用 O*NET Interest Profiler）；
- 情绪健康用公开筛查工具（PHQ-9、GAD-7、UCLA 简版）；
- 其余量表为本插件自编条目，已在来源里如实标注「自编」；
- 全部数据**只存本机 data/，不上传、不联网**；
- 只作自我了解与反思，**不是医学诊断**。
"""

from __future__ import annotations

import asyncio
import random
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Optional


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
        neko_plugin,
    )

    from . import _compat, _games, _tarot, _yui_link
    from ._engine import score
    from ._panel import PanelServer, find_open_port, guess_mime
    from ._scales import CATEGORIES, CRISIS_LINES, get_scale, list_scales
    from ._store import RecordStore, load_prefs, save_prefs
except Exception:
    _dump_crash("import")
    raise

_PLUGIN_ID = "neko_assessment"
_PANEL_PORT = 15800

# 她的记忆目录：留空 = 自动定位（问宿主 config_manager，再从安装位置上溯）。
# 别人装机位置各不相同，所以**不许写死绝对路径**。
_UI_DEFAULTS = {
    "yui_memory_dir": "",
}

_PREFS_DEFAULT = {
    "ui_font": "system",
    "ui_font_size": "m",
    "ui_trail": "on",
    "bg_mode": "default",
    "bg_dim": "medium",
}


_mark('before-class')


@neko_plugin
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
            # 塔罗：状态文件独立（data/tarot.json），解读任务在后台线程跑
            self._tarot_lock = threading.Lock()
            self._tarot_job: dict[str, Any] = {"status": "idle", "draw_id": "", "text": ""}
            # 解压小游戏：切水果记录 + 电子板本地音源（与测评记录完全分开）
            self._games: Optional[_games.GameStore] = None
            # 默契测试：回合状态机 + YUI 后台作答任务
            self._compat: Optional[_compat.CompatStore] = None
            self._compat_job: dict[str, Any] = {"status": "idle", "round_id": "", "source": ""}
            # 她回的原话（按回合存，揭晓时给面板看——这是"真的她在答"的证据）
            self._compat_reply: dict[str, dict] = {}
            # 每轮开问时的起始时间戳（只认这之后她说的新话）
            self._compat_since_ts: dict[str, str] = {}
            # 她的对话通道：None=还没建，False=定位不到，否则是 YuiDialog
            self._yui_mem: Any = None
            self.yui_memory_dir: str = _UI_DEFAULTS["yui_memory_dir"]
            # 后台线程（等她作答）的停止信号；shutdown 时置位
            self._stop_event = threading.Event()
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
        saved = self._prefs if isinstance(self._prefs, dict) else {}
        name = str(saved.get("bg_file") or "").strip()
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
            self._games = _games.GameStore(self._data_dir() / "games.json", logger=self.logger)
            self._compat = _compat.CompatStore(self._data_dir() / "compat.json", logger=self.logger)
            self._prefs = load_prefs(self._prefs_path())
            if isinstance(self._prefs, dict):
                self.yui_memory_dir = str(self._prefs.get("yui_memory_dir") or "").strip()
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
        try:
            self._stop_event.set()          # 让等她作答的后台线程退出
        except Exception:
            pass
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
            ("GET", "/api/background"): self._api_background,
            ("POST", "/api/background"): self._api_background,
            ("POST", "/api/export"): self._api_export,
            ("POST", "/api/card"): self._api_card,
            ("GET", "/api/tarot"): self._api_tarot_info,
            ("POST", "/api/tarot/draw"): self._api_tarot_draw,
            ("POST", "/api/tarot/interpret"): self._api_tarot_interpret,
            ("GET", "/api/game"): self._api_game,
            ("POST", "/api/game"): self._api_game,
            ("GET", "/api/compat"): self._api_compat,
            ("POST", "/api/compat"): self._api_compat,
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
            raw = dict(self._prefs) if isinstance(self._prefs, dict) else {}
            raw.update(prefs)
            self._save_prefs(raw)
        # 她的记忆目录：可以填、也可以清空（留空 = 自动定位），
        # 所以不能走上面那套「非空且截断到 32 字」的通用逻辑
        if "yui_memory_dir" in payload:
            wanted = str(payload.get("yui_memory_dir") or "").strip()[:260]
            if wanted != self.yui_memory_dir:
                self.yui_memory_dir = wanted
                raw = dict(self._prefs) if isinstance(self._prefs, dict) else {}
                raw["yui_memory_dir"] = wanted
                self._save_prefs(raw)
                self._yui_mem = None          # 改了路径就重新定位
        background = self._background_state()
        return {"ok": True, "prefs": prefs, "background": background,
                "yui_memory_dir": self.yui_memory_dir, "memory": self._yui_stats()}

    def _background_state(self) -> dict:
        prefs = self._prefs_payload()
        mode = prefs.get("bg_mode", "default")
        if mode not in ("default", "custom", "plain"):
            mode = "default"
        custom = self._bg_file()
        if mode == "custom" and custom is None:
            mode = "default"          # 图没了就退回默认，别留一片空白
        return {
            "mode": mode,
            "dim": prefs.get("bg_dim", "medium"),
            "has_custom": custom is not None,
            "custom_bytes": custom.stat().st_size if custom is not None else 0,
            "custom_name": custom.name if custom is not None else "",
            "custom_path": "/bg/custom",
        }

    def _save_prefs(self, prefs: dict) -> None:
        self._prefs = prefs
        save_prefs(self._prefs_path(), prefs)

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
        if rel.startswith("pad-audio/"):            # 用户自备的电子板音源（非商业自用）
            return _games.pad_audio_asset(self.data_dir, rel.split("/", 1)[1])
        return None

    _BG_MAX_BYTES = 8 * 1024 * 1024
    _BG_MIME_EXT = {
        "image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg",
        "image/webp": ".webp", "image/gif": ".gif",
    }

    def _api_background(self, body: dict) -> dict:
        """上传 / 切换 / 恢复自定义背景。图存 data/backgrounds/，不进安装包。"""
        import base64

        payload = body if isinstance(body, dict) else {}
        action = str(payload.get("action") or "").strip() or "mode"
        prefs = dict(self._prefs) if isinstance(self._prefs, dict) else {}
        if action == "upload":
            raw = str(payload.get("image_base64") or payload.get("image") or "").strip()
            if not raw:
                return {"ok": False, "error": "没有收到图片数据。", "background": self._background_state()}
            if raw.startswith("data:"):
                head, _, encoded = raw.partition(",")
                mime = head[5:].split(";")[0].strip().lower()
            else:
                encoded, mime = raw, "image/png"
            ext = self._BG_MIME_EXT.get(mime)
            if not ext:
                return {"ok": False, "error": f"不支持的格式：{mime or '未知'}", "background": self._background_state()}
            try:
                blob = base64.b64decode(encoded or "", validate=False)
            except Exception:
                return {"ok": False, "error": "图片数据解不开。", "background": self._background_state()}
            if not blob:
                return {"ok": False, "error": "图片是空的。", "background": self._background_state()}
            if len(blob) > self._BG_MAX_BYTES:
                return {"ok": False, "error": f"图片超过 {self._BG_MAX_BYTES // 1048576}MB 限制。", "background": self._background_state()}
            for suffix in (".png", ".jpg", ".webp", ".gif"):
                stale = self._bg_dir() / f"custom{suffix}"
                if stale.is_file():
                    try:
                        stale.unlink()
                    except Exception:
                        pass
            target = self._bg_dir() / f"custom{ext}"
            try:
                target.write_bytes(blob)
            except Exception as exc:
                return {"ok": False, "error": str(exc), "background": self._background_state()}
            prefs["bg_mode"] = "custom"
            prefs["bg_file"] = target.name
            self._save_prefs(prefs)
            return {"ok": True, "message": "背景已换成你上传的图。", "background": self._background_state()}
        if action == "reset":
            prefs["bg_mode"] = "default"
            self._save_prefs(prefs)
            return {"ok": True, "message": "已恢复默认背景。", "background": self._background_state()}
        mode = str(payload.get("mode") or "").strip() or str(prefs.get("bg_mode") or "default")
        if mode not in ("default", "custom", "plain"):
            return {"ok": False, "error": f"未知模式：{mode}", "background": self._background_state()}
        if mode == "custom" and self._bg_file() is None:
            return {"ok": False, "error": "还没上传过背景图。", "background": self._background_state()}
        prefs["bg_mode"] = mode
        dim = str(payload.get("dim") or "").strip()
        if dim in ("light", "medium", "strong"):
            prefs["bg_dim"] = dim
        self._save_prefs(prefs)
        return {"ok": True, "background": self._background_state()}

    # ── 解压小游戏（从学习辅助猫娘移植；与测评记录完全分开）──────
    def _api_game(self, body: dict) -> dict:
        """切水果：取规则 / 取记录 / 交成绩；电子板：扫本地音源 / 导入音源。"""
        if self._games is None:
            return {"ok": False, "error": "游戏存储未就绪。"}
        payload = body if isinstance(body, dict) else {}
        action = str(payload.get("action") or "state").strip() or "state"
        game = str(payload.get("game") or _games.GAME_FRUIT).strip() or _games.GAME_FRUIT
        if action == "config":
            config = self._games.config()
            config["local_audio"] = _games.scan_pad_audio(self.data_dir)
            config["local_audio_dir"] = f"data/{_games.PAD_AUDIO_DIR}"
            return {"ok": True, "config": config, "state": self._games.state(game)}
        if action in ("import-audio", "import_audio"):
            files = payload.get("files")
            if not isinstance(files, list) or not files:
                return {"ok": False, "error": "没有收到音源文件。"}
            saved, skipped = self._import_pad_audio(files)
            return {
                "ok": True,
                "saved": saved,
                "skipped": skipped,
                "files": _games.scan_pad_audio(self.data_dir),
                "dir": f"data/{_games.PAD_AUDIO_DIR}",
            }
        if action in ("pad-audio", "pad_audio"):
            return {
                "ok": True,
                "files": _games.scan_pad_audio(self.data_dir),
                "dir": f"data/{_games.PAD_AUDIO_DIR}",
                "note": (
                    "把你自己有的音源（mp3/ogg/wav）放进插件 data/"
                    f"{_games.PAD_AUDIO_DIR}/ 就会自动用上；这些文件不会被打进安装包。"
                ),
            }
        if action == "submit":
            run = payload.get("run")
            if not isinstance(run, dict):
                return {"ok": False, "error": "没有收到成绩数据。", "state": self._games.state(game)}
            return self._games.submit(run, game)
        return {"ok": True, "state": self._games.state(game), "config": self._games.config()}

    _AUDIO_MAX_BYTES = 8 * 1024 * 1024

    def _import_pad_audio(self, files: list) -> tuple[int, int]:
        """把用户在面板里选的本机音源写进 data/mikutap_audio/。

        文件是用户自己在自己机器上选的，插件只负责存到自己的数据目录，
        发行包里不含任何音频。单文件上限 8MB、总数上限 120 个，避免误选整个音乐库。
        """
        import base64

        target_dir = _games.pad_audio_dir(self.data_dir)
        saved = 0
        skipped = 0
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self.logger.warning("[assessment] 音源目录创建失败：{}", exc)
            return 0, len(files)
        for item in files[:120]:
            if not isinstance(item, dict):
                skipped += 1
                continue
            name = Path(str(item.get("name") or "")).name
            if not name or Path(name).suffix.lower() not in _games.AUDIO_EXTS:
                skipped += 1
                continue
            raw = str(item.get("data") or item.get("data_base64") or "").strip()
            if not raw:
                skipped += 1
                continue
            _, _, encoded = raw.partition(",")
            try:
                blob = base64.b64decode(encoded or raw, validate=False)
            except Exception:
                skipped += 1
                continue
            if not blob or len(blob) > self._AUDIO_MAX_BYTES:
                skipped += 1
                continue
            try:
                (target_dir / name).write_bytes(blob)
                saved += 1
            except Exception:
                skipped += 1
        self.logger.info("[assessment] 本地音源导入：成功 {}，跳过 {}", saved, skipped)
        return saved, skipped

    # ── 默契测试（你和 YUI 的默契度；机制复刻、题库自写）────────
    # ── 默契测试：请她本人作答，再把她的回答读回来 ─────────────────
    #
    # 为什么不是「把她的记忆注入 prompt、让模型替她答」：
    # 那样答话的是**插件**，只是套了她的人设和记忆——她既不知道自己在答题，
    # 用的也不是她自己真实的对话上下文。现在的做法是：
    #   插件把题目推进对话（ai_behavior="respond"）→ 宿主用**她本人**
    #   （人设 / 记忆 / 上下文）生成回复，屏幕上就是她在说话 →
    #   宿主把这一轮写进 time_indexed.db → 插件按时间戳把她的回复读回来解析。
    # 这样答案是她自己下的，而且她天然就记得——因为那就是她真实的对话。
    _COMPAT_WAIT_SECONDS = 120.0        # 等她作答的最长时间
    _COMPAT_POLL_SECONDS = 2.0

    def _yui_dialog(self) -> Any:
        """她的对话通道（懒建）。定位不到就是 None——**如实回报，绝不猜一个路径硬用**。"""
        if self._yui_mem is None:
            try:
                explicit = str(getattr(self, "yui_memory_dir", "") or "").strip()
                path, source = _yui_link.resolve_yui_dir(explicit, [str(self._data_dir())])
                self._yui_mem = _yui_link.YuiDialog(path, source)
            except Exception as exc:
                self.logger.warning("[assessment] 定位她的对话库失败：{}", exc)
                self._yui_mem = False
        return self._yui_mem or None

    def _yui_stats(self) -> dict:
        dlg = self._yui_dialog()
        if dlg is None:
            return {"available": False, "reason": "没定位到她的记忆目录"}
        try:
            return dlg.stats()
        except Exception as exc:
            return {"available": False, "reason": str(exc)}

    def _compat_ask_text(self, question_ids: list[str]) -> str:
        """推给她的那段话：讲清玩法 + 题目 + 严格的输出格式。"""
        lines = [
            "主人想和你玩默契测试，要你先答一份喵。",
            "每题选两个数字：先选**你自己**会选的那个，再猜**主人**会选哪个。序号从 0 开始。",
            "答完只回一段 JSON，不要解释、不要多余的话，形如：",
            '{"own": [0,1,2,...], "guess": [0,1,2,...]}',
            "",
        ]
        for i, qid in enumerate(question_ids, 1):
            pub = _compat.question_public(qid) or {}
            opts = "；".join(f"{j}.{o}" for j, o in enumerate(pub.get("options") or []))
            lines.append(f"{i}. {pub.get('text', '')} 选项：{opts}")
        lines.append("")
        lines.append(f"一共 {len(question_ids)} 题，own 和 guess 各要 {len(question_ids)} 个数字。")
        return "\n".join(lines)

    def _compat_push_now(self, question_ids: list[str]) -> None:
        """把题目推进对话，请她本人作答。失败要抛出去，让面板如实显示。"""
        text = self._compat_ask_text(question_ids)
        result = self.ctx.push_message(
            source=_PLUGIN_ID,
            visibility=["chat"],
            ai_behavior="respond",
            parts=[{"type": "text", "text": text}],
            priority=5,
            metadata={"description": "🐾 默契测试：请 YUI 本人作答"},
        )
        if asyncio.iscoroutine(result):
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(result)
            finally:
                loop.close()

    def _compat_since(self, dlg: Any) -> str:
        """本次要盯的起始时间戳：库里最新一条；取不到就用本机当前时间。"""
        if dlg is not None:
            try:
                got = dlg.latest_ts()
                if got:
                    return str(got)
            except Exception:
                pass
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def _compat_watch_worker(self, round_id: str) -> None:
        """后台线程：请她作答 → 等她回答 → 从她的对话库里读回来解析。"""
        try:
            entry = self._compat.get(round_id)
            if not entry:
                return
            qids = entry["question_ids"]
            dlg = self._yui_dialog()
            since = self._compat_since(dlg)
            self._compat_since_ts[round_id] = since

            try:
                self._compat_push_now(qids)
            except Exception as exc:
                self.logger.warning("[assessment] 把题目推给她失败：{}", traceback.format_exc())
                self._compat_job = {"status": "push_failed", "round_id": round_id,
                                    "source": "", "reason": f"{exc}"}
                return

            if dlg is None or not dlg.available:
                self._compat_job = {"status": "no_dialog", "round_id": round_id, "source": "",
                                    "reason": (dlg.source if dlg else "没定位到她的记忆目录")}
                return
            self._compat_job = {"status": "asking", "round_id": round_id, "source": "herself"}

            deadline = time.time() + self._COMPAT_WAIT_SECONDS
            while time.time() < deadline:
                stop = getattr(self, "_stop_event", None)
                if stop is not None and stop.is_set():
                    return
                got = dlg.find_answers(since, want=len(qids))
                if got:
                    self._compat.set_yui(
                        round_id, {"own": got["own"], "guess": got["guess"]}, "herself")
                    self._compat_reply[round_id] = {"text": got["reply"], "ts": got["ts"]}
                    self._compat_job = {"status": "done", "round_id": round_id, "source": "herself"}
                    self.logger.info("[assessment] 她自己答完了默契测试：{}", round_id)
                    return
                if stop is not None:
                    stop.wait(self._COMPAT_POLL_SECONDS)
                else:
                    time.sleep(self._COMPAT_POLL_SECONDS)

            self._compat_job = {"status": "timeout", "round_id": round_id, "source": "",
                                "reason": f"等了 {int(self._COMPAT_WAIT_SECONDS)} 秒没等到她的回复"}
        except Exception as exc:
            self.logger.warning("[assessment] 等她作答的线程异常：{}", traceback.format_exc())
            self._compat_job = {"status": "error", "round_id": round_id, "source": f"{exc}"}

    def _compat_start_round(self, question_ids: list[str]) -> dict:
        round_id = uuid.uuid4().hex[:10]
        entry = self._compat.start_round(round_id, question_ids)
        self._compat_job = {"status": "asking", "round_id": round_id, "source": "herself"}
        threading.Thread(target=self._compat_watch_worker, args=(round_id,),
                         daemon=True, name="neko-assess-compat").start()
        return entry

    def _api_compat(self, body: dict) -> dict:
        """默契测试：开回合 / 交卷 / 揭晓 / 重问 / 历史。双方交卷前绝不返回她的答案。"""
        if self._compat is None:
            return {"ok": False, "error": "默契存储未就绪。"}
        payload = body if isinstance(body, dict) else {}
        action = str(payload.get("action") or "info").strip() or "info"

        if action == "start":
            qids = _compat.sample_questions()
            entry = self._compat_start_round(qids)
            return {
                "ok": True,
                "round": {
                    "id": entry["id"],
                    "questions": [_compat.question_public(q) for q in qids],
                },
                "job": dict(self._compat_job),
                "note": "题目已经发给她了，她会用自己的身份在对话里回答；你在这边同时答你的。",
            }

        if action == "ask_again":
            round_id = str(payload.get("round_id") or "").strip()
            entry = self._compat.get(round_id)
            if entry is None:
                return {"ok": False, "error": "没有找到这一轮，可能已经换新一轮了。"}
            if entry.get("yui"):
                return {"ok": True, "status": entry["status"], "job": dict(self._compat_job),
                        "note": "她已经答过了。"}
            self._compat_job = {"status": "asking", "round_id": round_id, "source": "herself"}
            threading.Thread(target=self._compat_watch_worker, args=(round_id,),
                             daemon=True, name="neko-assess-compat").start()
            return {"ok": True, "job": dict(self._compat_job), "note": "又问她了一次。"}

        if action == "submit":
            round_id = str(payload.get("round_id") or "").strip()
            entry = self._compat.get(round_id)
            if entry is None:
                return {"ok": False, "error": "没有找到这一轮，可能已经换新一轮了。"}
            answers = _compat.validate_answers(entry["question_ids"], payload.get("answers"))
            if answers is None:
                return {"ok": False, "error": "答案格式不对：每题都要选自己的、再猜 YUI 的。"}
            entry = self._compat.set_self(round_id, answers)
            if entry is None:
                return {"ok": False, "error": "这一轮已经结束了，重新开一轮吧。"}
            return {"ok": True, "status": entry["status"], "job": dict(self._compat_job)}

        if action == "reveal":
            round_id = str(payload.get("round_id") or "").strip()
            entry = self._compat.reveal(round_id)
            if entry is None:
                return {"ok": False, "error": "没有找到这一轮。"}
            if entry.get("status") != "revealed":
                # 双方没交齐：只说在等，不给任何答案
                return {"ok": True, "status": "waiting", "job": dict(self._compat_job),
                        "yui_answered": bool(entry.get("yui"))}
            return {
                "ok": True,
                "status": "revealed",
                "round_id": round_id,
                "yui_source": entry.get("yui_source") or "",
                # 她原话。面板会把它显示出来——这是"真的她在答"最直接的证据
                "yui_reply": self._compat_reply.get(round_id) or {},
                "result": entry["result"],
                "job": dict(self._compat_job),
            }

        return {
            "ok": True,
            "history": self._compat.history(),
            "job": dict(self._compat_job),
            "memory": self._yui_stats(),
        }
    # ── 猫娘塔罗 ───────────────────────────────────────────────
    _TAROT_SYSTEM = (
        "你是猫娘塔罗解读师，用猫娘口吻解读塔罗牌。规则："
        "1. 只依据给出的牌名、正逆位与传统关键词解读，不许编造关键词以外的信息；"
        "2. 语气温柔俏皮，自称本喵，称呼用户为主人；"
        "3. 逐张牌简短解读后，给一段整体总结和一条具体建议；"
        "4. 全文 300 字以内，纯文本，不要任何列表符号或标题格式。"
    )

    def _tarot_path(self) -> Path:
        return self._data_dir() / "tarot.json"

    def _tarot_read(self) -> dict:
        import json

        try:
            data = json.loads(self._tarot_path().read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _tarot_write(self, state: dict) -> None:
        """原子写：.tmp → os.replace，绝不出现半截 JSON。"""
        import json
        import os

        self._tarot_path().parent.mkdir(parents=True, exist_ok=True)
        tmp = self._tarot_path().with_name("tarot.json.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._tarot_path())

    def _tarot_update(self, mutate) -> None:
        with self._tarot_lock:
            state = self._tarot_read()
            try:
                mutate(state)
                self._tarot_write(state)
            except Exception as exc:
                self.logger.warning("[assessment] 塔罗状态写入失败：{}", exc)

    def _api_tarot_info(self, _body: dict) -> dict:
        state = self._tarot_read()
        history = state.get("history")
        history = history if isinstance(history, list) else []
        readings = state.get("readings")
        readings = readings if isinstance(readings, dict) else {}
        interprets = {
            str(k): (v.get("interpret") if isinstance(v, dict) else "")
            for k, v in readings.items()
        }
        return {
            "ok": True,
            "spreads": _tarot.spread_meta(),
            "history": history[:_tarot._MAX_HISTORY],
            "interprets": interprets,
            "job": self._tarot_job,
        }

    def _api_tarot_draw(self, body: dict) -> dict:
        payload = body if isinstance(body, dict) else {}
        spread_id = str(payload.get("spread") or "").strip() or "three"
        question = str(payload.get("question") or "").strip()
        drawn = _tarot.draw(spread_id, question)
        if drawn is None:
            return {"ok": False, "error": f"未知牌阵：{spread_id}", "spreads": _tarot.spread_meta()}
        draw_id = uuid.uuid4().hex[:10]
        entry = {
            "id": draw_id,
            "ts": int(time.time()),
            "interpret": "",
            "interpret_kind": "",
            **drawn,
        }

        def mutate(state: dict) -> None:
            history = state.setdefault("history", [])
            if isinstance(history, list):
                history.insert(0, {
                    k: entry[k] for k in
                    ("id", "ts", "spread", "spread_name", "question", "cards")
                })
                del history[_tarot._MAX_HISTORY:]
            readings = state.setdefault("readings", {})
            readings[draw_id] = entry
            keep = {h.get("id") for h in history if isinstance(h, dict)}
            for k in [k for k in readings if k not in keep]:
                readings.pop(k, None)

        self._tarot_update(mutate)
        return {"ok": True, "draw": entry, "job": self._tarot_job}

    def _api_tarot_interpret(self, body: dict) -> dict:
        payload = body if isinstance(body, dict) else {}
        draw_id = str(payload.get("draw_id") or "").strip()
        entry = self._tarot_read().get("readings", {}).get(draw_id)
        if not isinstance(entry, dict):
            return {"ok": False, "error": "没有找到这次占卜的记录喵，重新抽一次吧。", "job": self._tarot_job}
        if self._tarot_job.get("status") == "running" and self._tarot_job.get("draw_id") == draw_id:
            return {"ok": True, "job": self._tarot_job}
        if str(entry.get("interpret") or "").strip():
            # 已有解读：直接回，不再花一次模型钱
            self._tarot_job = {
                "status": "done", "draw_id": draw_id,
                "text": entry["interpret"], "kind": entry.get("interpret_kind") or "llm",
            }
            return {"ok": True, "job": self._tarot_job}
        self._tarot_job = {"status": "running", "draw_id": draw_id, "text": ""}
        threading.Thread(
            target=self._tarot_worker, args=(draw_id,), daemon=True, name="neko-assess-tarot"
        ).start()
        return {"ok": True, "job": self._tarot_job}

    def _tarot_worker(self, draw_id: str) -> None:
        """后台线程：私有事件循环调 LLM，绝不碰宿主循环。"""
        try:
            entry = self._tarot_read().get("readings", {}).get(draw_id) or {}
            drawn = {
                "question": entry.get("question", ""),
                "spread_name": entry.get("spread_name", ""),
                "cards": entry.get("cards", []),
            }
            text, kind = "", "llm"
            try:
                loop = asyncio.new_event_loop()
                try:
                    text = loop.run_until_complete(self._tarot_llm(drawn))
                finally:
                    loop.close()
            except Exception as exc:
                self.logger.warning("[assessment] 塔罗 LLM 解读失败，降级为牌义摆盘：{}", exc)
                text, kind = _tarot.fallback_reading(drawn), "fallback"
            if not str(text or "").strip():
                text, kind = _tarot.fallback_reading(drawn), "fallback"
            self._tarot_job = {
                "status": "done", "draw_id": draw_id, "text": text, "kind": kind,
            }

            def mutate(state: dict) -> None:
                readings = state.setdefault("readings", {})
                if isinstance(readings.get(draw_id), dict):
                    readings[draw_id]["interpret"] = text
                    readings[draw_id]["interpret_kind"] = kind

            self._tarot_update(mutate)
        except Exception as exc:
            self.logger.warning("[assessment] 塔罗解读线程异常：{}", traceback.format_exc())
            self._tarot_job = {"status": "error", "draw_id": draw_id, "text": f"解读出了点问题：{exc}"}

    async def _llm_chat(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        """塔罗与默契共用的模型调用：llm_client 优先，失败直连 /chat/completions。"""
        cfg: dict[str, Any] = {}
        try:
            from utils.config_manager import get_config_manager

            cfg = get_config_manager().get_model_api_config("conversation")
            cfg = cfg if isinstance(cfg, dict) else {}
        except Exception as exc:
            self.logger.info("[assessment] 读取模型配置失败：{}", exc)
        model = str(cfg.get("model") or "").strip()
        base_url = str(cfg.get("base_url") or "").strip().rstrip("/")
        api_key = str(cfg.get("api_key") or "").strip()
        if not (model and base_url and api_key):
            raise RuntimeError("尚未配置会话模型")

        # 优先官方 llm_client；TypeError 兼容无 provider_type 参数的旧签名
        try:
            from utils.llm_client import create_chat_llm_async

            kwargs: dict[str, Any] = {
                "model": model, "base_url": base_url, "api_key": api_key,
                "max_completion_tokens": max_tokens, "timeout": 60.0,
            }
            try:
                llm = create_chat_llm_async(**kwargs)
            except TypeError:
                provider_type = str(cfg.get("provider_type") or "").strip() or None
                if provider_type:
                    kwargs["provider_type"] = provider_type
                llm = create_chat_llm_async(**kwargs)
            result = await asyncio.wait_for(
                llm.ainvoke([
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ]),
                timeout=60.0,
            )
            text = getattr(result, "content", None) or str(result or "")
            if str(text).strip():
                return str(text).strip()
            raise RuntimeError("模型返回为空")
        except ImportError:
            pass
        except Exception as exc:
            self.logger.warning("[assessment] llm_client 调用失败，降级直连：{}", exc)
        return await asyncio.to_thread(self._llm_chat_http, base_url, api_key, model, system, user, max_tokens)

    def _llm_chat_http(self, base_url: str, api_key: str, model: str,
                       system: str, user: str, max_tokens: int) -> str:
        import json
        import urllib.error
        import urllib.request

        endpoint = f"{base_url}/chat/completions"
        body = json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_completion_tokens": max_tokens,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60.0) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"模型请求失败：HTTP {exc.code}") from exc
        except Exception as exc:
            raise RuntimeError(f"模型请求失败：{exc}") from exc
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("模型没有返回内容")
        return str((choices[0].get("message") or {}).get("content") or "").strip()

    async def _tarot_llm(self, drawn: dict) -> str:
        return await self._llm_chat(self._TAROT_SYSTEM, "\n".join(_tarot.card_lines(drawn)))

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
