from typing import Any
import uuid
from datetime import datetime

import httpx
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sarvamai import AsyncSarvamAI
from sarvamai.core.api_error import ApiError


# ==================== Request Models ====================

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


class ResponsesAPIRequest(BaseModel):
    """OpenAI Responses API request model"""
    model_config = ConfigDict(extra="allow")

    model: str = "sarvam-m"
    input: str | list[dict[str, Any]] | None = None
    instructions: str | None = None
    # OpenAI Responses API uses `max_output_tokens`; keep `max_tokens`
    # as an optional legacy alias so both shapes are accepted.
    max_output_tokens: int | None = None
    max_tokens: int | None = None
    temperature: float | None = 0.1
    top_p: float | None = None
    stream: bool | None = False
    store: bool | None = True
    previous_response_id: str | None = None
    # Additional params
    stop: str | list[str] | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    seed: int | None = None
    reasoning_effort: str | None = None
    wiki_grounding: bool | None = None


# ==================== Error Models ====================

class OpenAIError(BaseModel):
    message: str
    type: str = "invalid_request_error"
    param: str | None = None
    code: str | None = None


class OpenAIErrorResponse(BaseModel):
    error: OpenAIError


# ==================== Model List Models ====================

class ModelData(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "sarvam"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[ModelData] = Field(default_factory=list)


# ==================== FastAPI Setup ====================

app = FastAPI(title="OpenAI-to-Sarvam Bridge")
SARVAM_CHAT_COMPLETIONS_URL = "https://api.sarvam.ai/v1/chat/completions"


# ==================== Helper Functions ====================

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


def _normalize_content(content: Any) -> str:
    """Convert various content formats to string"""
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


def _convert_input_to_messages(
    input_data: str | list[dict[str, Any]] | None,
    instructions: str | None
) -> list[dict[str, str]]:
    """Convert Responses API input to Chat Completions messages format"""
    messages = []
    
    # Add instructions as system message if provided
    if instructions:
        messages.append({"role": "system", "content": instructions})
    
    # Process input
    if isinstance(input_data, str):
        messages.append({"role": "user", "content": input_data})
    elif isinstance(input_data, list):
        for item in input_data:
            if isinstance(item, dict):
                role = item.get("role", "user")
                content = item.get("content")
                if content is not None:
                    messages.append({
                        "role": role,
                        "content": _normalize_content(content)
                    })
    
    return messages


def _build_payload(request: ChatCompletionRequest) -> dict[str, Any]:
    """Build request payload for Sarvam API"""
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


def _build_responses_payload(request: ResponsesAPIRequest) -> dict[str, Any]:
    """Build request payload for Responses API -> Sarvam conversion"""
    messages = _convert_input_to_messages(request.input, request.instructions)

    payload: dict[str, Any] = {
        "model": request.model,
        "messages": messages
    }

    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.top_p is not None:
        payload["top_p"] = request.top_p
    # Map Responses-style token params to Sarvam's `max_tokens`
    effective_max_tokens = request.max_output_tokens
    if effective_max_tokens is None and request.max_tokens is not None:
        effective_max_tokens = request.max_tokens
    if effective_max_tokens is not None:
        payload["max_tokens"] = effective_max_tokens
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
    """Extract SDK kwargs from Chat Completions request"""
    payload = _build_payload(request)
    payload.pop("model", None)
    payload.pop("stream", None)
    return payload


def _build_responses_sdk_kwargs(request: ResponsesAPIRequest) -> dict[str, Any]:
    """Extract SDK kwargs from Responses API request"""
    payload = _build_responses_payload(request)
    payload.pop("model", None)
    payload.pop("stream", None)
    return payload


# ==================== Routes ====================

@app.get("/v1/models", response_model=ModelListResponse)
@app.get("/models", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    """List available models"""
    return ModelListResponse(data=[ModelData(id="sarvam-m")])


# ==================== Chat Completions Endpoints ====================

@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    authorization: str | None = Header(default=None),
) -> Any:
    """Chat Completions API endpoint (backward compatible)"""
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


async def _stream_chat_completions(request: ChatCompletionRequest, token: str) -> Any:
    """Stream Chat Completions response"""
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


# ==================== Responses API Endpoints ====================

@app.post("/v1/responses")
@app.post("/responses")
async def responses_create(
    request: ResponsesAPIRequest,
    authorization: str | None = Header(default=None),
) -> Any:
    """Responses API endpoint (new OpenAI primitive)"""
    token = _extract_bearer_token(authorization)
    if token is None:
        return _error_response(
            status_code=401,
            message="Missing or invalid Authorization header. Use: Authorization: Bearer <SARVAM_API_KEY>",
            error_type="authentication_error",
            code="invalid_api_key",
        )

    if not request.input and not request.instructions:
        return _error_response(
            status_code=400,
            message="Either 'input' or 'instructions' must be provided",
            error_type="invalid_request_error",
            code="missing_input",
        )

    if request.stream:
        return await _stream_responses(request, token)

    sarvam_client = AsyncSarvamAI(api_subscription_key=token)

    try:
        sarvam_response = await sarvam_client.chat.completions(**_build_responses_sdk_kwargs(request))
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
        httpx_client = getattr(getattr(sarvam_client, "_client_wrapper", None), "httpx_client", None)
        if httpx_client is not None and hasattr(httpx_client, "aclose"):
            await httpx_client.aclose()

    # Convert Chat Completions response to Responses API format
    response_id = f"resp_{uuid.uuid4().hex[:32]}"
    message_id = f"msg_{uuid.uuid4().hex[:32]}"
    
    # Extract text content from first choice
    message_text = ""
    if sarvam_response.choices and len(sarvam_response.choices) > 0:
        message_text = sarvam_response.choices[0].message.content or ""

    response_payload: dict[str, Any] = {
        "id": response_id,
        "object": "response",
        "created_at": int(datetime.now().timestamp()),
        "model": sarvam_response.model or request.model,
        "output": [
            {
                "id": message_id,
                "type": "message",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": message_text,
                        "annotations": [],
                        "logprobs": []
                    }
                ],
                "role": "assistant"
            }
        ]
    }

    # Add usage if available
    if sarvam_response.usage is not None:
        response_payload["usage"] = {
            "prompt_tokens": sarvam_response.usage.prompt_tokens,
            "completion_tokens": sarvam_response.usage.completion_tokens,
            "total_tokens": sarvam_response.usage.total_tokens,
        }

    return response_payload


