"""Local settings shared by vision and notification import."""
from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit

AI_REQUIRED = "请先配置具备多模态能力(支持文字和图片识别)的 AI 接口."


def settings_dir() -> Path:
    override = os.environ.get("COURSEFLOW_HOME")
    if override:
        return Path(override).expanduser()
    import sys
    if getattr(sys, "frozen", False):
        portable = Path(sys.executable).parent / "data"
        try:
            portable.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=portable):
                pass
            return portable
        except OSError:
            pass
    return Path.home() / ".courseflow"


def atomic_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".courseflow-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _protect(value: str, decrypt: bool = False) -> str:
    """Use Windows user-bound DPAPI, without an additional keyring dependency."""
    if not value:
        return ""
    if os.name != "nt":
        return value

    class Blob(ctypes.Structure):
        _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    raw = base64.b64decode(value) if decrypt else value.encode("utf-8")
    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    function = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    ok = function(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target))
    if not ok:
        raise ValueError("无法读取本机保存的 API Key, 请重新输入.")
    try:
        result = ctypes.string_at(target.data, target.size)
        return result.decode("utf-8") if decrypt else base64.b64encode(result).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)


@dataclass
class AIConfig:
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    timeout: int = 90
    verified_signature: str = ""

    def validate(self) -> None:
        parsed = urlsplit(self.base_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(AI_REQUIRED + " 请填写有效的 API 地址.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("API 地址不能包含账号, 密码, 查询参数或片段.")
        if not self.model.strip():
            raise ValueError(AI_REQUIRED + " 请填写模型名称.")
        if not 5 <= self.timeout <= 300:
            raise ValueError("超时应在 5-300 秒之间.")
        host = parsed.hostname.lower()
        local = host in {"localhost", "127.0.0.1", "::1"}
        if not local and not self.api_key.strip():
            raise ValueError(AI_REQUIRED + " 请填写提供方要求的 API Key.")

    @property
    def signature(self) -> str:
        raw = "\n".join([self.base_url.rstrip("/"), self.model, self.api_key])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @property
    def vision_verified(self) -> bool:
        return self.verified_signature == self.signature


def load_ai_config(path=None) -> AIConfig:
    config_path = Path(path) if path else settings_dir() / "ai.json"
    data = {}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("invalid config")
        except (OSError, ValueError) as exc:
            raise ValueError("AI 配置文件无法读取, 请在设置中重新配置.") from exc
    key = str(data.get("api_key", ""))
    if data.get("key_storage") == "dpapi" and not os.environ.get("COURSEFLOW_API_KEY"):
        key = _protect(key, decrypt=True)
    try:
        timeout = int(data.get("timeout", 90))
    except (TypeError, ValueError):
        timeout = 90
    return AIConfig(
        base_url=os.environ.get("COURSEFLOW_BASE_URL", str(data.get("base_url", ""))),
        model=os.environ.get("COURSEFLOW_MODEL", str(data.get("model", ""))),
        api_key=os.environ.get("COURSEFLOW_API_KEY", key),
        timeout=timeout,
        verified_signature=str(data.get("verified_signature", "")),
    )


def save_ai_config(config: AIConfig, path=None) -> Path:
    config.validate()
    target = Path(path) if path else settings_dir() / "ai.json"
    data = asdict(config)
    if os.name == "nt" and config.api_key:
        data["api_key"] = _protect(config.api_key)
        data["key_storage"] = "dpapi"
    atomic_text(target, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return target


def recent_source():
    try:
        data = json.loads((settings_dir() / "session.json").read_text(encoding="utf-8"))
        value = data.get("current_source") if isinstance(data, dict) else None
        if isinstance(value, str):
            path = Path(value).expanduser()
            if path.suffix.lower() in {".yaml", ".yml"} and path.is_file():
                return path
    except (OSError, ValueError):
        pass
    return None


def remember_source(path):
    atomic_text(settings_dir() / "session.json", json.dumps({"current_source": str(Path(path).resolve())}, ensure_ascii=False))
