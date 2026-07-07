import argparse, asyncio, importlib.util, json, os, queue as Q, re, sys, threading, time, uuid
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

import traceback
import lark_oapi as lark
from lark_oapi.api.im.v1 import *


def _ensure_dir(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _workspace_root_dir():
    root = os.environ.get("GA_WORKSPACE_ROOT")
    if root:
        return _ensure_dir(Path(root).expanduser().resolve())
    return _ensure_dir(Path(PROJECT_ROOT).resolve())


def _workspace_config_dir(root=None):
    base = Path(root).expanduser().resolve() if root else _workspace_root_dir()
    if base.name == "ga_config":
        return _ensure_dir(base)
    return _ensure_dir(base / "ga_config")


def _load_dict_config(path):
    path = Path(path)
    if not path.exists():
        return None
    try:
        if path.suffix == ".py":
            mod_name = f"_fs_mykey_{uuid.uuid4().hex}"
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if not spec or not spec.loader:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            data = {k: v for k, v in vars(module).items() if not k.startswith("_")}
        else:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception as e:
        print(f"[ERROR] load config failed {path}: {e}")
        return None


def _resolve_mykey_path():
    workspace_root = _workspace_root_dir()
    config_root = _workspace_config_dir(workspace_root)
    candidates = [
        config_root / "mykey.json",
        config_root / "mykey.py",
        workspace_root / "mykey.json",
        workspace_root / "mykey.py",
        Path(PROJECT_ROOT) / "mykey.json",
        Path(PROJECT_ROOT) / "mykey.py",
    ]
    for candidate in candidates:
        if _load_dict_config(candidate):
            return candidate
    return candidates[0]


def _ensure_runtime_paths():
    workspace_root = _workspace_root_dir()
    config_root = _workspace_config_dir(workspace_root)
    os.environ.setdefault("GA_WORKSPACE_ROOT", str(workspace_root))
    os.environ.setdefault("GA_USER_DATA_DIR", str(config_root))
    return str(workspace_root), str(config_root)


_ensure_runtime_paths()
from agentmain import GeneraticAgent
import frontends.chatapp_common as chat_common
from frontends.aegis_mesh_sessions import (
    DEFAULT_AEGIS_REPORT_INTERVAL_SEC,
    AegisMeshPeriodicReporter,
    AegisMeshSessionManager,
    build_feishu_session_id,
    render_dashboard_text,
    render_periodic_report_text,
    render_session_status_text,
)
from frontends.chatapp_common import AgentChatMixin, FILE_HINT
from frontends.message_delivery import build_delivery_envelope, render_artifact_index, render_feishu_digest
from frontends.outbox_store import read_chunk, read_full, read_manifest, write_artifact
from frontends.platform_budgets import build_digest, sanitize_for_im, segment_markdown

_TAG_PATS = [r"<" + t + r">.*?</" + t + r">" for t in ("thinking", "summary", "tool_use", "file_content")]
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".tiff", ".tif"}
_AUDIO_EXTS = {".opus", ".mp3", ".wav", ".m4a", ".aac"}
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
_FILE_TYPE_MAP = {
    ".opus": "opus",
    ".mp4": "mp4",
    ".pdf": "pdf",
    ".doc": "doc",
    ".docx": "doc",
    ".xls": "xls",
    ".xlsx": "xls",
    ".ppt": "ppt",
    ".pptx": "ppt",
}
_MSG_TYPE_MAP = {"image": "[image]", "audio": "[audio]", "file": "[file]", "media": "[media]", "sticker": "[sticker]"}
_FEISHU_HELP_TEXT = (
    chat_common.HELP_TEXT
    + "\n/report - 立即发送当前会话摘要"
    + "\n/summary - 同上"
    + "\n/full [task_id] - 取回最近任务或指定任务的完整输出"
    + "\n/chunk [task_id] <n> - 取回指定输出分片"
    + "\n/artifacts [task_id] - 查看任务产物索引"
    + "\n/more - 取回最近任务的下一个分片"
)

TEMP_DIR = os.path.join(PROJECT_ROOT, "temp")
MEDIA_DIR = os.path.join(TEMP_DIR, "feishu_media")
OUTPUT_DIR = os.path.join(TEMP_DIR, "feishu_outputs")
os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


_TRUNC_TAIL = 300  # 截断兜底时保留原文尾部字符数
_TASKCARD_FINAL_PREVIEW_LIMIT = 1200
_FEISHU_INLINE_RESULT_LIMIT = 12000
_DEDUP_TTL_SEC = 10 * 60
_DEDUP_MAX = 2000
_DEDUP_LOCK = threading.Lock()
_SEEN_MESSAGES = {}


def _claim_message_once(message_id):
    """Best-effort cross-platform dedup for Feishu reconnect redeliveries."""
    if not message_id:
        return True
    now = time.time()
    with _DEDUP_LOCK:
        expired = [mid for mid, ts in _SEEN_MESSAGES.items() if now - ts > _DEDUP_TTL_SEC]
        for mid in expired:
            _SEEN_MESSAGES.pop(mid, None)
        if len(_SEEN_MESSAGES) > _DEDUP_MAX:
            for mid, _ in sorted(_SEEN_MESSAGES.items(), key=lambda item: item[1])[:len(_SEEN_MESSAGES) - _DEDUP_MAX]:
                _SEEN_MESSAGES.pop(mid, None)
        if message_id in _SEEN_MESSAGES:
            return False
        _SEEN_MESSAGES[message_id] = now
        return True


def _clean(text):
    for pat in _TAG_PATS:
        text = re.sub(pat, "", text or "", flags=re.DOTALL)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _extract_files(text):
    return re.findall(r"\[FILE:([^\]]+)\]", text or "")


def _strip_files(text):
    return re.sub(r"\[FILE:[^\]]+\]", "", text or "").strip()


def _display_text(text):
    cleaned = _strip_files(_clean(text))
    if cleaned:
        return cleaned
    tail = (text or "").strip()[-_TRUNC_TAIL:]
    return "⚠️ 模型输出被截断或为空" + (f"\n…{tail}" if tail else "")


def _result_summary(text, max_len=240):
    summary = re.sub(r"\s+", " ", _display_text(text)).strip()
    if len(summary) <= max_len:
        return summary
    return summary[: max_len - 1].rstrip() + "…"


def _segment_for_im(text, limit):
    return segment_markdown(sanitize_for_im(text), limit=limit)


