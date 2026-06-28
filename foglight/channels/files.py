"""File-ingestion channel — turn local documents into normalized items.

Reads text, markdown, code, JSON/CSV and HTML with the standard library, and
PDFs when ``pypdf`` is installed. Point it at a file or a directory and it
yields :class:`ContentItem`s ready to remember, brief, or mine into the graph.

It is **path-guarded**: ``search()`` only acts when the query is an existing
path, so it never fires on ordinary content queries. (Image OCR and video
transcription are intentionally out of scope here — wire the Supermemory
backend for those; this channel stays dependency-light.)
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

from ..schema import ContentItem, TIER_WEB, TIER_CODE
from .base import Channel, register

TEXT_EXT = {".txt", ".md", ".markdown", ".rst", ".json", ".csv", ".tsv",
            ".html", ".htm", ".log", ".yaml", ".yml"}
CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
            ".c", ".cpp", ".h", ".rb", ".sh", ".sql"}
_MAX_CHARS = 200_000


@register
class FileChannel(Channel):
    name = "files"
    tier = TIER_WEB
    requires = "none"

    def check(self) -> Tuple[bool, str]:
        try:
            import pypdf  # noqa: F401
            return True, "file ingest ready (text/code/json/html + PDF)"
        except Exception:
            return True, "file ingest ready (text/code/json/html; PDF needs pypdf)"

    def search(self, query: str, limit: int = 50) -> List[ContentItem]:
        if not query or not os.path.exists(query):
            return []          # not a path -> stay out of content searches
        return self._ingest(query, limit)

    def read(self, url: str) -> List[ContentItem]:
        path = url[7:] if url.startswith("file://") else url
        return self._ingest(path, 1000)

    # internal -------------------------------------------------------------
    def _ingest(self, path: str, limit: int) -> List[ContentItem]:
        items: List[ContentItem] = []
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for fname in sorted(files):
                    it = self._read_one(os.path.join(root, fname))
                    if it:
                        items.append(it)
                    if len(items) >= limit:
                        return items
        else:
            it = self._read_one(path)
            if it:
                items.append(it)
        return items[:limit]

    def _read_one(self, path: str) -> Optional[ContentItem]:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            text = self._pdf_text(path)
        elif ext in TEXT_EXT or ext in CODE_EXT:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    text = fh.read(_MAX_CHARS)
            except Exception:
                return None
        else:
            return None
        tier = TIER_CODE if ext in CODE_EXT else TIER_WEB
        return ContentItem(source="file", tier=tier,
                           title=os.path.basename(path),
                           url="file://" + os.path.abspath(path),
                           text=text or "",
                           raw={"path": os.path.abspath(path), "ext": ext})

    @staticmethod
    def _pdf_text(path: str) -> str:
        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            return "\n".join((pg.extract_text() or "") for pg in reader.pages[:50])
        except Exception:
            return ""
