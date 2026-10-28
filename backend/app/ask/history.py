"""Each person's last questions on the Ask page, with the answers they got, kept on the server so the
page shows them again when they come back. Only the newest KEPT_PER_PERSON are kept.
Reading the shop is not a change to business data, so nothing here goes to the audit log."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AskedQuestion, User

KEPT_PER_PERSON = 20


def remember(db: Session, user: User, question: str, kind: str, answer: dict) -> None:
    """Saves one question and its answer, then forgets the person's older ones beyond KEPT_PER_PERSON."""
    db.add(AskedQuestion(organization_id=user.organization_id, user_id=user.id, question=question, kind=kind, answer=answer))
    db.flush()
    kept = select(AskedQuestion.id).where(*_mine(user)).order_by(AskedQuestion.created_at.desc()).limit(KEPT_PER_PERSON)
    db.execute(delete(AskedQuestion).where(*_mine(user), AskedQuestion.id.not_in(kept)))
    db.commit()


def recent(db: Session, user: User) -> list[AskedQuestion]:
    """The person's last questions, oldest first (the order the page shows them)."""
    newest = db.scalars(
        select(AskedQuestion).where(*_mine(user)).order_by(AskedQuestion.created_at.desc()).limit(KEPT_PER_PERSON)
    ).all()
    return list(reversed(newest))


def forget(db: Session, user: User) -> None:
    db.execute(delete(AskedQuestion).where(*_mine(user)))
    db.commit()


def _mine(user: User) -> tuple:
    return (AskedQuestion.organization_id == user.organization_id, AskedQuestion.user_id == user.id)