def _build_markdown_post_rows(content):
    """Build Feishu post rows from Markdown, isolating fenced code blocks.

    Feishu `text` messages do not render Markdown.  Hermes-agent sends
    Feishu rich text as msg_type=post with `md` elements; split around
    fenced code blocks so a large md element cannot swallow following prose.
    """
    text = sanitize_for_im(content)
    if not text:
        return [[{"tag": "md", "text": ""}]]
    if "```" not in text:
        return [[{"tag": "md", "text": text}]]

    rows = []
    current = []
    in_code_block = False

    def flush_current():
        nonlocal current
        if not current:
            return
        segment = "\n".join(current)
        if segment.strip():
            rows.append([{"tag": "md", "text": segment}])
        current = []

    for raw_line in text.splitlines():
        stripped = raw_line.lstrip()
        is_fence = stripped.startswith("```")
        if is_fence and not in_code_block:
            flush_current()
            current.append(raw_line)
            in_code_block = True
            continue
        current.append(raw_line)
        if is_fence and in_code_block:
            flush_current()
            in_code_block = False

    flush_current()
    return rows or [[{"tag": "md", "text": text}]]


def _post(text):
    return json.dumps({"zh_cn": {"content": _build_markdown_post_rows(text)}}, ensure_ascii=False)


def _to_allowed_set(value):
    if value is None:
        return set()
    if isinstance(value, str):
        value = [value]
    return {str(x).strip() for x in value if str(x).strip()}


def _parse_json(raw):
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _extract_share_card_content(content_json, msg_type):
    parts = []
    if msg_type == "share_chat":
        parts.append(f"[shared chat: {content_json.get('chat_id', '')}]")
    elif msg_type == "share_user":
        parts.append(f"[shared user: {content_json.get('user_id', '')}]")
    elif msg_type == "interactive":
        parts.extend(_extract_interactive_content(content_json))
    elif msg_type == "share_calendar_event":
        parts.append(f"[shared calendar event: {content_json.get('event_key', '')}]")
    elif msg_type == "system":
        parts.append("[system message]")
    elif msg_type == "merge_forward":
        parts.append("[merged forward messages]")
    return "\n".join([p for p in parts if p]).strip() or f"[{msg_type}]"


def _extract_interactive_content(content):
    parts = []
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except Exception:
            return [content] if content.strip() else []
    if not isinstance(content, dict):
        return parts
    title = content.get("title")
    if isinstance(title, dict):
        title_text = title.get("content", "") or title.get("text", "")
        if title_text:
            parts.append(f"title: {title_text}")
    elif isinstance(title, str) and title:
        parts.append(f"title: {title}")
    elements = content.get("elements", [])
    if isinstance(elements, list):
        for row in elements:
            if isinstance(row, dict):
                parts.extend(_extract_element_content(row))
            elif isinstance(row, list):
                for el in row:
                    parts.extend(_extract_element_content(el))
    card = content.get("card", {})
    if card:
        parts.extend(_extract_interactive_content(card))
    header = content.get("header", {})
    if isinstance(header, dict):
        header_title = header.get("title", {})
        if isinstance(header_title, dict):
            header_text = header_title.get("content", "") or header_title.get("text", "")
            if header_text:
                parts.append(f"title: {header_text}")
    return [p for p in parts if p]


def _extract_element_content(element):
    parts = []
    if not isinstance(element, dict):
        return parts
    tag = element.get("tag", "")
    if tag in ("markdown", "lark_md"):
        content = element.get("content", "")
        if content:
            parts.append(content)
    elif tag == "div":
        text = element.get("text", {})
        if isinstance(text, dict):
            text_content = text.get("content", "") or text.get("text", "")
            if text_content:
                parts.append(text_content)
        elif isinstance(text, str) and text:
            parts.append(text)
        for field in element.get("fields", []) or []:
            if isinstance(field, dict):
                field_text = field.get("text", {})
                if isinstance(field_text, dict):
                    content = field_text.get("content", "") or field_text.get("text", "")
                    if content:
                        parts.append(content)
    elif tag == "a":
        href = element.get("href", "")
        text = element.get("text", "")
        if href:
            parts.append(f"link: {href}")
        if text:
            parts.append(text)
    elif tag == "button":
        text = element.get("text", {})
        if isinstance(text, dict):
            content = text.get("content", "") or text.get("text", "")
            if content:
                parts.append(content)
        url = element.get("url", "") or (element.get("multi_url", {}) or {}).get("url", "")
        if url:
            parts.append(f"link: {url}")
    elif tag == "img":
        alt = element.get("alt", {})
        if isinstance(alt, dict):
            parts.append(alt.get("content", "[image]") or "[image]")
        else:
            parts.append("[image]")
    for child in element.get("elements", []) or []:
        parts.extend(_extract_element_content(child))
    for col in element.get("columns", []) or []:
        for child in (col.get("elements", []) if isinstance(col, dict) else []):
            parts.extend(_extract_element_content(child))
    return parts


def _extract_post_content(content_json):
    def _parse_block(block):
        if not isinstance(block, dict) or not isinstance(block.get("content"), list):
            return None, []
        texts, images = [], []
        if block.get("title"):
            texts.append(block.get("title"))
        for row in block["content"]:
            if not isinstance(row, list):
                continue
            for el in row:
                if not isinstance(el, dict):
                    continue
                tag = el.get("tag")
                if tag in ("text", "a"):
                    texts.append(el.get("text", ""))
                elif tag == "at":
                    texts.append(f"@{el.get('user_name', 'user')}")
                elif tag == "img" and el.get("image_key"):
                    images.append(el["image_key"])
        text = " ".join([t for t in texts if t]).strip()
        return text or None, images

    root = content_json
    if isinstance(root, dict) and isinstance(root.get("post"), dict):
        root = root["post"]
    if not isinstance(root, dict):
        return "", []
    if "content" in root:
        text, imgs = _parse_block(root)
        if text or imgs:
            return text or "", imgs
    for key in ("zh_cn", "en_us", "ja_jp"):
        if key in root:
            text, imgs = _parse_block(root[key])
            if text or imgs:
                return text or "", imgs
    for val in root.values():
        if isinstance(val, dict):
            text, imgs = _parse_block(val)
            if text or imgs:
                return text or "", imgs
    return "", []


AGENT_TIMEOUT_SEC = 900

