"""Transport-neutral contract for digest inputs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol

from ai_brief.digest.imap_client import Attachment

DigestKind = Literal["events", "builder", "research", "engineering", "agent"]


@dataclass(frozen=True)
class DigestEnvelope:
    kind: DigestKind
    message_id: str
    subject: str
    received_at: datetime
    requested_date: date
    matched_date: date | None
    used_fallback: bool
    text: str | None
    html: str | None
    attachments: tuple[Attachment, ...]

    def metadata(self) -> dict[str, object]:
        """Return source metadata safe to persist in run records."""
        return {
            "kind": self.kind,
            "message_id": self.message_id,
            "subject": self.subject,
            "received_at": self.received_at.isoformat(),
            "requested_date": self.requested_date.isoformat(),
            "matched_date": self.matched_date.isoformat() if self.matched_date else None,
            "used_fallback": self.used_fallback,
            "attachments": [
                {
                    "filename": attachment.filename,
                    "content_type": attachment.content_type,
                    "size_bytes": len(attachment.data),
                }
                for attachment in self.attachments
            ],
        }


class DigestInputAdapter(Protocol):
    def fetch(self, brief_date: date) -> dict[DigestKind, DigestEnvelope | None]: ...
