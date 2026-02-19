from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database.models import Conversation, Message, Role
from app.service import (
    create_conversation,
    get_conversation,
    get_response,
    save_chat_exchange,
)

router = APIRouter(prefix="/chat", tags=["chat with sarvam"])


class CreateConversationRequest(BaseModel):
    title: str | None = None


class ConversationResponse(BaseModel):
    id: int
    title: str | None


class ChatRequest(BaseModel):
    message: str


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: Role
    content: str


class ConversationHistoryResponse(BaseModel):
    conversation_id: int
    title: str | None
    messages: list[MessageResponse]


class ChatResponse(BaseModel):
    conversation_id: int
    user_message: MessageResponse
    assistant_message: MessageResponse


def _serialize_message(message: Message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
    )


@router.post("/conversations", response_model=ConversationResponse)
async def start_conversation(
    payload: CreateConversationRequest,
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    conversation = await create_conversation(db, title=payload.title)
    return ConversationResponse(id=conversation.id, title=conversation.title)


@router.get("/conversations/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
) -> ConversationHistoryResponse:
    conversation: Conversation | None = await get_conversation(db, conversation_id=conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationHistoryResponse(
        conversation_id=conversation.id,
        title=conversation.title,
        messages=[_serialize_message(message) for message in conversation.messages],
    )


@router.post("/conversations/{conversation_id}/messages", response_model=ChatResponse)
async def chat(
    conversation_id: int,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    conversation = await get_conversation(db, conversation_id=conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    assistant_text = await get_response(payload.message)
    user_msg, assistant_msg = await save_chat_exchange(
        db=db,
        conversation_id=conversation_id,
        user_message=payload.message,
        assistant_message=assistant_text,
    )

    return ChatResponse(
        conversation_id=conversation_id,
        user_message=_serialize_message(user_msg),
        assistant_message=_serialize_message(assistant_msg),
    )
