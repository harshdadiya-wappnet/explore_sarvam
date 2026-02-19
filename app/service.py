from sarvamai import AsyncSarvamAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import os
from dotenv import load_dotenv

from app.database.models import Conversation, Message, Role

load_dotenv()

client = AsyncSarvamAI(
    api_subscription_key=os.getenv("SARVAM_API_KEY"),
)

async def get_response(input_text: str) -> str:
    """
    This is method is to get response from the ai model.
    
    :param input_text: input given by user.
    :type input_text: str
    :return: Output given by AI.
    :rtype: str
    """
    response = await client.chat.completions(
        messages=[{"content": input_text, "role": "user"}],
    )

    final_result = "I could not generate a response right now."
    for i in response.choices:
        if i.finish_reason == "stop":
            final_result = i.message.content

    return final_result


async def create_conversation(db: AsyncSession, title: str | None = None) -> Conversation:
    """Create and persist a new conversation."""
    conversation = Conversation(title=title)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def save_message(
    db: AsyncSession,
    conversation_id: int,
    role: Role,
    content: str,
) -> Message:
    """Persist a single message in an existing conversation."""
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def save_chat_exchange(
    db: AsyncSession,
    conversation_id: int,
    user_message: str,
    assistant_message: str,
) -> tuple[Message, Message]:
    """Save user and assistant messages for one exchange."""
    user_row = Message(
        conversation_id=conversation_id,
        role=Role.USER,
        content=user_message,
    )
    assistant_row = Message(
        conversation_id=conversation_id,
        role=Role.ASSISTANT,
        content=assistant_message,
    )
    db.add_all([user_row, assistant_row])
    await db.commit()
    await db.refresh(user_row)
    await db.refresh(assistant_row)
    return user_row, assistant_row


async def get_conversation(db: AsyncSession, conversation_id: int) -> Conversation | None:
    """Fetch a conversation by id."""
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
