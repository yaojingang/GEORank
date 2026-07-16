import unittest

from app.services.ai_client import AIClient


class _EmptyChoiceMessage:
    content = ""


class _EmptyChoice:
    message = _EmptyChoiceMessage()


class _EmptyResponse:
    choices = [_EmptyChoice()]


class _EmptyCompletions:
    async def create(self, **kwargs):
        return _EmptyResponse()


class _EmptyChat:
    completions = _EmptyCompletions()


class _EmptyClient:
    chat = _EmptyChat()


class _Delta:
    def __init__(self, content):
        self.content = content


class _StreamChoice:
    def __init__(self, content):
        self.delta = _Delta(content)


class _StreamChunk:
    def __init__(self, content):
        self.choices = [_StreamChoice(content)]


class _BufferedStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        self._iterator = iter(self._chunks)
        return self

    async def __anext__(self):
        try:
            return _StreamChunk(next(self._iterator))
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _StreamingCompletions:
    async def create(self, **kwargs):
        return _BufferedStream(["完整", "回复"])


class _StreamingChat:
    completions = _StreamingCompletions()


class _StreamingClient:
    chat = _StreamingChat()


class AIClientFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_buffered_upstream_stream_is_yielded_as_one_accountable_chunk(self):
        client = AIClient()

        async def fake_runtime_config():
            return {
                "llm_providers": [
                    {
                        "id": "primary",
                        "model": "test-model",
                        "api_key": "test-key",
                        "base_url": "https://llm.example/v1",
                        "enabled": True,
                        "priority": 1,
                    }
                ]
            }

        async def fake_provider_client(provider):
            return _StreamingClient()

        client._get_runtime_config = fake_runtime_config
        client._get_provider_client = fake_provider_client

        chunks = [
            chunk
            async for chunk in client._stream_complete_with_fallback(
                [{"role": "user", "content": "hello"}],
                temperature=0,
                max_tokens=100,
            )
        ]

        self.assertEqual(chunks, ["完整回复"])

    async def test_complete_falls_back_to_raw_codex_when_primary_is_blank(self):
        client = AIClient()

        async def fake_runtime_config():
            return {
                "llm_model": "primary-model",
                "llm_fallback_model": "gpt-5.3-codex-spark",
                "codex_model": "gpt-5.3-codex-spark",
                "llm_api_key": "primary-key",
                "llm_base_url": "http://llm.example/v1",
                "codex_api_key": "codex-key",
                "codex_base_url": "http://codex.example/v1",
            }

        async def fake_get_client():
            return _EmptyClient()

        async def fake_raw_chat_complete(**kwargs):
            self.assertEqual(kwargs["model"], "gpt-5.3-codex-spark")
            self.assertEqual(kwargs["max_tokens"], 6000)
            return "FALLBACK_OK"

        client._get_runtime_config = fake_runtime_config
        client._get_client = fake_get_client
        client._raw_chat_complete = fake_raw_chat_complete

        result = await client._complete_with_fallback(
            [{"role": "user", "content": "hello"}],
            temperature=0,
            max_tokens=6000,
        )

        self.assertEqual(result, "FALLBACK_OK")

    def test_extract_chat_content_handles_openai_compatible_payload(self):
        payload = {
            "choices": [
                {
                    "message": {
                        "content": "HELLO",
                    }
                }
            ]
        }

        self.assertEqual(AIClient._extract_chat_content(payload), "HELLO")