async def _stream_responses(request: ResponsesAPIRequest, token: str) -> Any:
    """Stream Responses API response"""
    client = httpx.AsyncClient(timeout=None)
    req = client.build_request(
        method="POST",
        url=SARVAM_CHAT_COMPLETIONS_URL,
        headers={
            "api-subscription-key": token,
            "content-type": "application/json",
            "accept": "text/event-stream",
        },
        json=_build_responses_payload(request),
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
        """Transform Chat Completions SSE to Responses API SSE format"""
        try:
            response_id = f"resp_{uuid.uuid4().hex[:32]}"
            message_id = f"msg_{uuid.uuid4().hex[:32]}"
            
            async for chunk in upstream.aiter_raw():
                # Parse SSE chunks and transform them
                chunk_str = chunk.decode('utf-8', errors='replace')
                
                # Transform chunk format if needed
                # For now, pass through - you might want to parse and reformat SSE events
                if chunk_str.startswith('data:'):
                    # Parse the chat completion event and transform to responses format
                    yield chunk
                else:
                    yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    media_type = upstream.headers.get("content-type", "text/event-stream")
    return StreamingResponse(event_stream(), media_type=media_type)


# ==================== Health Check ====================

@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint"""
    return {"status": "ok", "service": "openai-to-sarvam-bridge"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app=app, host="0.0.0.0", port=8000)