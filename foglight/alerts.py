"""Alert delivery — pluggable notifiers fired on high-corroboration stories.

When a watchlist run surfaces a *new* story that is corroborated across
multiple platforms, Foglight can push an alert. Notifiers are pluggable and
configured purely via environment variables:

* **Console** — always available; prints the alert.
* **Slack**   — set ``FOGLIGHT_SLACK_WEBHOOK`` (an incoming-webhook URL).
* **Email**   — set ``FOGLIGHT_SMTP_HOST`` / ``_PORT`` / ``_USER`` /
                ``_PASS`` / ``_FROM`` / ``_TO``.

The monitor builds the alert objects (pure, side-effect-free) and the surface
layer (CLI / API) calls :func:`dispatch` to actually send them, so the core
stays testable.
"""

from __future__ import annotations

import json
import os
import smtplib
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import List, Optional, Tuple


@dataclass
class Alert:
    title: str
    summary: str
    score: float = 0.0
    sources: List[str] = field(default_factory=list)

    def as_text(self) -> str:
        src = f" [{', '.join(self.sources)}]" if self.sources else ""
        return f"• {self.title}{src} — {self.summary} (score {self.score})"


def build_alerts(clusters, new_ids, min_sources: int = 2,
                 limit: int = 5) -> List[Alert]:
    """Turn alert-worthy clusters (corroborated + containing new items) into
    Alert objects. Pure function — no side effects."""
    out: List[Alert] = []
    for c in clusters:
        corroborated = c.size >= 2 and len(c.sources) >= min_sources
        is_new = any(i in new_ids for i in c.item_ids)
        if corroborated and is_new:
            out.append(Alert(
                title=c.title,
                summary=f"{c.size} items across {len(c.sources)} platforms",
                score=c.score, sources=list(c.sources)))
    return out[:limit]


# --- notifiers --------------------------------------------------------------
class Notifier(ABC):
    name = "base"

    @abstractmethod
    def check(self) -> Tuple[bool, str]:
        ...

    @abstractmethod
    def send(self, alerts: List[Alert]) -> bool:
        ...


class ConsoleNotifier(Notifier):
    name = "console"

    def check(self):
        return True, "console notifier ready"

    def send(self, alerts):
        print("\n🔔 Foglight alerts:")
        for a in alerts:
            print("  " + a.as_text())
        return True


class SlackNotifier(Notifier):
    name = "slack"

    def __init__(self):
        self.webhook = os.getenv("FOGLIGHT_SLACK_WEBHOOK", "")

    def check(self):
        return bool(self.webhook), ("slack webhook configured" if self.webhook
                                    else "set FOGLIGHT_SLACK_WEBHOOK")

    def send(self, alerts):
        if not self.webhook:
            return False
        text = "*Foglight alerts*\n" + "\n".join(a.as_text() for a in alerts)
        payload = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            self.webhook, data=payload,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status < 300
        except Exception:
            return False


class EmailNotifier(Notifier):
    name = "email"

    def __init__(self):
        self.host = os.getenv("FOGLIGHT_SMTP_HOST", "")
        self.port = int(os.getenv("FOGLIGHT_SMTP_PORT", "587"))
        self.user = os.getenv("FOGLIGHT_SMTP_USER", "")
        self.password = os.getenv("FOGLIGHT_SMTP_PASS", "")
        self.sender = os.getenv("FOGLIGHT_SMTP_FROM", self.user)
        self.to = os.getenv("FOGLIGHT_SMTP_TO", "")

    def check(self):
        ok = bool(self.host and self.to)
        return ok, ("smtp configured" if ok
                    else "set FOGLIGHT_SMTP_HOST and FOGLIGHT_SMTP_TO")

    def send(self, alerts):
        if not (self.host and self.to):
            return False
        msg = EmailMessage()
        msg["Subject"] = f"Foglight: {len(alerts)} new corroborated stor" + \
                         ("y" if len(alerts) == 1 else "ies")
        msg["From"] = self.sender
        msg["To"] = self.to
        msg.set_content("\n".join(a.as_text() for a in alerts))
        try:
            with smtplib.SMTP(self.host, self.port, timeout=15) as s:
                s.starttls()
                if self.user:
                    s.login(self.user, self.password)
                s.send_message(msg)
            return True
        except Exception:
            return False


def configured_notifiers() -> List[Notifier]:
    """Console always; Slack/Email only when their env vars are set."""
    notifiers: List[Notifier] = [ConsoleNotifier()]
    for cls in (SlackNotifier, EmailNotifier):
        n = cls()
        if n.check()[0]:
            notifiers.append(n)
    return notifiers


def dispatch(alerts: List[Alert],
             notifiers: Optional[List[Notifier]] = None) -> dict:
    """Send alerts through each notifier. Returns {notifier_name: ok}."""
    if not alerts:
        return {}
    notifiers = notifiers if notifiers is not None else configured_notifiers()
    return {n.name: n.send(alerts) for n in notifiers}
