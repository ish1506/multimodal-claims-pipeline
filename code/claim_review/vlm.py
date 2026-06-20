from __future__ import annotations

import logging
import time
from typing import Protocol

import httpx
from openai.types.chat import (
    ChatCompletionContentPartImageParam,
    ChatCompletionContentPartTextParam,
    ChatCompletionUserMessageParam,
)

from .context import ClaimContext
from .images import PreparedImage
from .prompts import build_prompt
from .usage import UsageCollector, UsageSample

LOGGER = logging.getLogger(__name__)
HTTP_LOGGER = logging.getLogger("claim_review.http")


class VLMClient(Protocol):
    """Protocol for clients that can review a claim with prepared images."""

    def complete(
        self,
        context: ClaimContext,
        images: list[PreparedImage],
        *,
        prompt_config: str,
        model: str,
    ) -> str:
        ...


class OpenAIVLMClient:
    """OpenAI-backed vision client with safe HTTP request/response logging."""

    def __init__(self, usage_collector: UsageCollector | None = None) -> None:
        """Create an OpenAI client with HTTP event hooks installed."""
        from openai import OpenAI

        http_client = httpx.Client(
            event_hooks={
                "request": [self._log_request],
                "response": [self._log_response],
            }
        )
        self._client = OpenAI(http_client=http_client)
        self._usage_collector = usage_collector

    @staticmethod
    def _safe_url(url: httpx.URL) -> str:
        return str(url.copy_with(query=None))

    @classmethod
    def _log_request(cls, request: httpx.Request) -> None:
        request.extensions["claim_review_start"] = time.monotonic()
        HTTP_LOGGER.info(
            "outgoing_http_request method=%s url=%s",
            request.method,
            cls._safe_url(request.url),
        )

    @classmethod
    def _log_response(cls, response: httpx.Response) -> None:
        start = response.request.extensions.get("claim_review_start")
        duration_ms = (time.monotonic() - start) * 1000 if isinstance(start, float) else -1
        HTTP_LOGGER.info(
            "incoming_http_response method=%s url=%s status_code=%s duration_ms=%.1f",
            response.request.method,
            cls._safe_url(response.request.url),
            response.status_code,
            duration_ms,
        )

    def complete(
        self,
        context: ClaimContext,
        images: list[PreparedImage],
        *,
        prompt_config: str,
        model: str,
    ) -> str:
        """Send one multimodal review request and return the response text."""
        prompt = build_prompt(context, prompt_config)
        content: list[ChatCompletionContentPartTextParam | ChatCompletionContentPartImageParam] = [
            {"type": "text", "text": prompt}
        ]
        for image in images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": image.data_url, "detail": "high"},
                }
            )

        messages: list[ChatCompletionUserMessageParam] = [{"role": "user", "content": content}]

        LOGGER.info(
            "vlm_request row_index=%s user_id=%s prompt_config=%s model=%s image_count=%s image_ids=%s",
            context.row_index,
            context.user_id,
            prompt_config,
            model,
            len(images),
            ",".join(image.image_id for image in images),
        )
        if prompt_config == "concise_v1":
            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=1200,
                response_format={"type": "json_object"},
            )
        else:
            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=1200,
            )
        LOGGER.info("vlm_response row_index=%s finish_reason=%s", context.row_index, response.choices[0].finish_reason)
        if response.usage is not None:
            LOGGER.info(
                "vlm_usage row_index=%s prompt_config=%s model=%s image_count=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s",
                context.row_index,
                prompt_config,
                model,
                len(images),
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                response.usage.total_tokens,
            )
            if self._usage_collector is not None:
                self._usage_collector.record(
                    UsageSample(
                        row_index=context.row_index,
                        prompt_config=prompt_config,
                        model=model,
                        image_count=len(images),
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                        total_tokens=response.usage.total_tokens,
                    )
                )
        return response.choices[0].message.content or ""
