"""Bounded OpenAI-compatible requests, with a real image-capability probe."""
from __future__ import annotations

import base64
import io
import json
import re
import secrets
from typing import Callable, Optional
from urllib import error, request

from PIL import Image, ImageDraw, ImageFont

from .settings import AIConfig, AI_REQUIRED


class AIError(ValueError):
    pass


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def decode_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        result = json.loads(text)
    except ValueError as exc:
        raise AIError("AI 返回的内容不是完整 JSON, 请重试或更换模型. 本次未修改课表.") from exc
    if not isinstance(result, dict):
        raise AIError("AI 返回的最外层应为对象. 本次未修改课表.")
    return result


def image_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


class AIClient:
    def __init__(self, config: AIConfig, transport: Optional[Callable] = None):
        try:
            config.validate()
        except ValueError as exc:
            raise AIError(str(exc)) from exc
        self.config = config
        self.transport = transport or self._post

    def _post(self, payload: dict) -> dict:
        base = self.config.base_url.rstrip("/")
        url = base if base.endswith("/chat/completions") else base + "/chat/completions"
        headers = {"Content-Type": "application/json", "User-Agent": "CourseFlow/1.0"}
        if self.config.api_key:
            headers["Authorization"] = "Bearer " + self.config.api_key
        req = request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with request.build_opener(_NoRedirect()).open(req, timeout=self.config.timeout) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
                if len(raw) > 4 * 1024 * 1024:
                    raise AIError("AI 响应过大, 已停止读取.")
                return json.loads(raw)
        except error.HTTPError as exc:
            # A single compatibility fallback; never loop on rate limits or authentication.
            try:
                detail = exc.read(2048).decode("utf-8", errors="replace")
            finally:
                exc.close()
            if self.config.api_key:
                detail = detail.replace(self.config.api_key, "***")
            if exc.code in {400, 422} and "response_format" in detail and "response_format" in payload:
                fallback = dict(payload)
                fallback.pop("response_format")
                return self._post(fallback)
            messages = {
                401: "API 认证失败, 请检查 Key.",
                403: "接口拒绝访问, 请检查账号权限和模型权限.",
                404: "接口或模型不存在, 请检查 API 地址及模型名.",
                429: "接口限流或额度不足, 请稍后重试或检查余额.",
            }
            raise AIError(messages.get(exc.code, f"AI 接口返回 HTTP {exc.code}, 请检查配置.")) from exc
        except (error.URLError, TimeoutError, OSError) as exc:
            raise AIError("AI 接口连接失败或超时, 请检查网络和地址后重试.") from exc
        except (ValueError, KeyError) as exc:
            raise AIError("AI 接口返回了无法解析的响应.") from exc

    def json(self, system: str, text: str, images=()) -> dict:
        content = [{"type": "text", "text": text}]
        content.extend({"type": "image_url", "image_url": {"url": image_url(img), "detail": "high"}} for img in images)
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        response = self.transport(payload)
        try:
            message = response["choices"][0]["message"]
            result = message.get("content")
            if isinstance(result, list):
                result = "".join(x.get("text", "") for x in result if isinstance(x, dict))
            if not isinstance(result, str) or not result.strip():
                raise ValueError("empty message")
            if response["choices"][0].get("finish_reason") == "length":
                raise AIError("AI 响应被截断, 请使用分块识别或提高提供方的输出上限.")
            return decode_json(result)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            if isinstance(exc, AIError):
                raise
            raise AIError("AI 没有返回可用结果, 请检查模型是否支持该接口.") from exc

    def test_vision(self) -> str:
        code = "".join(secrets.choice("23456789") for _ in range(4))
        picture = Image.new("RGB", (280, 100), "white")
        draw = ImageDraw.Draw(picture)
        font = ImageFont.load_default(size=54)
        draw.text((34, 16), code, fill="black", font=font)
        result = self.json(
            'Read the four digits in the attached image. Reply only JSON: {"code":"digits"}. Do not guess if image input is unsupported.',
            "请读取图片中的四位数字, 只返回 JSON.", [picture],
        )
        if str(result.get("code", "")).strip() != code:
            raise AIError(AI_REQUIRED + " 当前模型未通过图片识别自检, 请更换模型后重试.")
        self.config.verified_signature = self.config.signature
        return "多模态自检通过: 图片中的四位数字读取正确."

    def require_vision(self) -> None:
        if not self.config.vision_verified:
            self.test_vision()
