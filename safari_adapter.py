"""Read-only Safari bookmark discovery, backup, and conversion for macOS."""

from __future__ import annotations

import copy
import plistlib
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

SUPPORTED_SAFARI_BOOKMARK_VERSIONS = {1}
SAFARI_BOOKMARK_FILENAME = "Bookmarks.plist"


def discover_safari_bookmarks(home: Path | None = None, platform: str | None = None) -> Path | None:
    """Return Safari's standard bookmark plist when it exists on macOS."""
    if (platform or sys.platform) != "darwin":
        raise RuntimeError("Safari bookmark support is available only on macOS.")
    candidate = (home or Path.home()) / "Library" / "Safari" / SAFARI_BOOKMARK_FILENAME
    return candidate if candidate.is_file() else None


def load_safari_plist(path: Path) -> dict[str, Any]:
    """Load and minimally validate a Safari bookmark property list without exposing its path."""
    try:
        with path.open("rb") as stream:
            document = plistlib.load(stream)
    except (OSError, plistlib.InvalidFileException, ValueError) as exc:
        raise RuntimeError("Safari bookmark data is malformed or unreadable.") from exc
    if not isinstance(document, dict):
        raise RuntimeError("Safari bookmark data has an unsupported structure.")
    version = document.get("WebBookmarkFileVersion")
    if version not in SUPPORTED_SAFARI_BOOKMARK_VERSIONS:
        raise RuntimeError(
            f"Safari bookmark schema version {version!r} is unsupported; no data was changed."
        )
    if not isinstance(document.get("Children"), list):
        raise RuntimeError("Safari bookmark data has an unsupported root structure.")
    return document


def _is_reading_list(node: dict[str, Any]) -> bool:
    identifier = str(node.get("WebBookmarkIdentifier", "")).casefold()
    return identifier == "com.apple.readinglist" or identifier.endswith(".readinglist")


def safari_to_bookmark_model(document: dict[str, Any]) -> dict[str, Any]:
    """Convert bookmark-only Safari nodes to the internal Chromium-shaped model."""
    if document.get("WebBookmarkFileVersion") not in SUPPORTED_SAFARI_BOOKMARK_VERSIONS:
        raise RuntimeError("Safari bookmark schema version is unsupported; no data was changed.")
    next_id = 3

    def convert(node: Any, location: str) -> dict[str, Any] | None:
        nonlocal next_id
        if not isinstance(node, dict):
            raise RuntimeError(f"Safari bookmark data contains a malformed node at {location}.")
        if _is_reading_list(node):
            return None
        kind = node.get("WebBookmarkType")
        if kind == "WebBookmarkTypeLeaf":
            url = node.get("URLString")
            uri = node.get("URIDictionary", {})
            if not isinstance(url, str) or not url or not isinstance(uri, dict):
                raise RuntimeError(f"Safari bookmark data contains a malformed bookmark at {location}.")
            title = uri.get("title", url)
            if not isinstance(title, str):
                raise RuntimeError(f"Safari bookmark data contains a malformed title at {location}.")
            result = {"type": "url", "id": str(next_id), "guid": str(uuid.uuid4()), "name": title, "url": url}
            next_id += 1
            return result
        if kind in ("WebBookmarkTypeList", "WebBookmarkTypeProxy"):
            children = node.get("Children", [])
            if not isinstance(children, list):
                raise RuntimeError(f"Safari bookmark data contains a malformed folder at {location}.")
            converted = [item for index, child in enumerate(children) if (item := convert(child, f"{location}.Children[{index}]")) is not None]
            result = {
                "type": "folder",
                "id": str(next_id),
                "guid": str(uuid.uuid4()),
                "name": str(node.get("Title") or "Safari Bookmarks"),
                "children": converted,
            }
            next_id += 1
            return result
        raise RuntimeError(f"Safari bookmark data contains an unsupported node type at {location}.")

    bar_children: list[dict[str, Any]] = []
    other_children: list[dict[str, Any]] = []
    for index, child in enumerate(document["Children"]):
        converted = convert(child, f"Children[{index}]")
        if converted is None:
            continue
        identifier = str(child.get("WebBookmarkIdentifier", "")).casefold()
        destination = bar_children if identifier.endswith(("bookmarkbar", "bookmarksbar")) else other_children
        if converted["type"] == "folder" and identifier.endswith(("bookmarkbar", "bookmarksbar", "bookmarksmenu")):
            destination.extend(converted["children"])
        else:
            destination.append(converted)
    return {
        "version": 1,
        "roots": {
            "bookmark_bar": {"type": "folder", "id": "1", "guid": str(uuid.uuid4()), "name": "Bookmarks bar", "children": bar_children},
            "other": {"type": "folder", "id": "2", "guid": str(uuid.uuid4()), "name": "Other bookmarks", "children": other_children},
        },
    }


def read_safari_bookmarks(path: Path) -> dict[str, Any]:
    return safari_to_bookmark_model(load_safari_plist(path))


def backup_safari_bookmarks(source: Path, destination: Path) -> Path:
    """Validate then copy Safari bookmarks; never touches or coordinates with the live profile."""
    load_safari_plist(source)
    try:
        shutil.copy2(source, destination)
    except OSError as exc:
        raise RuntimeError("Could not create the Safari bookmark backup.") from exc
    # Parse the copy so the exact manifested artifact is independently validated.
    read_safari_bookmarks(destination)
    return destination


def clone_safari_model(data: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(data)
