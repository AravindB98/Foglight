"""Domain / entity intelligence channel — passive, public data only.

Given a domain (e.g. ``example.com``) this gathers footprint facts from
keyless public sources:

* **Registration** via RDAP (registrar, created/expires dates)
* **DNS** via DNS-over-HTTPS (A / AAAA / MX / NS / TXT)
* **Certificate transparency** via crt.sh (observed subdomains)
* **Tech stack** from response headers + a slice of HTML

Everything here is read-only reconnaissance over publicly published data — no
scanning, probing, brute-forcing or any active/offensive behavior. The
channel is **domain-guarded**: if the query is not a bare domain it returns
nothing, so it never interferes with ordinary content searches. Network is
only touched when a real domain is passed.
"""

from __future__ import annotations

import json
import re
import urllib.request
from typing import List, Optional, Tuple

from ..schema import ContentItem, TIER_INTEL
from .base import Channel, register

_DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
_TIMEOUT = 10


def _normalize_domain(query: str) -> Optional[str]:
    q = (query or "").strip().lower()
    q = re.sub(r"^[a-z]+://", "", q)          # strip scheme
    q = q.split("/")[0].split("?")[0]          # strip path/query
    q = q.split("@")[-1]                        # strip userinfo
    if q.startswith("www."):
        q = q[4:]
    return q if _DOMAIN_RE.match(q) else None


def _get(url: str, as_json: bool = True):
    req = urllib.request.Request(url, headers={"User-Agent": "foglight",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        data = resp.read().decode("utf-8", "ignore")
    return json.loads(data) if as_json else data


@register
class DomainChannel(Channel):
    name = "domain"
    tier = TIER_INTEL
    requires = "none"

    def check(self) -> Tuple[bool, str]:
        return True, "domain intel ready (passive public data; needs network)"

    def search(self, query: str, limit: int = 10) -> List[ContentItem]:
        domain = _normalize_domain(query)
        if not domain:
            return []      # not a domain -> stay out of content searches
        items: List[ContentItem] = []
        for facet in (self._rdap, self._dns, self._ct, self._tech):
            try:
                it = facet(domain)
                if it:
                    items.append(it)
            except Exception:
                continue
        return items

    def read(self, url: str) -> List[ContentItem]:
        return self.search(url)

    # facets ---------------------------------------------------------------
    def _rdap(self, domain: str) -> Optional[ContentItem]:
        d = _get(f"https://rdap.org/domain/{domain}")
        events = {e.get("eventAction"): e.get("eventDate")
                  for e in d.get("events", [])}
        registrar = ""
        for ent in d.get("entities", []):
            if "registrar" in (ent.get("roles") or []):
                for field in ent.get("vcardArray", [[], []])[1]:
                    if field and field[0] == "fn":
                        registrar = field[3]
        text = (f"Registrar: {registrar or 'n/a'}\n"
                f"Registered: {events.get('registration', 'n/a')}\n"
                f"Expires: {events.get('expiration', 'n/a')}\n"
                f"Status: {', '.join(d.get('status', [])) or 'n/a'}")
        return ContentItem(source="whois", tier=TIER_INTEL,
                           title=f"Registration — {domain}", url=domain, text=text)

    def _dns(self, domain: str) -> Optional[ContentItem]:
        lines = []
        for rtype in ("A", "AAAA", "MX", "NS", "TXT"):
            try:
                d = _get(f"https://dns.google/resolve?name={domain}&type={rtype}")
                vals = [a.get("data", "") for a in d.get("Answer", [])]
                if vals:
                    lines.append(f"{rtype}: {', '.join(vals[:6])}")
            except Exception:
                continue
        if not lines:
            return None
        return ContentItem(source="dns", tier=TIER_INTEL,
                           title=f"DNS records — {domain}", url=domain,
                           text="\n".join(lines))

    def _ct(self, domain: str) -> Optional[ContentItem]:
        d = _get(f"https://crt.sh/?q=%25.{domain}&output=json")
        subs = set()
        for row in d:
            for name in (row.get("name_value", "") or "").split("\n"):
                name = name.strip().lstrip("*.")
                if name.endswith(domain):
                    subs.add(name)
        if not subs:
            return None
        ordered = sorted(subs)[:25]
        return ContentItem(source="ct_logs", tier=TIER_INTEL,
                           title=f"Subdomains (certificate transparency) — {domain}",
                           url=domain,
                           text=f"{len(subs)} observed; showing {len(ordered)}:\n"
                                + "\n".join(ordered),
                           metrics={"subdomains": float(len(subs))})

    def _tech(self, domain: str) -> Optional[ContentItem]:
        req = urllib.request.Request(f"https://{domain}",
                                     headers={"User-Agent": "foglight"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            html = resp.read(40000).decode("utf-8", "ignore").lower()
        signals = []
        for h in ("server", "x-powered-by", "via", "x-generator"):
            if headers.get(h):
                signals.append(f"{h}: {headers[h]}")
        sigs = {"wordpress": "WordPress", "wp-content": "WordPress",
                "shopify": "Shopify", "react": "React", "next.js": "Next.js",
                "_next": "Next.js", "vue": "Vue", "angular": "Angular",
                "cloudflare": "Cloudflare", "gatsby": "Gatsby",
                "drupal": "Drupal", "squarespace": "Squarespace"}
        found = sorted({label for key, label in sigs.items() if key in html})
        if found:
            signals.append("detected: " + ", ".join(found))
        if not signals:
            return None
        return ContentItem(source="techstack", tier=TIER_INTEL,
                           title=f"Tech stack — {domain}", url=domain,
                           text="\n".join(signals))
