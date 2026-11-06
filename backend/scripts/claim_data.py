"""Hand the data from before accounts existed to your account (docs/decisions.md D29).

Register in the app first, then from backend/:
    python -m scripts.claim_data you@example.com
Every workspace the placeholder owns becomes yours (as owner), with its tutor conversations, quizzes, progress
and lesson feedback; then the placeholder account is deleted.
"""

import sys

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.modules.users.models import User

LEGACY = "legacy@semsaviour.invalid"
OWNED = [("tutor_sessions", "user_id"), ("quizzes", "user_id"), ("lesson_feedback", "user_id"), ("lessons", "owner_id"),
         ("courses", "created_by"), ("documents", "uploaded_by"), ("jobs", "user_id"), ("llm_usage", "user_id")]


def claim(db: Session, email: str) -> int:
    """Returns how many workspaces changed hands. The caller commits."""
    legacy = db.scalar(select(User.id).where(User.email == LEGACY))
    target = db.scalar(select(User.id).where(User.email == email.strip().lower()))
    if legacy is None:
        raise SystemExit("Nothing to claim: there's no unclaimed data.")
    if target is None:
        raise SystemExit(f"No account for {email}. Register in the app first, then run this again.")
    ids = {"legacy": legacy, "target": target}
    # An existing membership in a claimed workspace gives way to ownership; progress the account already has wins.
    db.execute(text("DELETE FROM workspace_members WHERE user_id = :target AND workspace_id IN "
                    "(SELECT workspace_id FROM workspace_members WHERE user_id = :legacy)"), ids)
    claimed = db.execute(text("UPDATE workspace_members SET user_id = :target WHERE user_id = :legacy"), ids).rowcount
    db.execute(text("DELETE FROM topic_progress WHERE user_id = :legacy AND topic_id IN "
                    "(SELECT topic_id FROM topic_progress WHERE user_id = :target)"), ids)
    db.execute(text("UPDATE topic_progress SET user_id = :target WHERE user_id = :legacy"), ids)
    for table, column in OWNED:
        db.execute(text(f"UPDATE {table} SET {column} = :target WHERE {column} = :legacy"), ids)
    db.execute(text("DELETE FROM users WHERE id = :legacy"), ids)
    return claimed


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    with SessionLocal() as session:
        count = claim(session, sys.argv[1])
        session.commit()
    print(f"{count} workspace(s) are now owned by {sys.argv[1]}.")