agent = None
agent_error = None
session_manager = None
periodic_reporter = None
client, user_tasks, app = None, {}, None
agent_lock = threading.RLock()
reporter_lock = threading.Lock()


def _load_config():
    if os.environ.get("AVATAR_SKIP_CONFIG_LOAD") == "1":
        return {}, ""
    path = _resolve_mykey_path()
    if not path or not path.exists():
        return {}, str(path or "")
    try:
        data = _load_dict_config(path)
        return data if isinstance(data, dict) else {}, str(path)
    except Exception as e:
        print(f"[ERROR] load mykey failed {path}: {e}")
        return {}, str(path)


def _feishu_config():
    cfg, path = _load_config()
    app_id = str(cfg.get("fs_app_id", "") or "").strip()
    app_secret = str(cfg.get("fs_app_secret", "") or "").strip()
    allowed = _to_allowed_set(cfg.get("fs_allowed_users", []))
    return app_id, app_secret, allowed, (not allowed or "*" in allowed), path


def _coerce_report_interval(raw):
    try:
        return max(0, int(float(raw)))
    except (TypeError, ValueError):
        return DEFAULT_AEGIS_REPORT_INTERVAL_SEC


def _aegis_report_interval_sec():
    cfg, _ = _load_config()
    raw = os.environ.get("FS_AEGIS_REPORT_INTERVAL_SEC")
    if raw is None:
        raw = cfg.get(
            "fs_aegis_report_interval_sec",
            cfg.get("FS_AEGIS_REPORT_INTERVAL_SEC", DEFAULT_AEGIS_REPORT_INTERVAL_SEC),
        )
    return _coerce_report_interval(raw)


APP_ID, APP_SECRET, ALLOWED_USERS, PUBLIC_ACCESS, CONFIG_PATH = _feishu_config()


def get_session_manager():
    global session_manager
    with agent_lock:
        if agent_error:
            raise RuntimeError(agent_error)
        if session_manager is None:
            session_manager = AegisMeshSessionManager(GeneraticAgent)
        return session_manager


def get_agent(session_id=None):
    global agent, agent_error
    try:
        sid = session_id or build_feishu_session_id(APP_ID, None, "__config_check__")
        agent = get_session_manager().get_or_create(sid, label="config-check").agent
        return agent
    except Exception as e:
        agent_error = str(e)
        raise


def create_client():
    return lark.Client.builder().app_id(APP_ID).app_secret(APP_SECRET).log_level(lark.LogLevel.INFO).build()


def _mask_secret(value):
    value = str(value or "")
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def check_config(init_agent=False):
    app_id, app_secret, allowed, public_access, path = _feishu_config()
    result = {
        "config_path": path,
        "app_id": app_id,
        "app_secret": _mask_secret(app_secret),
        "app_secret_present": bool(app_secret),
        "public_access": public_access,
        "allowed_users": sorted(allowed),
        "ready": bool(app_id and app_secret),
        "aegis_report_interval_sec": _aegis_report_interval_sec(),
    }
    if init_agent:
        try:
            ga = get_agent()
            result["agent_ready"] = True
            result["llm_count"] = len(ga.list_llms()) if hasattr(ga, "list_llms") else 0
            result["current_llm"] = ga.get_llm_name() if getattr(ga, "llmclient", None) else ""
        except Exception as e:
            result["agent_ready"] = False
            result["agent_error"] = str(e)
    return result


def _card_raw(elements):
    return json.dumps({
        "schema": "2.0",
        "config": {"streaming_mode": False, "width_mode": "fill"},
        "body": {"elements": elements},
    }, ensure_ascii=False)


def _card(text):
    return _card_raw([{"tag": "markdown", "content": text}])


def _send_raw(receive_id, payload, msg_type, rtype):
    try:
        body = CreateMessageRequest.builder().receive_id_type(rtype).request_body(
            CreateMessageRequestBody.builder().receive_id(receive_id).msg_type(msg_type).content(payload).build()
        ).build()
        r = client.im.v1.message.create(body)
        if r.success():
            return r.data.message_id if r.data else None
        print(f"发送失败: {r.code}, {r.msg}")
    except Exception as e:
        print(f"[ERROR] send_message failed: {e}")
        traceback.print_exc()
    return None


def _patch_card(message_id, card_json):
    try:
        body = PatchMessageRequest.builder().message_id(message_id).request_body(
            PatchMessageRequestBody.builder().content(card_json).build()
        ).build()
        r = client.im.v1.message.patch(body)
        if not r.success():
            print(f"[ERROR] patch_card 失败: {r.code}, {r.msg}")
        return r.success()
    except Exception as e:
        print(f"[ERROR] patch_card exception: {e}")
        traceback.print_exc()
        return False


def send_message(receive_id, content, msg_type="text", use_card=False, receive_id_type="open_id"):
    if use_card:
        return _send_raw(receive_id, _card(content), "interactive", receive_id_type)
    if msg_type == "post":
        sent = _send_raw(receive_id, _post(content), "post", receive_id_type)
        if sent:
            return sent
        # Best-effort compatibility fallback: preserve deliverability if Feishu
        # rejects rich text for an unexpected account/client constraint.
        return _send_raw(receive_id, json.dumps({"text": content}, ensure_ascii=False), "text", receive_id_type)
    if msg_type == "text":
        return _send_raw(receive_id, json.dumps({"text": content}, ensure_ascii=False), "text", receive_id_type)
    return _send_raw(receive_id, content, msg_type, receive_id_type)


def _send_report_message(receive_id, content, receive_id_type="open_id"):
    return send_message(receive_id, content, "post", False, receive_id_type)


def _log_reporter_error(exc):
    print(f"[ERROR] Aegis Mesh periodic report failed: {exc}")
    traceback.print_exception(type(exc), exc, exc.__traceback__)


def start_aegis_periodic_reporter(interval_sec=None):
    global periodic_reporter
    interval = _aegis_report_interval_sec() if interval_sec is None else _coerce_report_interval(interval_sec)
    if interval <= 0:
        return None
    with reporter_lock:
        if periodic_reporter is None:
            periodic_reporter = AegisMeshPeriodicReporter(
                get_session_manager(),
                send_fn=_send_report_message,
                split_fn=_segment_for_im,
                interval_sec=interval,
                on_error=_log_reporter_error,
            )
        else:
            periodic_reporter.interval_sec = interval
        reporter = periodic_reporter
    reporter.start()
    return reporter


def update_message(message_id, content):
    return _patch_card(message_id, _card(content))


