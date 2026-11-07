import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from PIL import Image

from courseflow.ai import AIClient, AIError, decode_json
from courseflow.settings import AIConfig, load_ai_config, save_ai_config
from courseflow.vision import draft_from_payload, recognize_image


def config():
    return AIConfig("http://localhost:11434/v1", "test-vision-model", "test-key-not-real")


def completion(payload):
    return {"choices": [{"message": {"content": json.dumps(payload)}, "finish_reason": "stop"}]}


class SharedAITests(unittest.TestCase):
    def test_configuration_roundtrip_preserves_key_without_exposing_windows_plaintext(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "ai.json"
            original = config()
            save_ai_config(original, path)
            loaded = load_ai_config(path)
            self.assertEqual((loaded.model, loaded.api_key), (original.model, original.api_key))
            if path.read_text(encoding="utf-8").find('"key_storage": "dpapi"') >= 0:
                self.assertNotIn(original.api_key, path.read_text(encoding="utf-8"))

    def test_probe_requires_correct_random_image_content(self):
        seen = []
        def transport(payload):
            seen.append(payload)
            return completion({"code": "2222"})
        client = AIClient(config(), transport)
        with patch("courseflow.ai.secrets.choice", return_value="2"):
            client.require_vision()
            client.require_vision()
        self.assertEqual(len(seen), 1)
        self.assertTrue(client.config.vision_verified)
        content = seen[0]["messages"][1]["content"]
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_wrong_probe_does_not_mark_text_only_model_as_verified(self):
        client = AIClient(config(), lambda payload: completion({"code": "1111"}))
        with patch("courseflow.ai.secrets.choice", return_value="2"):
            with self.assertRaises(AIError):
                client.require_vision()
        self.assertFalse(client.config.vision_verified)

    def test_changing_model_invalidates_cached_capability_check(self):
        settings = config()
        settings.verified_signature = settings.signature
        settings.model = "different-model"
        self.assertFalse(settings.vision_verified)

    def test_rate_limit_is_not_retried(self):
        client = AIClient(config())
        error = HTTPError("http://localhost", 429, "limit", {}, io.BytesIO(b"rate limit"))
        with patch("courseflow.ai.request.build_opener") as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaisesRegex(AIError, "限流"):
                client.json("Return JSON", "test")
            self.assertEqual(opener.return_value.open.call_count, 1)

    def test_invalid_json_or_truncated_response_cannot_be_applied(self):
        with self.assertRaises(AIError):
            decode_json('{"courses": [')
        client = AIClient(config(), lambda payload: {"choices": [{"message": {"content": "{}"}, "finish_reason": "length"}]})
        with self.assertRaisesRegex(AIError, "截断"):
            client.json("Return JSON", "test")

    def test_partial_vision_result_preserves_uncertainty(self):
        draft = draft_from_payload({"courses": [
            {"name": "数学", "day": "周一", "periods": "1-2", "weeks": "", "room": ""},
            {"name": "无法定位的课", "day": None, "periods": "", "weeks": "1-16周"},
        ], "notes": ["右下角看不清"]})
        self.assertEqual(len(draft.courses), 1)
        self.assertEqual(draft.courses[0].weeks, "")
        self.assertTrue(any("周次需要人工确认" in n for n in draft.notes))
        self.assertTrue(any("请人工补充" in n for n in draft.notes))

    def test_out_of_term_weeks_are_preserved_and_flagged(self):
        draft = draft_from_payload({"courses": [
            {"name": "数学", "day": "周一", "periods": "1-2", "weeks": "4-19周"},
        ]}, total_weeks=16)
        self.assertEqual(draft.courses[0].weeks, "4-19周")
        self.assertTrue(any("学期总周数" in note for note in draft.notes))

    def test_invalid_image_does_not_contact_ai(self):
        with TemporaryDirectory() as folder:
            client = AIClient(config())
            with patch.object(client, "require_vision") as probe:
                with self.assertRaises(AIError):
                    recognize_image(Path(folder) / "missing.png", client)
            probe.assert_not_called()


    def test_tiled_recognition_retains_completed_parts_after_a_failed_tile(self):
        first = {"name": "数学", "day": "周一", "periods": "1-2", "weeks": "1-16周"}
        last = {"name": "体育", "day": "周五", "periods": "5-6", "weeks": "1-16周"}
        replies = [completion({"courses": [first]}), AIError("测试分块失败"),
                   completion({"courses": [first]}), completion({"courses": [last]})]
        seen = []
        def transport(payload):
            seen.append(payload)
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply
        settings = config()
        settings.verified_signature = settings.signature
        with TemporaryDirectory() as folder:
            path = Path(folder) / "test.png"
            Image.new("RGB", (800, 800), "white").save(path)
            before = path.read_bytes()
            draft = recognize_image(path, AIClient(settings, transport), tiled=True)
            self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(seen), 4)
        self.assertEqual([course.name for course in draft.courses], ["数学", "体育"])
        self.assertTrue(any("分块 2 未完成" in note for note in draft.notes))
        self.assertTrue(all(len(payload["messages"][1]["content"]) == 3 for payload in seen))


if __name__ == "__main__":
    unittest.main()
