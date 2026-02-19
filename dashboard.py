import asyncio
import json
import os
from datetime import datetime
from urllib import error, request

import chainlit as cl
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = f"http://localhost:{os.getenv("DEPLOYMENT_PORT")}"
CONVERSATION_KEY = "conversation_id"


def _http_post(path: str, payload: dict) -> dict:
    """Run a JSON POST request to the FastAPI backend."""
    req = request.Request(
        url=f"{API_BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"API request failed ({exc.code}): {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(
            f"Could not connect to API server at {API_BASE_URL}. Is server.py running?"
        ) from exc


async def _create_conversation() -> int:
    title = f"Chainlit chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    response = await asyncio.to_thread(_http_post, "/chat/conversations", {"title": title})
    conversation_id = response.get("id")
    if not conversation_id:
        raise RuntimeError("Conversation creation failed: missing id in API response.")
    return int(conversation_id)


async def _send_message(conversation_id: int, content: str) -> str:
    response = await asyncio.to_thread(
        _http_post,
        f"/chat/conversations/{conversation_id}/messages",
        {"message": content},
    )
    assistant = response.get("assistant_message") or {}
    assistant_text = assistant.get("content")
    if not assistant_text:
        raise RuntimeError("Chat API response missing assistant message content.")
    return assistant_text


@cl.on_chat_start
async def on_chat_start() -> None:
    try:
        conversation_id = await _create_conversation()
        cl.user_session.set(CONVERSATION_KEY, conversation_id)
    except RuntimeError as exc:
        await cl.Message(content=str(exc)).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    conversation_id = cl.user_session.get(CONVERSATION_KEY)

    if conversation_id is None:
        try:
            conversation_id = await _create_conversation()
            cl.user_session.set(CONVERSATION_KEY, conversation_id)
        except RuntimeError as exc:
            await cl.Message(content=str(exc)).send()
            return

    try:
        assistant_text = await _send_message(conversation_id=conversation_id, content=message.content)
    except RuntimeError as exc:
        await cl.Message(content=str(exc)).send()
        return

    await cl.Message(content=assistant_text).send()