def _upload_image_sync(file_path):
    try:
        with open(file_path, "rb") as f:
            request = CreateImageRequest.builder().request_body(
                CreateImageRequestBody.builder().image_type("message").image(f).build()
            ).build()
            response = client.im.v1.image.create(request)
            if response.success():
                return response.data.image_key
            print(f"[ERROR] upload image failed: {response.code}, {response.msg}")
    except Exception as e:
        print(f"[ERROR] upload image failed {file_path}: {e}")
    return None


def _upload_file_sync(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    file_type = _FILE_TYPE_MAP.get(ext, "stream")
    file_name = os.path.basename(file_path)
    try:
        with open(file_path, "rb") as f:
            request = CreateFileRequest.builder().request_body(
                CreateFileRequestBody.builder().file_type(file_type).file_name(file_name).file(f).build()
            ).build()
            response = client.im.v1.file.create(request)
            if response.success():
                return response.data.file_key
            print(f"[ERROR] upload file failed: {response.code}, {response.msg}")
    except Exception as e:
        print(f"[ERROR] upload file failed {file_path}: {e}")
    return None


def _download_image_sync(message_id, image_key):
    try:
        request = GetMessageResourceRequest.builder().message_id(message_id).file_key(image_key).type("image").build()
        response = client.im.v1.message_resource.get(request)
        if response.success():
            data = response.file.read() if hasattr(response.file, "read") else response.file
            return data, response.file_name
        print(f"[ERROR] download image failed: {response.code}, {response.msg}")
    except Exception as e:
        print(f"[ERROR] download image failed {image_key}: {e}")
    return None, None


def _download_file_sync(message_id, file_key, resource_type="file"):
    if resource_type == "audio":
        resource_type = "file"
    try:
        request = GetMessageResourceRequest.builder().message_id(message_id).file_key(file_key).type(resource_type).build()
        response = client.im.v1.message_resource.get(request)
        if response.success():
            data = response.file.read() if hasattr(response.file, "read") else response.file
            return data, response.file_name
        print(f"[ERROR] download {resource_type} failed: {response.code}, {response.msg}")
    except Exception as e:
        print(f"[ERROR] download {resource_type} failed {file_key}: {e}")
    return None, None


def _download_and_save_media(msg_type, content_json, message_id):
    data, filename = None, None
    if msg_type == "image":
        image_key = content_json.get("image_key")
        if image_key and message_id:
            data, filename = _download_image_sync(message_id, image_key)
            if not filename:
                filename = f"{image_key[:16]}.jpg"
    elif msg_type in ("audio", "file", "media"):
        file_key = content_json.get("file_key")
        if file_key and message_id:
            data, filename = _download_file_sync(message_id, file_key, msg_type)
            if not filename:
                filename = file_key[:16]
            if msg_type == "audio" and filename and not filename.endswith(".opus"):
                filename = f"{filename}.opus"
    if data and filename:
        file_path = os.path.join(MEDIA_DIR, os.path.basename(filename))
        with open(file_path, "wb") as f:
            f.write(data)
        return file_path, filename
    return None, None


def _describe_media(msg_type, file_path, filename):
    if msg_type == "image":
        return f"[image: {filename}]\n[Image: source: {file_path}]"
    if msg_type == "audio":
        return f"[audio: {filename}]\n[File: source: {file_path}]"
    if msg_type in ("file", "media"):
        return f"[{msg_type}: {filename}]\n[File: source: {file_path}]"
    return f"[{msg_type}]\n[File: source: {file_path}]"


def _send_local_file(receive_id, file_path, receive_id_type="open_id"):
    if not os.path.isfile(file_path):
        send_message(receive_id, f"⚠️ 文件不存在: {file_path}", receive_id_type=receive_id_type)
        return False
    ext = os.path.splitext(file_path)[1].lower()
    if ext in _IMAGE_EXTS:
        image_key = _upload_image_sync(file_path)
        if image_key:
            send_message(receive_id, json.dumps({"image_key": image_key}, ensure_ascii=False), msg_type="image", receive_id_type=receive_id_type)
            return True
    else:
        file_key = _upload_file_sync(file_path)
        if file_key:
            msg_type = "media" if ext in _AUDIO_EXTS or ext in _VIDEO_EXTS else "file"
            send_message(receive_id, json.dumps({"file_key": file_key}, ensure_ascii=False), msg_type=msg_type, receive_id_type=receive_id_type)
            return True
    send_message(receive_id, f"⚠️ 文件发送失败: {os.path.basename(file_path)}", receive_id_type=receive_id_type)
    return False


def _send_generated_files(receive_id, raw_text, receive_id_type="open_id"):
    for file_path in _extract_files(raw_text):
        _send_local_file(receive_id, file_path, receive_id_type)


def _send_final_result_text(receive_id, raw_text, receive_id_type="open_id"):
    body = _display_text(raw_text).strip() or "_(无文本输出)_"
    saved_path = None
    if len(body) > _FEISHU_INLINE_RESULT_LIMIT:
        saved_path = _write_feishu_output(raw_text)
        intro = f"✅ 完整结果较长（{len(body)} 字），已保存到 [FILE:{saved_path}]；下面发送文本分片："
        send_message(receive_id, intro, receive_id_type=receive_id_type)
    else:
        send_message(receive_id, "✅ 完整结果：", receive_id_type=receive_id_type)
    for part in split_text(body, 3800):
        send_message(receive_id, part, receive_id_type=receive_id_type)
    return saved_path


def _build_user_message(message):
    msg_type = message.message_type
    message_id = message.message_id
    content_json = _parse_json(message.content)
    parts, image_paths = [], []
    if msg_type == "text":
        text = str(content_json.get("text", "") or "").strip()
        if text:
            parts.append(text)
    elif msg_type == "post":
        text, image_keys = _extract_post_content(content_json)
        if text:
            parts.append(text)
        for image_key in image_keys:
            file_path, filename = _download_and_save_media("image", {"image_key": image_key}, message_id)
            if file_path and filename:
                parts.append(_describe_media("image", file_path, filename))
                image_paths.append(file_path)
            else:
                parts.append("[image: download failed]")
    elif msg_type in ("image", "audio", "file", "media"):
        file_path, filename = _download_and_save_media(msg_type, content_json, message_id)
        if file_path and filename:
            parts.append(_describe_media(msg_type, file_path, filename))
            if msg_type == "image":
                image_paths.append(file_path)
        else:
            parts.append(f"[{msg_type}: download failed]")
    elif msg_type in ("share_chat", "share_user", "interactive", "share_calendar_event", "system", "merge_forward"):
        parts.append(_extract_share_card_content(content_json, msg_type))
    else:
        parts.append(_MSG_TYPE_MAP.get(msg_type, f"[{msg_type}]"))
    return "\n".join([p for p in parts if p]).strip(), image_paths


def _fmt_tool_call(tc):
    name = tc.get('tool_name', '?')
    args = {k: v for k, v in (tc.get('args') or {}).items() if not k.startswith('_')}
    return f"- `{name}`({json.dumps(args, ensure_ascii=False)[:200]})"


def _build_step_detail(resp, tool_calls):
    """从 LLM response + tool_calls 组装单步展开详情（纯函数）。"""
    parts = []
    thinking = (getattr(resp, 'thinking', '') or '').strip() if resp else ''
    if thinking:
        parts.append(f"### 💭 Thinking\n{thinking}")
    if tool_calls:
        parts.append("### 🛠 Tool Calls\n" + "\n".join(_fmt_tool_call(tc) for tc in tool_calls))
    content = _display_text((getattr(resp, 'content', '') or '')).strip() if resp else ''
    if content and content != '...':
        parts.append(f"### 📝 Output\n{content}")
    return "\n\n".join(parts)


class _TaskCard:
    """飞书任务卡片：单卡片持续 patch；每步一个独立折叠面板（header 显示 summary，展开看详情）。"""
    _DETAIL_LIMIT = 8000
    _MAX_VISIBLE_STEPS = 8

    def __init__(self, receive_id, rid_type, *, task_id=None, outbox_dir=None, session=None):
        self.rid, self.rtype = receive_id, rid_type
        self.task_id = task_id or f"fs_card_{uuid.uuid4().hex}"
        self.outbox_dir = outbox_dir
        self.session = dict(session or {})
        self.steps = []          # [(summary, detail), ...]
        self.status = "🤔 思考中..."
        self.final = None
        self.msg_id = None
        self.start_fallback_sent = False
        self.final_fallback_sent = False

    def _step_detail_notice(self, idx, summary, detail):
        digest = build_digest(detail, budget=1200)
        try:
            saved = write_artifact(
                self.task_id,
                f"step_{idx}_detail",
                detail,
                kind="task_step_detail",
                status=self.status,
                session=self.session,
                metadata={"summary": summary, "step": idx},
                omitted_section={"section": "task_card_step", "step": idx, "summary": summary},
                base_dir=self.outbox_dir,
            )
            artifact = saved["artifact"]
            return (
                "步骤详情较长，完整内容已保存到本地 outbox。\n\n"
                f"{digest}\n\n"
                f"任务: `{self.task_id}`\n"
                f"详情: `{artifact['path']}` ({artifact['chars']} 字符)\n"
                f"索引: `/artifacts {self.task_id}`\n"
                f"全文: `/full {self.task_id}`；分片: `/chunk {self.task_id} <n>`；继续: `/more`"
            )
        except Exception as exc:
            return (
                f"步骤详情较长，但写入 outbox 失败: {exc}\n\n"
                f"{digest}\n\n"
                "请检查本地 outbox 配置后重试。"
            )

    def _prepare_step_detail(self, summary, detail):
        detail = detail or "_(无输出)_"
        if len(detail) <= self._DETAIL_LIMIT:
            return detail
        return self._step_detail_notice(len(self.steps) + 1, summary, detail)

    def _step_panel(self, idx, summary, detail):
        detail = detail or "_(无输出)_"
        if len(detail) > self._DETAIL_LIMIT:
            detail = (
                build_digest(detail, budget=1200)
                + f"\n\n任务: `{self.task_id}`\n索引: `/artifacts {self.task_id}`"
            )
        return {
            "tag": "collapsible_panel", "expanded": False,
            "header": {"title": {"tag": "plain_text", "content": f"步骤 {idx} · {summary}"}},
            "elements": [{"tag": "markdown", "content": detail}],
        }

    def _visible_steps(self):
        if len(self.steps) <= self._MAX_VISIBLE_STEPS:
            return 0, self.steps
        hidden = len(self.steps) - self._MAX_VISIBLE_STEPS
        return hidden, self.steps[-self._MAX_VISIBLE_STEPS:]

    def _build(self):
        els = [{"tag": "markdown", "content": f"**{self.status}**"}]
        hidden, visible_steps = self._visible_steps()
        if hidden:
            els.append({
                "tag": "note",
                "elements": [{
                    "tag": "plain_text",
                    "content": (
                        f"已折叠 {hidden} 个较早步骤以控制飞书卡片大小。"
                        f"当前卡片仅展示最近 {len(visible_steps)} 步；"
                        f"完整最终输出见 /full {self.task_id}，外置详情见 /artifacts {self.task_id}。"
                    ),
                }],
            })
        start_index = hidden + 1
        for offset, (summary, detail) in enumerate(visible_steps):
            els.append(self._step_panel(start_index + offset, summary, detail))
        if self.final:
            els += [{"tag": "hr"}, {"tag": "markdown", "content": self.final}]
        return _card_raw(els)

    def _push(self):
        card = self._build()
        if self.msg_id:
            ok = _patch_card(self.msg_id, card)
        else:
            self.msg_id = _send_raw(self.rid, card, "interactive", self.rtype)
            ok = bool(self.msg_id)
        return ok

    def _fallback_text(self, text, *, final=False):
        attr = "final_fallback_sent" if final else "start_fallback_sent"
        if getattr(self, attr):
            return
        setattr(self, attr, True)
        send_message(self.rid, text, receive_id_type=self.rtype)

    # ── 公开接口 ──

    def start(self):
        if not self._push():
            self._fallback_text("🤔 思考中...")

    def step(self, summary, detail=""):
        self.steps.append((summary, self._prepare_step_detail(summary, detail)))
        self.status = f"⏳ 工作中 · 步骤 {len(self.steps)}"
        self._push()

    def done(self, text, *, result_note=None):
        self.status = "✅ 已完成"
        preview = _final_preview_text(text)
        if result_note:
            preview = f"{preview}\n\n{result_note}"
        self.final = preview or "_(无文本输出)_"
        if not self._push():
            self._fallback_text(self.final, final=True)

    def fail(self, msg, detail=None):
        self.status = f"❌ {msg}"
        if detail:
            self.final = detail
        if not self._push():
            fallback = f"❌ {msg}"
            if detail:
                fallback = f"{fallback}\n\n{detail}"
            self._fallback_text(fallback, final=True)


def _make_task_hook(card, task_id, on_final, on_progress=None):
    """飞书任务 hook：每轮 patch 卡片状态；结束触发 on_final(raw) 处理附件。"""
    def hook(ctx):
        try:
            parent = getattr(ctx.get("self"), "parent", None)
            if getattr(parent, "_fs_active_task_id", None) != task_id:
                return
            if ctx.get('exit_reason'):
                resp = ctx.get('response')
                raw = resp.content if hasattr(resp, 'content') else str(resp)
                on_final(raw)
            elif ctx.get('summary'):
                if on_progress:
                    on_progress(ctx['summary'])
                detail = _build_step_detail(ctx.get('response'), ctx.get('tool_calls') or [])
                card.step(ctx['summary'], detail)
        except Exception as e:
            print(f"[fs hook] error: {e}")
    return hook


class FeishuApp(AgentChatMixin):
    label, source, split_limit = "Feishu", "feishu", 4000

    def __init__(self, session_manager, *, outbox_dir=None):
        self.session_manager = session_manager
        self.agent = None
        self.user_tasks = {}
        self.outbox_dir = outbox_dir
        self._recent_task_ids = {}
        self._more_cursors = {}

    def _session_id(self, chat_id, session_id=None):
        return session_id or chat_id

    def _remember_task(self, mesh_session_id, task_id):
        self._recent_task_ids[mesh_session_id] = task_id
        self._more_cursors.setdefault(mesh_session_id, {"task_id": task_id, "next_chunk": 1})
        if self._more_cursors[mesh_session_id].get("task_id") != task_id:
            self._more_cursors[mesh_session_id] = {"task_id": task_id, "next_chunk": 1}

    def _recent_task_id(self, mesh_session_id):
        return self._recent_task_ids.get(mesh_session_id)

    def _task_arg_or_recent(self, mesh_session_id, parts, *, index=1):
        if len(parts) > index:
            return parts[index]
        return self._recent_task_id(mesh_session_id)

    async def send_text(self, chat_id, content, *, receive_id=None, receive_id_type="open_id", **_):
        rid = receive_id or chat_id
        for part in _segment_for_im(content, self.split_limit):
            await asyncio.to_thread(send_message, rid, part, "post", False, receive_id_type)

    async def send_done(self, chat_id, raw_text, *, receive_id=None, receive_id_type="open_id", session_id=None, **_):
        rid = receive_id or chat_id
        text = _display_text(raw_text)
        mesh_session_id = self._session_id(chat_id, session_id)
        task_id = f"{mesh_session_id}_{uuid.uuid4().hex}"
        envelope = await asyncio.to_thread(
            build_delivery_envelope,
            task_id,
            text,
            raw_text=raw_text,
            status="done",
            session={"id": mesh_session_id, "receive_id_type": receive_id_type},
            metadata={"source": self.source, "entrypoint": "send_done"},
            base_dir=self.outbox_dir,
        )
        self._remember_task(mesh_session_id, task_id)
        await self.send_text(chat_id, render_feishu_digest(envelope), receive_id=rid, receive_id_type=receive_id_type)
        await asyncio.to_thread(_send_generated_files, rid, raw_text, receive_id_type)

    async def _handle_full_command(self, chat_id, mesh_session_id, parts, **ctx):
        task_id = self._task_arg_or_recent(mesh_session_id, parts)
        if not task_id:
            return await self.send_text(chat_id, "没有最近任务。用法: /full <task_id>", **ctx)
        try:
            manifest, text = read_full(task_id, base_dir=self.outbox_dir)
        except Exception as exc:
            return await self.send_text(chat_id, f"❌ 无法读取完整输出 `{task_id}`: {exc}", **ctx)
        self._remember_task(mesh_session_id, task_id)
        self._more_cursors[mesh_session_id] = {"task_id": task_id, "next_chunk": len(manifest.get("chunks") or []) + 1}
        header = f"Full output for `{task_id}` ({manifest.get('full', {}).get('chars', len(text))} chars):\n\n"
        return await self.send_text(chat_id, header + text, **ctx)

    def _parse_chunk_args(self, mesh_session_id, parts):
        if len(parts) == 2 and parts[1].isdigit():
            return self._recent_task_id(mesh_session_id), int(parts[1])
        if len(parts) >= 3 and parts[2].isdigit():
            return parts[1], int(parts[2])
        return None, None

    async def _handle_chunk_command(self, chat_id, mesh_session_id, parts, **ctx):
        task_id, index = self._parse_chunk_args(mesh_session_id, parts)
        if not task_id or not index:
            return await self.send_text(chat_id, "用法: /chunk [task_id] <n>", **ctx)
        try:
            manifest, text, _entry = read_chunk(task_id, index, base_dir=self.outbox_dir)
        except Exception as exc:
            return await self.send_text(chat_id, f"❌ 无法读取分片 `{task_id}` #{index}: {exc}", **ctx)
        chunks = manifest.get("chunks") or []
        self._remember_task(mesh_session_id, task_id)
        self._more_cursors[mesh_session_id] = {"task_id": task_id, "next_chunk": index + 1}
        header = f"Chunk {index}/{len(chunks)} for `{task_id}`:\n\n"
        return await self.send_text(chat_id, header + text, **ctx)

    async def _handle_artifacts_command(self, chat_id, mesh_session_id, parts, **ctx):
        task_id = self._task_arg_or_recent(mesh_session_id, parts)
        if not task_id:
            return await self.send_text(chat_id, "没有最近任务。用法: /artifacts <task_id>", **ctx)
        try:
            manifest = read_manifest(task_id, base_dir=self.outbox_dir)
        except Exception as exc:
            return await self.send_text(chat_id, f"❌ 无法读取产物索引 `{task_id}`: {exc}", **ctx)
        self._remember_task(mesh_session_id, task_id)
        return await self.send_text(chat_id, render_artifact_index(manifest), **ctx)

    async def _handle_more_command(self, chat_id, mesh_session_id, **ctx):
        cursor = self._more_cursors.get(mesh_session_id)
        if not cursor:
            task_id = self._recent_task_id(mesh_session_id)
            if not task_id:
                return await self.send_text(chat_id, "没有最近任务。用法: /chunk <n> 或 /full <task_id>", **ctx)
            cursor = {"task_id": task_id, "next_chunk": 1}
        task_id = cursor["task_id"]
        index = int(cursor.get("next_chunk") or 1)
        try:
            manifest = read_manifest(task_id, base_dir=self.outbox_dir)
        except Exception as exc:
            return await self.send_text(chat_id, f"❌ 无法读取任务 `{task_id}`: {exc}", **ctx)
        chunks = manifest.get("chunks") or []
        if index > len(chunks):
            return await self.send_text(chat_id, f"任务 `{task_id}` 没有更多分片。", **ctx)
        try:
            _manifest, text, _entry = read_chunk(task_id, index, base_dir=self.outbox_dir)
        except Exception as exc:
            return await self.send_text(chat_id, f"❌ 无法读取分片 `{task_id}` #{index}: {exc}", **ctx)
        self._more_cursors[mesh_session_id] = {"task_id": task_id, "next_chunk": index + 1}
        header = f"Chunk {index}/{len(chunks)} for `{task_id}`:\n\n"
        return await self.send_text(chat_id, header + text, **ctx)

    async def handle_command(self, chat_id, cmd, *, session_id=None, **ctx):
        mesh_session_id = self._session_id(chat_id, session_id)
        parts = (cmd or "").split()
        op = (parts[0] if parts else "").lower()
        if op == "/help":
            return await self.send_text(chat_id, _FEISHU_HELP_TEXT, **ctx)
        if op == "/stop":
            stopped = self.session_manager.stop_task(mesh_session_id)
            msg = "⏹️ 正在停止..." if stopped else "当前会话没有正在运行的任务。"
            return await self.send_text(chat_id, msg, **ctx)
        if op == "/dashboard" or (op == "/status" and len(parts) > 1 and parts[1].lower() == "all"):
            return await self.send_text(
                chat_id,
                render_dashboard_text(self.session_manager.dashboard_snapshot()),
                **ctx,
            )
        if op in ("/report", "/summary"):
            return await self.send_text(
                chat_id,
                render_periodic_report_text(
                    self.session_manager.dashboard_snapshot(),
                    target_session_id=mesh_session_id,
                ),
                **ctx,
            )
        if op == "/full":
            return await self._handle_full_command(chat_id, mesh_session_id, parts, **ctx)
        if op == "/chunk":
            return await self._handle_chunk_command(chat_id, mesh_session_id, parts, **ctx)
        if op == "/artifacts":
            return await self._handle_artifacts_command(chat_id, mesh_session_id, parts, **ctx)
        if op == "/more":
            return await self._handle_more_command(chat_id, mesh_session_id, **ctx)

        state = self.session_manager.get_or_create(mesh_session_id, label=chat_id)
        agent = state.agent
        if op == "/status":
            llm = agent.get_llm_name() if getattr(agent, "llmclient", None) else "未配置"
            status_text = render_session_status_text(
                self.session_manager.snapshot(mesh_session_id),
                dashboard=self.session_manager.dashboard_snapshot(),
            )
            return await self.send_text(chat_id, f"{status_text}\nLLM: [{getattr(agent, 'llm_no', 0)}] {llm}", **ctx)
        if op == "/llm":
            if not getattr(agent, "llmclient", None):
                return await self.send_text(chat_id, "❌ 当前没有可用的 LLM 配置", **ctx)
            if len(parts) > 1:
                try:
                    agent.next_llm(int(parts[1]))
                    return await self.send_text(chat_id, f"✅ 已切换到 [{agent.llm_no}] {agent.get_llm_name()}", **ctx)
                except Exception:
                    return await self.send_text(chat_id, f"用法: /llm <0-{len(agent.list_llms()) - 1}>", **ctx)
            lines = [f"{'→' if cur else '  '} [{i}] {name}" for i, name, cur in agent.list_llms()]
            return await self.send_text(chat_id, "LLMs:\n" + "\n".join(lines), **ctx)
        if op == "/restore":
            try:
                restored_info, err = chat_common.format_restore()
                if err:
                    return await self.send_text(chat_id, err, **ctx)
                restored, fname, count = restored_info
                agent.abort()
                agent.history.extend(restored)
                return await self.send_text(chat_id, f"✅ 已恢复 {count} 轮对话\n来源: {fname}\n(仅恢复上下文，请输入新问题继续)", **ctx)
            except Exception as e:
                return await self.send_text(chat_id, f"❌ 恢复失败: {e}", **ctx)
        if op == "/continue":
            return await self.send_text(chat_id, chat_common._handle_continue_frontend(agent, cmd), **ctx)
        if op == "/new":
            return await self.send_text(chat_id, chat_common._reset_conversation(agent), **ctx)
        if op == "/btw":
            answer = await asyncio.to_thread(chat_common._handle_btw_frontend, agent, cmd)
            return await self.send_text(chat_id, answer, **ctx)
        if op == "/review":
            return await self.run_agent(chat_id, cmd, session_id=mesh_session_id, **ctx)
        return await self.send_text(chat_id, _FEISHU_HELP_TEXT, **ctx)

    async def run_agent(self, chat_id, text, *, receive_id=None, receive_id_type="open_id", session_id=None, images=None, **_):
        mesh_session_id = self._session_id(chat_id, session_id)
        task_id = f"{mesh_session_id}_{uuid.uuid4().hex}"
        state, active_task = self.session_manager.begin_task(
            mesh_session_id,
            task_id,
            label=chat_id,
            metadata={"receive_id": receive_id or chat_id, "receive_id_type": receive_id_type},
        )
        if active_task is None:
            await self.send_text(chat_id, "当前会话已有任务在运行，请等待完成或发送 /stop 后再试。", receive_id=receive_id, receive_id_type=receive_id_type)
            return
        agent = state.agent
        rid = receive_id or chat_id
        hook_key = f"fs_{task_id}"
        session_meta = {"id": mesh_session_id, "chat_id": chat_id, "receive_id": rid, "receive_id_type": receive_id_type}
        self._remember_task(mesh_session_id, task_id)
        card = _TaskCard(rid, receive_id_type, task_id=task_id, outbox_dir=self.outbox_dir, session=session_meta)
        result = {"raw": None, "sent": False}
        finish_lock = threading.Lock()

        def _task_status_text():
            return render_session_status_text(
                self.session_manager.snapshot(mesh_session_id),
                dashboard=self.session_manager.dashboard_snapshot(),
            )

        def _claim_terminal():
            with finish_lock:
                if result["sent"]:
                    return False
                result["sent"] = True
                return True

        def _finish(raw):
            if not _claim_terminal():
                return
            result["raw"] = raw
            full_text = _display_text(raw)
            envelope = build_delivery_envelope(
                task_id,
                full_text,
                raw_text=raw,
                title="Feishu agent result",
                status="done",
                session=session_meta,
                metadata={"source": self.source},
                base_dir=self.outbox_dir,
            )
            self._remember_task(mesh_session_id, task_id)
            self.session_manager.complete_task(mesh_session_id, task_id, result_summary=_result_summary(raw))
            card.done(f"{_task_status_text()}\n\n{render_feishu_digest(envelope)}")
            _send_generated_files(rid, raw, receive_id_type=receive_id_type)

        def _record_progress(summary):
            self.session_manager.record_task_event(mesh_session_id, task_id, message=summary)

        try:
            await asyncio.to_thread(card.start)
            if not hasattr(agent, '_turn_end_hooks'):
                agent._turn_end_hooks = {}
            agent._turn_end_hooks[hook_key] = _make_task_hook(card, task_id, _finish, _record_progress)
            agent._fs_active_task_id = task_id
            dq = agent.put_task(f"{FILE_HINT}\n\n{text}", source=self.source, images=images or None)
            start = time.time()
            while active_task.running and not result["sent"]:
                try:
                    item = await asyncio.to_thread(dq.get, True, 1)
                except Q.Empty:
                    item = None
                if item and "done" in item:
                    await asyncio.to_thread(_finish, item.get("done", ""))
                    break
                if time.time() - start > AGENT_TIMEOUT_SEC:
                    error_msg = "任务超时"
                    self.session_manager.fail_task(mesh_session_id, task_id, error=error_msg)
                    abort = getattr(agent, "abort", None)
                    if callable(abort):
                        abort()
                    if _claim_terminal():
                        await asyncio.to_thread(card.fail, error_msg, _task_status_text())
                    break
            if not active_task.running and _claim_terminal():
                await asyncio.to_thread(card.fail, "已停止", _task_status_text())
        except Exception as e:
            traceback.print_exc()
            error_msg = f"错误: {e}"
            self.session_manager.fail_task(mesh_session_id, task_id, error=error_msg)
            if _claim_terminal():
                await asyncio.to_thread(card.fail, error_msg, _task_status_text())
        finally:
            if getattr(agent, "_fs_active_task_id", None) == task_id:
                try:
                    delattr(agent, "_fs_active_task_id")
                except AttributeError:
                    pass
            if hasattr(agent, '_turn_end_hooks'):
                agent._turn_end_hooks.pop(hook_key, None)


def get_app():
    global app
    if app is None:
        app = FeishuApp(get_session_manager())
    return app


def _run_async(coro):
    try:
        asyncio.run(coro)
    except Exception:
        traceback.print_exc()


def handle_message(data):
    event, message, sender = data.event, data.event.message, data.event.sender
    message_id = getattr(message, "message_id", "") or ""
    if not _claim_message_once(message_id):
        print(f"忽略重复飞书消息: {message_id}")
        return
    open_id = sender.sender_id.open_id
    chat_id = message.chat_id
    if not PUBLIC_ACCESS and open_id not in ALLOWED_USERS:
        print(f"未授权用户: {open_id}")
        return
    user_input, image_paths = _build_user_message(message)
    if not user_input:
        if chat_id:
            send_message(chat_id, f"⚠️ 暂不支持处理此类飞书消息：{message.message_type}", receive_id_type="chat_id")
        else:
            send_message(open_id, f"⚠️ 暂不支持处理此类飞书消息：{message.message_type}")
        return
    print(f"收到消息 [{open_id}] ({message.message_type}, {len(image_paths)} images): {user_input[:200]}")
    receive_id = chat_id or open_id
    receive_id_type = "chat_id" if chat_id else "open_id"
    session_id = build_feishu_session_id(APP_ID, chat_id, open_id)
    chat_key = receive_id
    if message.message_type == "text" and user_input.startswith("/"):
        threading.Thread(
            target=_run_async,
            args=(get_app().handle_command(chat_key, user_input, session_id=session_id, receive_id=receive_id, receive_id_type=receive_id_type),),
            daemon=True,
        ).start()
        return
    threading.Thread(
        target=_run_async,
        args=(get_app().run_agent(chat_key, user_input, session_id=session_id, receive_id=receive_id, receive_id_type=receive_id_type, images=image_paths),),
        daemon=True,
    ).start()


def main():
    global client, APP_ID, APP_SECRET, ALLOWED_USERS, PUBLIC_ACCESS, CONFIG_PATH
    APP_ID, APP_SECRET, ALLOWED_USERS, PUBLIC_ACCESS, CONFIG_PATH = _feishu_config()
    if not APP_ID or not APP_SECRET:
        print(f"错误: 请在 mykey 配置中填写 fs_app_id 和 fs_app_secret\n配置文件: {CONFIG_PATH}", flush=True)
        sys.exit(1)
    handler = lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(handle_message).build()
    retry_delay = 5
    while True:
        try:
            client = create_client()
            reporter = start_aegis_periodic_reporter()
            cli = lark.ws.Client(APP_ID, APP_SECRET, event_handler=handler, log_level=lark.LogLevel.INFO)
            report_line = f"摘要报告间隔: {reporter.interval_sec}s\n" if reporter else "摘要报告: 已禁用\n"
            print("=" * 50 + "\n飞书 Agent 已启动（长连接模式）\n" + f"App ID: {APP_ID}\n配置: {CONFIG_PATH}\n{report_line}等待消息...\n" + "=" * 50, flush=True)
            cli.start()
            retry_delay = 5
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"[WARN] 飞书长连接断开或启动失败: {e}", flush=True)
            traceback.print_exc()
        print(f"[INFO] {retry_delay}s 后重连飞书长连接...", flush=True)
        time.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 120)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A3Agent Feishu frontend")
    parser.add_argument("--check", action="store_true", help="只检查飞书配置，不启动长连接")
    parser.add_argument("--check-agent", action="store_true", help="检查配置并初始化 Agent/LLM")
    args = parser.parse_args()
    if args.check or args.check_agent:
        print(json.dumps(check_config(init_agent=args.check_agent), ensure_ascii=False, indent=2), flush=True)
    else:
        main()
