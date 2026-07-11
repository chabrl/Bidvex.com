"""
BidVex Community Q&A Router
Handles community questions and replies (comments).
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from deps import User, get_current_user
import uuid
import logging

logger = logging.getLogger(__name__)

community_router = APIRouter(prefix="/community", tags=["Community"])

_db = None

def set_db(db_instance):
    global _db
    _db = db_instance

def get_db():
    if _db is None:
        raise RuntimeError("Community DB not initialised")
    return _db


@community_router.get("/questions")
async def get_questions(
    limit: int = 20,
    skip: int = 0,
    search: Optional[str] = None,
    sort: str = "newest",
):
    """Get paginated list of community questions."""
    db = get_db()
    query = {}
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"body": {"$regex": search, "$options": "i"}},
        ]

    sort_field = "created_at"
    sort_order = -1
    if sort == "most_replies":
        sort_field = "reply_count"
    elif sort == "most_upvoted":
        sort_field = "upvote_count"

    total = await db.community_questions.count_documents(query)
    questions = (
        await db.community_questions.find(query, {"_id": 0})
        .sort(sort_field, sort_order)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )
    return {"questions": questions, "total": total}


@community_router.get("/questions/{question_id}")
async def get_question(question_id: str):
    """Get a single question with its replies."""
    db = get_db()
    question = await db.community_questions.find_one({"id": question_id}, {"_id": 0})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Increment views
    await db.community_questions.update_one(
        {"id": question_id}, {"$inc": {"views": 1}}
    )

    replies = (
        await db.community_replies.find({"question_id": question_id}, {"_id": 0})
        .sort("created_at", 1)
        .to_list(200)
    )
    question["replies"] = replies
    return question


@community_router.post("/questions")
async def create_question(
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """Create a new community question."""
    db = get_db()
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()

    if not title or len(title) < 5:
        raise HTTPException(status_code=400, detail="Title must be at least 5 characters")
    if not body or len(body) < 10:
        raise HTTPException(status_code=400, detail="Body must be at least 10 characters")

    question = {
        "id": str(uuid.uuid4()),
        "title": title,
        "body": body,
        "author_id": current_user.id,
        "author_name": current_user.name or current_user.email.split("@")[0],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reply_count": 0,
        "upvote_count": 0,
        "upvoters": [],
        "views": 0,
        "best_reply_id": None,
    }
    await db.community_questions.insert_one(question)
    question.pop("_id", None)
    return question


@community_router.post("/questions/{question_id}/replies")
async def create_reply(
    question_id: str,
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """Add a reply to a question."""
    db = get_db()
    question = await db.community_questions.find_one({"id": question_id})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    body = (data.get("body") or "").strip()
    if not body or len(body) < 5:
        raise HTTPException(status_code=400, detail="Reply must be at least 5 characters")

    reply = {
        "id": str(uuid.uuid4()),
        "question_id": question_id,
        "body": body,
        "author_id": current_user.id,
        "author_name": current_user.name or current_user.email.split("@")[0],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "upvote_count": 0,
        "upvoters": [],
        "is_best": False,
    }
    await db.community_replies.insert_one(reply)
    await db.community_questions.update_one(
        {"id": question_id}, {"$inc": {"reply_count": 1}}
    )
    reply.pop("_id", None)
    return reply


@community_router.post("/questions/{question_id}/upvote")
async def upvote_question(
    question_id: str,
    current_user: User = Depends(get_current_user),
):
    """Toggle upvote on a question."""
    db = get_db()
    question = await db.community_questions.find_one({"id": question_id})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    upvoters = question.get("upvoters", [])
    if current_user.id in upvoters:
        await db.community_questions.update_one(
            {"id": question_id},
            {"$pull": {"upvoters": current_user.id}, "$inc": {"upvote_count": -1}},
        )
        return {"status": "removed", "upvote_count": question.get("upvote_count", 1) - 1}
    else:
        await db.community_questions.update_one(
            {"id": question_id},
            {"$push": {"upvoters": current_user.id}, "$inc": {"upvote_count": 1}},
        )
        return {"status": "added", "upvote_count": question.get("upvote_count", 0) + 1}


@community_router.post("/replies/{reply_id}/upvote")
async def upvote_reply(
    reply_id: str,
    current_user: User = Depends(get_current_user),
):
    """Toggle upvote on a reply."""
    db = get_db()
    reply = await db.community_replies.find_one({"id": reply_id})
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")

    upvoters = reply.get("upvoters", [])
    if current_user.id in upvoters:
        await db.community_replies.update_one(
            {"id": reply_id},
            {"$pull": {"upvoters": current_user.id}, "$inc": {"upvote_count": -1}},
        )
        return {"status": "removed", "upvote_count": reply.get("upvote_count", 1) - 1}
    else:
        await db.community_replies.update_one(
            {"id": reply_id},
            {"$push": {"upvoters": current_user.id}, "$inc": {"upvote_count": 1}},
        )
        return {"status": "added", "upvote_count": reply.get("upvote_count", 0) + 1}


@community_router.post("/questions/{question_id}/best-reply")
async def mark_best_reply(
    question_id: str,
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """Mark a reply as best answer (only question author can do this)."""
    db = get_db()
    question = await db.community_questions.find_one({"id": question_id})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    if question["author_id"] != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Only the question author can mark best reply")

    reply_id = data.get("reply_id")
    # Unset previous best
    await db.community_replies.update_many(
        {"question_id": question_id}, {"$set": {"is_best": False}}
    )
    # Set new best
    await db.community_replies.update_one(
        {"id": reply_id, "question_id": question_id}, {"$set": {"is_best": True}}
    )
    await db.community_questions.update_one(
        {"id": question_id}, {"$set": {"best_reply_id": reply_id}}
    )
    return {"status": "ok"}
