from typing import Any

import httpx
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sarvamai import AsyncSarvamAI
from sarvamai.core.api_error import ApiError

class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = "sarvam-m"
    messages: list[ChatMessage]
    max_tokens: int | None = 512
    temperature: float | None = 0.1
    top_p: float | None = None
    n: int | None = 1
    stream: bool | None = False
    stop: str | list[str] | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    seed: int | None = None
    reasoning_effort: str | None = None
    wiki_grounding: bool | None = None


class OpenAIError(BaseModel):
    message: str
    type: str = "invalid_request_error"
    param: str | None = None
    code: str | None = None


class OpenAIErrorResponse(BaseModel):
    error: OpenAIError


class ModelData(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "sarvam"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[ModelData] = Field(default_factory=list)


app = FastAPI(title="OpenAI-to-Sarvam Bridge")
SARVAM_CHAT_COMPLETIONS_URL = "https://api.sarvam.ai/v1/chat/completions"


def _error_response(
    status_code: int,
    message: str,
    error_type: str,
    param: str | None = None,
    code: str | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=OpenAIErrorResponse(
            error=OpenAIError(
                message=message,
                type=error_type,
                param=param,
                code=code,
            )
        ).model_dump(),
    )


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None

    token = authorization[len(prefix) :].strip()
    if not token:
        return None
    return token


@app.get("/v1/models", response_model=ModelListResponse)
@app.get("/models", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    return ModelListResponse(data=[ModelData(id="sarvam-m")])


@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    authorization: str | None = Header(default=None),
) -> Any:
    token = _extract_bearer_token(authorization)
    if token is None:
        return _error_response(
            status_code=401,
            message="Missing or invalid Authorization header. Use: Authorization: Bearer <SARVAM_API_KEY>",
            error_type="authentication_error",
            code="invalid_api_key",
        )

    if request.stream:
        return await _stream_chat_completions(request, token)

    sarvam_client = AsyncSarvamAI(api_subscription_key=token)

    try:
        sarvam_response = await sarvam_client.chat.completions(**_build_sdk_kwargs(request))
    except ApiError as exc:
        status = exc.status_code or 500
        return _error_response(
            status_code=status,
            message=str(exc.body) if exc.body is not None else str(exc),
            error_type="api_error" if status >= 500 else "invalid_request_error",
            code="upstream_error",
        )
    except Exception as exc:
        return _error_response(
            status_code=500,
            message=str(exc),
            error_type="api_error",
            code="bridge_error",
        )
    finally:
        # AsyncSarvamAI currently doesn't expose a public close(); close underlying http client if present.
        httpx_client = getattr(getattr(sarvam_client, "_client_wrapper", None), "httpx_client", None)
        if httpx_client is not None and hasattr(httpx_client, "aclose"):
            await httpx_client.aclose()

    response_payload: dict[str, Any] = {
        "id": sarvam_response.id,
        "object": sarvam_response.object,
        "created": sarvam_response.created,
        "model": sarvam_response.model or request.model,
        "choices": [
            {
                "index": choice.index,
                "message": {
                    "role": choice.message.role,
                    "content": choice.message.content,
                    "reasoning_content": getattr(choice.message, "reasoning_content", None),
                },
                "finish_reason": choice.finish_reason,
            }
            for choice in sarvam_response.choices
        ],
    }

    if sarvam_response.usage is not None:
        response_payload["usage"] = {
            "prompt_tokens": sarvam_response.usage.prompt_tokens,
            "completion_tokens": sarvam_response.usage.completion_tokens,
            "total_tokens": sarvam_response.usage.total_tokens,
        }

    return response_payload


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content)


def _build_payload(request: ChatCompletionRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": request.model,
        "messages": [{"role": m.role, "content": _normalize_content(m.content)} for m in request.messages]
    }

    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.top_p is not None:
        payload["top_p"] = request.top_p
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    if request.n is not None:
        payload["n"] = request.n
    if request.stop is not None:
        payload["stop"] = request.stop
    if request.frequency_penalty is not None:
        payload["frequency_penalty"] = request.frequency_penalty
    if request.presence_penalty is not None:
        payload["presence_penalty"] = request.presence_penalty
    if request.seed is not None:
        payload["seed"] = request.seed
    if request.reasoning_effort is not None:
        payload["reasoning_effort"] = request.reasoning_effort
    if request.wiki_grounding is not None:
        payload["wiki_grounding"] = request.wiki_grounding
    if request.stream is not None:
        payload["stream"] = request.stream

    return payload


def _build_sdk_kwargs(request: ChatCompletionRequest) -> dict[str, Any]:
    payload = _build_payload(request)
    payload.pop("model", None)
    payload.pop("stream", None)
    return payload


async def _stream_chat_completions(request: ChatCompletionRequest, token: str) -> Any:
    client = httpx.AsyncClient(timeout=None)
    req = client.build_request(
        method="POST",
        url=SARVAM_CHAT_COMPLETIONS_URL,
        headers={
            "api-subscription-key": token,
            "content-type": "application/json",
            "accept": "text/event-stream",
        },
        json=_build_payload(request),
    )
    upstream = await client.send(req, stream=True)
    if upstream.status_code >= 400:
        try:
            body = await upstream.json()
        except Exception:
            raw = await upstream.aread()
            body = {"error": {"message": raw.decode("utf-8", errors="replace")}}
        finally:
            await upstream.aclose()
            await client.aclose()

        if isinstance(body, dict) and "error" in body:
            return JSONResponse(status_code=upstream.status_code, content=body)
        return _error_response(
            status_code=upstream.status_code,
            message=str(body),
            error_type="api_error" if upstream.status_code >= 500 else "invalid_request_error",
            code="upstream_error",
        )

    async def event_stream():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    media_type = upstream.headers.get("content-type", "text/event-stream")
    return StreamingResponse(event_stream(), media_type=media_type)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app=app, host="0.0.0.0", port=8000)
