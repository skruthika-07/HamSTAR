"""Tiara, streaks, badges, corrected mistakes and the certificate. Every award goes through the ledger exactly once."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import BADGES, Badge, Certificate, Reward, User
from ..models.base import new_id, now


def _once(db: Session, user: User, kind: str, ref: str, amount: int = 1) -> bool:
    """Record a reward unless this exact one is already in the ledger. Returns whether it is new."""
    if db.scalar(select(Reward.id).where(Reward.user_id == user.id, Reward.kind == kind, Reward.ref == ref)):
        return False
    db.add(Reward(user_id=user.id, kind=kind, ref=ref, amount=amount))
    return True


def record_answer(user: User, correct: bool) -> None:
    """An answered question (right or wrong) keeps the no-skip run going; only a right one extends the streak."""
    user.answered_count += 1
    user.noskip_count += 1
    if correct:
        user.correct_count += 1
        user.current_streak += 1
        user.longest_streak = max(user.longest_streak, user.current_streak)
    else:
        user.current_streak = 0


def record_skip(user: User) -> None:
    """No Tiara, no mistake, no diagnosis. Both runs are broken."""
    user.skipped_count += 1
    user.current_streak = 0
    user.noskip_count = 0


def award_tiara(db: Session, user: User, attempt_id: str) -> int:
    """One correct question = one Tiara, once per attempt however often the request is repeated."""
    if not _once(db, user, "TIARA", attempt_id):
        return 0
    user.tiara_count += 1
    return 1


def award_correction(db: Session, user: User, session_id: str) -> bool:
    """A mistake counts as corrected once, and only after understanding was shown above the threshold."""
    if not _once(db, user, "CORRECTION", session_id):
        return False
    user.mistakes_corrected += 1
    return True


def add_demo_tiara(db: Session, user: User, amount: int) -> None:
    _once(db, user, "DEMO", new_id(), amount)
    user.tiara_count += amount


def badge_progress(user: User) -> dict[str, int]:
    return {"streak": user.current_streak, "noskip": user.noskip_count, "mistakes": user.mistakes_corrected}


def check_unlocks(db: Session, user: User) -> list[dict]:
    """Grant any badge or the certificate whose requirement has just been met. Returns what is new."""
    unlocked: list[dict] = []
    have = set(db.scalars(select(Badge.code).where(Badge.user_id == user.id)))
    progress = badge_progress(user)
    for code, (_, _, target) in BADGES.items():
        if code not in have and progress[code] >= target:
            db.add(Badge(user_id=user.id, code=code))
            unlocked.append({"kind": "badge", "badge": code})
    if user.tiara_count >= get_settings().tiara_for_certificate and not db.scalar(select(Certificate.id).where(Certificate.user_id == user.id)):
        token = new_id()
        db.add(Certificate(user_id=user.id, code=f"HS-{now().year}-{token[:6].upper()}", share_token=token, certificate_url=f"/certificate/{token}"))
        unlocked.append({"kind": "certificate"})
    return unlocked


def iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


def badges_view(db: Session, user: User) -> list[dict]:
    got = {b.code: b.unlocked_at for b in db.scalars(select(Badge).where(Badge.user_id == user.id))}
    progress = badge_progress(user)
    return [
        {"id": code, "name": name, "requirement": req, "target": target, "progress": target if code in got else min(progress[code], target), "unlocked": code in got, "unlocked_at": iso(got.get(code))}
        for code, (name, req, target) in BADGES.items()
    ]


def certificate_view(db: Session, user: User) -> dict:
    target = get_settings().tiara_for_certificate
    c = db.scalar(select(Certificate).where(Certificate.user_id == user.id))
    return {
        "status": "certificate_unlocked" if c else "certificate_locked",
        "unlocked": bool(c),
        "target": target,
        "tiara": user.tiara_count,
        "to_go": max(0, target - user.tiara_count),
        "id": c.code if c else None,
        "unlocked_at": iso(c.unlocked_at) if c else None,
        "certificate_url": c.certificate_url if c else None,
        "share_token": c.share_token if c else None,
    }
