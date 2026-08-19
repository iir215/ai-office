from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.company import Company
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse, MessageResponse
from app.services.director import get_or_create_conversation, handle_user_message


router = APIRouter(
    tags=["Chat"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/chat/", response_model=ChatResponse)
def send_chat_message(
    chat_data: ChatRequest,
    db: Session = Depends(get_db),
):
    company = (
        db.query(Company)
        .filter(Company.id == chat_data.company_id)
        .first()
    )

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found",
        )

    user = (
        db.query(User)
        .filter(User.id == chat_data.user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    conversation = get_or_create_conversation(
        db,
        chat_data.company_id,
        chat_data.user_id,
        chat_data.conversation_id,
    )

    reply = handle_user_message(db, conversation, chat_data.message)

    return ChatResponse(conversation_id=conversation.id, reply=reply)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
def get_conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
):
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )
