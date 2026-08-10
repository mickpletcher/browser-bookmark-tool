from __future__ import annotations

import argparse
import base64
import configparser
import copy
import csv
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import uuid
import webbrowser
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any
from urllib.parse import urlsplit, urlunsplit

APP_NAME = "Browser Bookmark Tool"
ROOT_NAMES = ("bookmark_bar", "other", "synced")
BROWSER_PROCESS_NAMES = ("chrome.exe", "msedge.exe")
FIREFOX_PROCESS_NAME = "firefox.exe"
SUPPORTED_BROWSER_PROCESS_NAMES = (*BROWSER_PROCESS_NAMES, FIREFOX_PROCESS_NAME)
MAX_BACKUPS = 50
DUPLICATE_MODES = ("conservative", "aggressive")
MERGE_STRATEGIES = ("chrome-wins", "edge-wins", "preserve-both", "merge-folders", "dated-folder")
BACKUP_CATALOG_FILTERS = ("all", "complete", "incomplete", "valid", "invalid")
AUTOMATION_SCHEMA_VERSION = 1
AUTOMATION_OPERATIONS = ("backup", "sync", "dry-run")
AUTOMATION_BROWSER_BEHAVIORS = ("block", "close")
AUTOMATION_HEALTH_LIMIT = 100
AUTOMATION_HEALTH_MAX_LIMIT = 1000
AUTOMATION_ERROR_CATEGORIES = (
    "none",
    "active_lock",
    "browser_running",
    "configuration",
    "profile_missing",
    "bookmark_json",
    "process_detection",
    "backup_destination",
    "automation",
)
BACKUP_NAME_PATTERN = re.compile(
    r"^(?P<prefix>Chrome|Edge|Firefox|Bookmarks|Manifest)_"
    r"(?P<stamp>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:_\d{6})?)"
    r"\.(?P<extension>json|sqlite|html)$"
)


def local_app_data() -> Path:
    value = os.environ.get("LOCALAPPDATA")
    if not value:
        raise RuntimeError("LOCALAPPDATA is unavailable. This app currently supports Windows.")
    return Path(value)


def roaming_app_data() -> Path:
    value = os.environ.get("APPDATA")
    if not value:
        raise RuntimeError("APPDATA is unavailable. Firefox profile discovery currently supports Windows.")
    return Path(value)


def default_backup_dir() -> Path:
    return Path.home() / "Documents" / "Browser Bookmark Backups"


def browser_user_data(browser: str) -> Path:
    relative = {
        "Chrome": Path("Google/Chrome/User Data"),
        "Edge": Path("Microsoft/Edge/User Data"),
    }[browser]
    return local_app_data() / relative


def discover_profiles(browser: str) -> list[Path]:
    base = browser_user_data(browser)
    if not base.exists():
        return []
    candidates = [p for p in base.iterdir() if p.is_dir() and (p.name == "Default" or p.name.startswith("Profile "))]
    return sorted((p for p in candidates if (p / "Bookmarks").exists()), key=lambda p: (p.name != "Default", p.name))


def discover_firefox_profiles(profiles_ini: Path | None = None) -> list[Path]:
    source = profiles_ini or roaming_app_data() / "Mozilla" / "Firefox" / "profiles.ini"
    if not source.is_file():
        return []
    parser = configparser.ConfigParser(interpolation=None)
    try:
        with source.open(encoding="utf-8-sig") as stream:
            parser.read_file(stream)
    except (OSError, configparser.Error) as exc:
        raise RuntimeError(f"Could not read Firefox profile discovery file {source}.") from exc
    profiles: list[tuple[bool, str, Path]] = []
    for section in parser.sections():
        if not section.casefold().startswith("profile") or not parser.has_option(section, "Path"):
            continue
        raw_path = parser.get(section, "Path").strip()
        if not raw_path:
            continue
        relative = parser.get(section, "IsRelative", fallback="1").strip() != "0"
        path = Path(raw_path)
        if relative:
            path = source.parent / path
        path = path.expanduser().resolve()
        if (path / "places.sqlite").is_file():
            profiles.append((parser.get(section, "Default", fallback="0").strip() == "1", section, path))
    return [path for _default, _section, path in sorted(profiles, key=lambda item: (not item[0], item[1].casefold()))]


def running_browser_processes() -> list[str]:
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except OSError as exc:
        raise RuntimeError("Browser process detection failed. Use --force only if both browsers are closed.") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or "tasklist returned an error"
        raise RuntimeError(f"Browser process detection failed: {detail}. Use --force only if both browsers are closed.")
    running = {
        row[0].lstrip("\ufeff").casefold()
        for row in csv.reader(result.stdout.splitlines())
        if row
    }
    return [name for name in BROWSER_PROCESS_NAMES if name in running]


def running_firefox_processes() -> list[str]:
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except OSError as exc:
        raise RuntimeError("Firefox process detection failed. Use --force only if Firefox is closed.") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or "tasklist returned an error"
        raise RuntimeError(f"Firefox process detection failed: {detail}. Use --force only if Firefox is closed.")
    running = {row[0].lstrip("\ufeff").casefold() for row in csv.reader(result.stdout.splitlines()) if row}
    return [FIREFOX_PROCESS_NAME] if FIREFOX_PROCESS_NAME in running else []


def close_browser_processes(processes: Iterable[str]) -> None:
    requested = {process.casefold() for process in processes}
    for process in SUPPORTED_BROWSER_PROCESS_NAMES:
        if process not in requested:
            continue
        try:
            subprocess.run(
                ["taskkill", "/IM", process, "/T", "/F"],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
        except OSError as exc:
            raise RuntimeError(f"Could not run taskkill for {process}.") from exc


def wait_for_browsers_to_close(timeout: float = 10.0) -> list[str]:
    deadline = time.monotonic() + timeout
    while True:
        running = running_browser_processes()
        if not running or time.monotonic() >= deadline:
            return running
        time.sleep(0.25)


def wait_for_firefox_to_close(timeout: float = 10.0) -> list[str]:
    deadline = time.monotonic() + timeout
    while True:
        running = running_firefox_processes()
        if not running or time.monotonic() >= deadline:
            return running
        time.sleep(0.25)


def backup_retention(value: str) -> int:
    try:
        keep = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("backup retention must be a number from 1 to 50") from exc
    if not 1 <= keep <= MAX_BACKUPS:
        raise argparse.ArgumentTypeError("backup retention must be from 1 to 50")
    return keep


@dataclass
class ProfileMapping:
    name: str
    chrome_profile: Path
    edge_profile: Path
    backup_dir: Path
    firefox_profile: Path | None = None


@dataclass(frozen=True)
class AutomationConfig:
    source: Path
    operation: str
    profile_map: Path
    mappings: tuple[str, ...]
    keep: int
    deduplicate: bool
    alphabetize: bool
    duplicate_mode: str
    merge_strategy: str
    browser_behavior: str
    firefox_enabled: bool
    firefox_export: bool
    result_file: Path
    lock_file: Path
    lock_timeout_minutes: int
    health_file: Path
    health_history_limit: int
    notifications_enabled: bool
    notification_command: tuple[str, ...]


def config_relative_path(value: str, source: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (source.parent / path).resolve()


def load_automation_config(path: Path) -> AutomationConfig:
    source = path.expanduser().resolve()
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Could not read the private automation configuration.") from exc
    if not isinstance(document, dict):
        raise RuntimeError("The automation configuration must be a JSON object.")
    if document.get("schema_version") != AUTOMATION_SCHEMA_VERSION:
        raise RuntimeError(f"Automation schema_version must be {AUTOMATION_SCHEMA_VERSION}.")

    operation = document.get("operation")
    if operation not in AUTOMATION_OPERATIONS:
        raise RuntimeError(f"Automation operation must be one of: {', '.join(AUTOMATION_OPERATIONS)}.")
    profile_map_value = document.get("profile_map")
    if not isinstance(profile_map_value, str) or not profile_map_value.strip():
        raise RuntimeError("Automation profile_map must be a non-empty path string.")

    mappings_value = document.get("mappings", [])
    if (
        not isinstance(mappings_value, list)
        or any(not isinstance(name, str) or not name.strip() for name in mappings_value)
        or len(mappings_value) != len(set(mappings_value))
    ):
        raise RuntimeError("Automation mappings must be a list of unique non-empty names.")

    keep_value = document.get("keep", MAX_BACKUPS)
    if isinstance(keep_value, bool) or not isinstance(keep_value, int) or not 1 <= keep_value <= MAX_BACKUPS:
        raise RuntimeError(f"Automation keep must be a number from 1 to {MAX_BACKUPS}.")
    for option in ("deduplicate", "alphabetize", "firefox_enabled", "firefox_export"):
        if not isinstance(document.get(option, False), bool):
            raise RuntimeError(f"Automation {option} must be true or false.")
    if document.get("firefox_export", False) and not document.get("firefox_enabled", False):
        raise RuntimeError("Automation firefox_export requires firefox_enabled.")
    if document.get("firefox_export", False) and operation != "sync":
        raise RuntimeError("Automation firefox_export can be true only when operation is sync.")

    duplicate_mode = document.get("duplicate_mode", "conservative")
    if duplicate_mode not in DUPLICATE_MODES:
        raise RuntimeError(f"Automation duplicate_mode must be one of: {', '.join(DUPLICATE_MODES)}.")
    merge_strategy = document.get("merge_strategy", "chrome-wins")
    if merge_strategy not in MERGE_STRATEGIES:
        raise RuntimeError(f"Automation merge_strategy must be one of: {', '.join(MERGE_STRATEGIES)}.")
    browser_behavior = document.get("browser_behavior", "block")
    if browser_behavior not in AUTOMATION_BROWSER_BEHAVIORS:
        raise RuntimeError(
            f"Automation browser_behavior must be one of: {', '.join(AUTOMATION_BROWSER_BEHAVIORS)}."
        )
    if operation != "sync" and browser_behavior != "block":
        raise RuntimeError("Automation browser_behavior can be close only when operation is sync.")

    result_value = document.get("result_file", "browser-bookmark-automation-result.json")
    lock_value = document.get("lock_file", "browser-bookmark-automation.lock")
    health_value = document.get("health_file", "browser-bookmark-automation-health.json")
    if not isinstance(result_value, str) or not result_value.strip():
        raise RuntimeError("Automation result_file must be a non-empty path string.")
    if not isinstance(lock_value, str) or not lock_value.strip():
        raise RuntimeError("Automation lock_file must be a non-empty path string.")
    if not isinstance(health_value, str) or not health_value.strip():
        raise RuntimeError("Automation health_file must be a non-empty path string.")
    result_file = config_relative_path(result_value, source)
    lock_file = config_relative_path(lock_value, source)
    health_file = config_relative_path(health_value, source)
    if len({result_file, lock_file, health_file}) != 3:
        raise RuntimeError("Automation result_file, lock_file, and health_file must be different paths.")

    lock_timeout = document.get("lock_timeout_minutes", 180)
    if isinstance(lock_timeout, bool) or not isinstance(lock_timeout, int) or not 5 <= lock_timeout <= 1440:
        raise RuntimeError("Automation lock_timeout_minutes must be from 5 to 1440.")

    health_history_limit = document.get("health_history_limit", AUTOMATION_HEALTH_LIMIT)
    if (
        isinstance(health_history_limit, bool)
        or not isinstance(health_history_limit, int)
        or not 1 <= health_history_limit <= AUTOMATION_HEALTH_MAX_LIMIT
    ):
        raise RuntimeError(
            f"Automation health_history_limit must be from 1 to {AUTOMATION_HEALTH_MAX_LIMIT}."
        )
    notifications_enabled = document.get("notifications_enabled", False)
    if not isinstance(notifications_enabled, bool):
        raise RuntimeError("Automation notifications_enabled must be true or false.")
    notification_command_value = document.get("notification_command", [])
    if (
        not isinstance(notification_command_value, list)
        or any(not isinstance(value, str) or not value.strip() for value in notification_command_value)
    ):
        raise RuntimeError("Automation notification_command must be a list of non-empty strings.")
    if notifications_enabled and not notification_command_value:
        raise RuntimeError("Automation notification_command is required when notifications are enabled.")

    return AutomationConfig(
        source=source,
        operation=operation,
        profile_map=config_relative_path(profile_map_value, source),
        mappings=tuple(mappings_value),
        keep=keep_value,
        deduplicate=document.get("deduplicate", False),
        alphabetize=document.get("alphabetize", False),
        duplicate_mode=duplicate_mode,
        merge_strategy=merge_strategy,
        browser_behavior=browser_behavior,
        firefox_enabled=document.get("firefox_enabled", False),
        firefox_export=document.get("firefox_export", False),
        result_file=result_file,
        lock_file=lock_file,
        lock_timeout_minutes=lock_timeout,
        health_file=health_file,
        health_history_limit=health_history_limit,
        notifications_enabled=notifications_enabled,
        notification_command=tuple(notification_command_value),
    )


class AutomationRunLock:
    def __init__(self, path: Path, stale_minutes: int) -> None:
        self.path = path
        self.stale_seconds = stale_minutes * 60
        self.token = str(uuid.uuid4())
        self.acquired = False
        self.stale_replaced = False

    def __enter__(self) -> AutomationRunLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(3):
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age <= self.stale_seconds:
                    raise RuntimeError("Another browser bookmark automation run is already active.") from None
                stale = self.path.with_name(f"{self.path.name}.stale.{uuid.uuid4().hex}")
                try:
                    os.replace(self.path, stale)
                except FileNotFoundError:
                    continue
                stale.unlink(missing_ok=True)
                self.stale_replaced = True
                continue
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(
                    {
                        "schema_version": AUTOMATION_SCHEMA_VERSION,
                        "pid": os.getpid(),
                        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                        "token": self.token,
                    },
                    stream,
                )
                stream.flush()
                os.fsync(stream.fileno())
            self.acquired = True
            return self
        raise RuntimeError("Could not acquire the browser bookmark automation lock.")

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        if not self.acquired:
            return
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if document.get("token") == self.token:
            self.path.unlink(missing_ok=True)


def write_json_atomic(path: Path, document: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".pending", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return path


def load_profile_mappings(path: Path) -> dict[str, ProfileMapping]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read profile mappings from {path}.") from exc
    if not isinstance(document, dict) or not isinstance(document.get("mappings"), list):
        raise RuntimeError(f"Profile mappings in {path} must contain a mappings list.")
    mappings: dict[str, ProfileMapping] = {}
    for item in document["mappings"]:
        try:
            mapping = ProfileMapping(
                name=str(item["name"]),
                chrome_profile=Path(item["chrome_profile"]),
                edge_profile=Path(item["edge_profile"]),
                backup_dir=Path(item["backup_dir"]),
                firefox_profile=(Path(item["firefox_profile"]) if item.get("firefox_profile") else None),
            )
        except (KeyError, TypeError) as exc:
            raise RuntimeError(f"A profile mapping in {path} is incomplete.") from exc
        if mapping.name in mappings:
            raise RuntimeError(f"Duplicate profile mapping name: {mapping.name}")
        mappings[mapping.name] = mapping
    if not mappings:
        raise RuntimeError(f"No profile mappings exist in {path}.")
    return mappings


def save_profile_mapping(path: Path, mapping: ProfileMapping) -> None:
    existing: dict[str, ProfileMapping] = {}
    if path.exists():
        existing = load_profile_mappings(path)
    existing[mapping.name] = mapping
    document = {
        "mappings": [
            {
                "name": item.name,
                "chrome_profile": str(item.chrome_profile),
                "edge_profile": str(item.edge_profile),
                "backup_dir": str(item.backup_dir),
                **({"firefox_profile": str(item.firefox_profile)} if item.firefox_profile else {}),
            }
            for item in sorted(existing.values(), key=lambda value: value.name.casefold())
        ]
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_backup_manifest(
    destination: Path,
    files: Iterable[Path],
    preview: SyncPreview | None = None,
) -> Path:
    entries = [
        {"name": path.name, "sha256": sha256_file(path), "size": path.stat().st_size}
        for path in files
    ]
    document: dict[str, Any] = {
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "files": entries,
    }
    if preview is not None:
        summary = {
            "chrome_count": preview.chrome_count,
            "edge_count": preview.edge_count,
            "merged_count": preview.merged_count,
            "duplicates_removed": preview.duplicates_removed,
            "merge_strategy": preview.merge_strategy,
            "duplicate_mode": preview.duplicate_mode,
        }
        if preview.firefox_enabled:
            summary["firefox_count"] = preview.firefox_count
        document["summary"] = summary
    destination.write_text(json.dumps(document, indent=2), encoding="utf-8")
    validate_backup_manifest(destination)
    return destination


def validate_backup_manifest(path: Path) -> None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Backup manifest {path} is invalid.") from exc
    if not isinstance(document, dict) or not isinstance(document.get("files"), list):
        raise RuntimeError(f"Backup manifest {path} does not contain a files list.")
    for entry in document["files"]:
        if not isinstance(entry, dict):
            raise RuntimeError(f"Backup manifest {path} contains an invalid file entry.")
        name = entry.get("name")
        size = entry.get("size")
        checksum = entry.get("sha256")
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or not isinstance(size, int)
            or size < 0
            or not isinstance(checksum, str)
            or re.fullmatch(r"[0-9a-f]{64}", checksum) is None
        ):
            raise RuntimeError(f"Backup manifest {path} contains an invalid file entry.")
        target = path.parent / name
        if not target.is_file() or target.stat().st_size != size or sha256_file(target) != checksum:
            raise RuntimeError(f"Backup integrity validation failed for {target}.")


def validate_chromium_bookmark_schema(data: Any) -> None:
    if not isinstance(data, dict):
        raise RuntimeError("The recovery snapshot is not a Chromium bookmark file.")
    roots = data.get("roots")
    if not isinstance(roots, dict):
        raise RuntimeError("The recovery snapshot does not contain a Chromium roots object.")
    missing = [name for name in ("bookmark_bar", "other") if name not in roots]
    if missing:
        raise RuntimeError(f"The recovery snapshot is missing required Chromium root(s): {', '.join(missing)}.")

    def validate_node(node: Any, location: str) -> None:
        if not isinstance(node, dict):
            raise RuntimeError(f"The recovery snapshot contains an invalid node at {location}.")
        node_type = node.get("type")
        if node_type not in ("folder", "url"):
            raise RuntimeError(f"The recovery snapshot contains an invalid node type at {location}.")
        if not isinstance(node.get("id"), str) or not isinstance(node.get("name"), str):
            raise RuntimeError(f"The recovery snapshot contains invalid Chromium metadata at {location}.")
        guid = node.get("guid")
        if guid is not None:
            if not isinstance(guid, str):
                raise RuntimeError(f"The recovery snapshot contains an invalid GUID at {location}.")
            try:
                uuid.UUID(guid)
            except ValueError as exc:
                raise RuntimeError(f"The recovery snapshot contains an invalid GUID at {location}.") from exc
        if node_type == "url":
            if not isinstance(node.get("url"), str) or not node["url"]:
                raise RuntimeError(f"The recovery snapshot contains an invalid URL node at {location}.")
            return
        children = node.get("children")
        if not isinstance(children, list):
            raise RuntimeError(f"The recovery snapshot contains an invalid folder at {location}.")
        for index, child in enumerate(children):
            validate_node(child, f"{location}.children[{index}]")

    for name, root in roots.items():
        validate_node(root, f"roots.{name}")
        if root.get("type") != "folder":
            raise RuntimeError(f"The Chromium root roots.{name} must be a folder.")


@dataclass(frozen=True)
class BackupVerification:
    backup_path: Path
    manifest_path: Path
    bookmark_count: int
    folder_count: int

    def render(self) -> str:
        return (
            "Backup verification passed.\n"
            f"Bookmarks: {self.bookmark_count}\n"
            f"Folders: {self.folder_count}\n"
            f"Manifest: {self.manifest_path.name}\n"
            "No live browser files were changed."
        )


def matching_backup_manifest(backup_path: Path) -> Path:
    match = BACKUP_NAME_PATTERN.fullmatch(backup_path.name)
    if match is None or match.group("prefix") not in ("Chrome", "Edge"):
        raise RuntimeError("Could not determine the matching manifest from the recovery snapshot name.")
    return backup_path.parent / f"Manifest_{match.group('stamp')}.json"


def verify_json_backup(backup_path: Path, manifest_path: Path | None = None) -> BackupVerification:
    if backup_path.suffix.casefold() != ".json":
        raise RuntimeError("Backup verification requires a raw JSON recovery snapshot.")
    if not backup_path.is_file():
        raise RuntimeError(f"Recovery snapshot {backup_path} does not exist.")
    resolved_manifest = manifest_path or matching_backup_manifest(backup_path)

    with tempfile.TemporaryDirectory(prefix="browser-bookmark-verify-") as temporary:
        profile = Path(temporary) / "Default"
        profile.mkdir()
        shutil.copy2(backup_path, profile / "Bookmarks")
        data = read_bookmarks(profile)
        validate_chromium_bookmark_schema(data)
        validate_unique_guids(data)

    validate_backup_manifest(resolved_manifest)
    manifest = json.loads(resolved_manifest.read_text(encoding="utf-8"))
    matching_entries = [entry for entry in manifest["files"] if entry["name"] == backup_path.name]
    if not matching_entries:
        raise RuntimeError(f"Backup manifest {resolved_manifest} does not reference {backup_path.name}.")
    entry = matching_entries[0]
    if backup_path.stat().st_size != entry["size"] or sha256_file(backup_path) != entry["sha256"]:
        raise RuntimeError(f"Backup integrity validation failed for {backup_path}.")
    return BackupVerification(
        backup_path=backup_path,
        manifest_path=resolved_manifest,
        bookmark_count=count_bookmarks(data),
        folder_count=count_folders(data),
    )


def write_privacy_safe_log(path: Path, event: str, **details: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = " ".join(f"{key}={value}" for key, value in sorted(details.items()))
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"{timestamp} event={event}{' ' if safe else ''}{safe}\n")


def restore_json_backup(
    backup_path: Path,
    profile: Path,
    browser: str,
    recovery_dir: Path,
    force: bool = False,
) -> Path:
    if backup_path.suffix.casefold() != ".json":
        raise RuntimeError("Direct restore requires a raw JSON recovery snapshot. Import HTML backups through the browser.")
    try:
        data = json.loads(backup_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read recovery snapshot {backup_path}.") from exc
    if not isinstance(data, dict) or "roots" not in data:
        raise RuntimeError(f"The recovery snapshot {backup_path} is not a Chromium bookmark file.")
    validate_chromium_bookmark_schema(data)
    validate_unique_guids(data)
    process = {"Chrome": "chrome.exe", "Edge": "msedge.exe"}[browser]
    if not force and process in running_browser_processes():
        raise RuntimeError(f"Restore blocked because {process} is running.")
    current = profile / "Bookmarks"
    if not current.is_file():
        raise RuntimeError(f"No current Bookmarks file exists in {profile}.")
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    recovery_dir.mkdir(parents=True, exist_ok=True)
    preserved = recovery_dir / f"{browser}_PreRestore_{stamp}.json"
    shutil.copy2(current, preserved)
    staged = prepare_json_write(current, data)
    try:
        os.replace(staged, current)
    finally:
        staged.unlink(missing_ok=True)
    return preserved


def write_task_scheduler_script(
    destination: Path,
    chrome_profile: Path,
    edge_profile: Path,
    backup_dir: Path,
    task_name: str,
    task_time: str,
    synchronize_task: bool = False,
    firefox_profile: Path | None = None,
    firefox_export: bool = False,
) -> Path:
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", task_time):
        raise RuntimeError("Task time must use 24-hour HH:MM format.")
    if firefox_export and (not firefox_profile or not synchronize_task):
        raise RuntimeError("Firefox task export requires a Firefox profile and synchronization opt in.")
    frozen = bool(getattr(sys, "frozen", False))
    executable = sys.executable if frozen else "py"
    arguments = ([] if frozen else ["-m", "browser_bookmark_sync"]) + [
        "--chrome-profile",
        str(chrome_profile),
        "--edge-profile",
        str(edge_profile),
        "--backup-dir",
        str(backup_dir),
        "--keep",
        str(MAX_BACKUPS),
    ]
    if firefox_profile:
        arguments.extend(["--firefox-profile", str(firefox_profile)])
    if synchronize_task:
        arguments.append("--sync")
        if firefox_export:
            arguments.append("--firefox-export")
    argument_text = subprocess.list2cmdline(arguments).replace("'", "''")
    executable_text = executable.replace("'", "''")
    task_name_text = task_name.replace("'", "''")
    script = (
        f"$action = New-ScheduledTaskAction -Execute '{executable_text}' -Argument '{argument_text}'\n"
        f"$trigger = New-ScheduledTaskTrigger -Daily -At '{task_time}'\n"
        f"Register-ScheduledTask -TaskName '{task_name_text}' -Action $action -Trigger $trigger "
        f"-Description 'Browser bookmark backup{' and synchronization' if synchronize_task else ''}'\n"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(script, encoding="utf-8")
    return destination


def read_bookmarks(profile: Path) -> dict[str, Any]:
    path = profile / "Bookmarks"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"No Bookmarks file exists in {profile}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"The Bookmarks file in {profile} is not valid JSON") from exc


def firefox_database(profile: Path) -> Path:
    path = profile / "places.sqlite"
    if not path.is_file():
        raise RuntimeError(f"No places.sqlite file exists in Firefox profile {profile}")
    return path


def firefox_table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def validate_firefox_schema(connection: sqlite3.Connection) -> None:
    place_columns = firefox_table_columns(connection, "moz_places")
    bookmark_columns = firefox_table_columns(connection, "moz_bookmarks")
    if not {
        "id",
        "url",
        "url_hash",
        "title",
        "rev_host",
        "hidden",
        "typed",
        "frecency",
        "guid",
        "foreign_count",
    }.issubset(place_columns):
        raise RuntimeError("The Firefox places.sqlite file has an unsupported moz_places schema.")
    if not {
        "id",
        "type",
        "fk",
        "parent",
        "position",
        "title",
        "dateAdded",
        "lastModified",
        "guid",
        "syncStatus",
        "syncChangeCounter",
    }.issubset(bookmark_columns):
        raise RuntimeError("The Firefox places.sqlite file has an unsupported moz_bookmarks schema.")
    if "place_id" not in firefox_table_columns(connection, "moz_keywords"):
        raise RuntimeError("The Firefox places.sqlite file has an unsupported moz_keywords schema.")
    root_guids = {
        str(row[0])
        for row in connection.execute(
            "SELECT guid FROM moz_bookmarks WHERE guid IN ('toolbar_____', 'menu________', 'unfiled_____', 'mobile______')"
        )
    }
    if not {"toolbar_____", "menu________", "unfiled_____"}.issubset(root_guids):
        raise RuntimeError("The Firefox places.sqlite file is missing required bookmark roots.")


def read_firefox_database(path: Path, immutable: bool = False) -> dict[str, Any]:
    try:
        immutable_option = "&immutable=1" if immutable else ""
        connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro{immutable_option}", uri=True)
    except sqlite3.Error as exc:
        raise RuntimeError(f"Could not open Firefox bookmark database {path}.") from exc
    try:
        validate_firefox_schema(connection)
        rows = list(
            connection.execute(
                "SELECT b.id, b.type, b.parent, b.position, b.title, b.guid, p.url "
                "FROM moz_bookmarks b LEFT JOIN moz_places p ON p.id = b.fk "
                "ORDER BY b.parent, b.position, b.id"
            )
        )
        root_ids = {
            str(guid): int(identifier)
            for identifier, guid in connection.execute(
                "SELECT id, guid FROM moz_bookmarks "
                "WHERE guid IN ('toolbar_____', 'menu________', 'unfiled_____', 'mobile______')"
            )
        }
    except sqlite3.Error as exc:
        raise RuntimeError(f"Could not read Firefox bookmarks from {path}.") from exc
    finally:
        connection.close()

    children: dict[int, list[tuple[Any, ...]]] = {}
    for row in rows:
        children.setdefault(int(row[2]), []).append(row)

    def build(parent: int, ancestors: set[int]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for identifier, item_type, _parent, _position, title, guid, url in children.get(parent, []):
            identifier = int(identifier)
            if identifier in ancestors:
                raise RuntimeError(f"Firefox bookmark database {path} contains a folder cycle.")
            if item_type == 1 and url:
                result.append(
                    {
                        "type": "url",
                        "id": str(identifier),
                        "guid": str(guid or ""),
                        "name": str(title or url),
                        "url": str(url),
                    }
                )
            elif item_type == 2:
                result.append(
                    {
                        "type": "folder",
                        "id": str(identifier),
                        "guid": str(guid or ""),
                        "name": str(title or "Folder"),
                        "children": build(identifier, ancestors | {identifier}),
                    }
                )
        return result

    other_children: list[dict[str, Any]] = []
    for guid in ("menu________", "unfiled_____", "mobile______"):
        if guid in root_ids:
            other_children.extend(build(root_ids[guid], {root_ids[guid]}))
    return {
        "roots": {
            "bookmark_bar": {
                "type": "folder",
                "id": "1",
                "name": "Bookmarks Toolbar",
                "children": build(root_ids["toolbar_____"], {root_ids["toolbar_____"]}),
            },
            "other": {"type": "folder", "id": "2", "name": "Other Bookmarks", "children": other_children},
            "synced": {"type": "folder", "id": "3", "name": "Mobile Bookmarks", "children": []},
        },
        "version": 1,
    }


def read_firefox_bookmarks(profile: Path) -> dict[str, Any]:
    return read_firefox_database(firefox_database(profile))


def firefox_guid() -> str:
    return base64.urlsafe_b64encode(os.urandom(9)).decode("ascii").rstrip("=")


def places_url_hash(url: str) -> int:
    raw = url.encode("utf-8")[:1500]

    def hash_bytes(value: bytes) -> int:
        result = 0
        for byte in value:
            result = (((result << 5) | (result >> 27)) ^ byte) & 0xFFFFFFFF
            result = (result * 0x9E3779B9) & 0xFFFFFFFF
        return result

    url_hash = hash_bytes(raw)
    colon = raw[:50].find(b":")
    if colon >= 0:
        return ((hash_bytes(raw[:colon]) & 0xFFFF) << 32) + url_hash
    return url_hash


def backup_firefox_database(profile: Path, destination: Path) -> Path:
    source_path = firefox_database(profile)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(f"{source_path.resolve().as_uri()}?mode=ro", uri=True)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
        if target.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise RuntimeError("The Firefox backup did not pass SQLite integrity validation.")
        target.commit()
    except sqlite3.Error as exc:
        raise RuntimeError(f"Could not back up Firefox bookmark database {source_path}.") from exc
    finally:
        target.close()
        source.close()
    return destination


def prepare_firefox_write(
    profile: Path,
    backup_path: Path,
    merged: dict[str, Any],
    duplicate_mode: str,
) -> tuple[Path, int]:
    live_path = firefox_database(profile)
    descriptor, temporary = tempfile.mkstemp(prefix="places.pending.", suffix=".sqlite", dir=live_path.parent)
    os.close(descriptor)
    staged = Path(temporary)
    shutil.copy2(backup_path, staged)
    added = 0
    try:
        connection = sqlite3.connect(staged)
        try:
            validate_firefox_schema(connection)
            existing_bookmark_urls = [
                str(row[0])
                for row in connection.execute(
                    "SELECT p.url FROM moz_bookmarks b JOIN moz_places p ON p.id = b.fk WHERE b.type = 1"
                )
            ]
            known = {normalized_url(url, duplicate_mode) for url in existing_bookmark_urls}
            candidates: list[dict[str, Any]] = []
            for root in merged.get("roots", {}).values():
                for node in iter_urls(root):
                    key = normalized_url(str(node["url"]), duplicate_mode)
                    if key not in known:
                        known.add(key)
                        candidates.append(node)
            if candidates:
                unfiled = connection.execute(
                    "SELECT id FROM moz_bookmarks WHERE guid = 'unfiled_____'"
                ).fetchone()
                if unfiled is None:
                    raise RuntimeError("The Firefox bookmark database is missing the Other Bookmarks root.")
                unfiled_id = int(unfiled[0])
                folder = connection.execute(
                    "SELECT id FROM moz_bookmarks WHERE parent = ? AND type = 2 AND title = ? ORDER BY id LIMIT 1",
                    (unfiled_id, APP_NAME),
                ).fetchone()
                now = int(time.time() * 1_000_000) // 1000 * 1000
                if folder is None:
                    folder_position = int(
                        connection.execute(
                            "SELECT COALESCE(MAX(position), -1) + 1 FROM moz_bookmarks WHERE parent = ?",
                            (unfiled_id,),
                        ).fetchone()[0]
                    )
                    connection.execute(
                        "INSERT INTO moz_bookmarks "
                        "(type, fk, parent, position, title, dateAdded, lastModified, guid, syncStatus, syncChangeCounter) "
                        "VALUES (2, NULL, ?, ?, ?, ?, ?, ?, 1, 1)",
                        (unfiled_id, folder_position, APP_NAME, now, now, firefox_guid()),
                    )
                    folder_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
                else:
                    folder_id = int(folder[0])
                position = int(
                    connection.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 FROM moz_bookmarks WHERE parent = ?",
                        (folder_id,),
                    ).fetchone()[0]
                )
                place_ids = {str(url): int(identifier) for identifier, url in connection.execute("SELECT id, url FROM moz_places")}
                touched_places: set[int] = set()
                for node in candidates:
                    url = str(node["url"])
                    place_id = place_ids.get(url)
                    if place_id is None:
                        host = urlsplit(url).hostname or ""
                        connection.execute(
                            "INSERT INTO moz_places "
                            "(url, url_hash, title, rev_host, hidden, typed, frecency, guid, foreign_count) "
                            "VALUES (?, ?, ?, ?, 0, 0, -1, ?, 0)",
                            (url, places_url_hash(url), str(node.get("name") or url)[:4096], host[::-1] + "." if host else "", firefox_guid()),
                        )
                        place_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
                        place_ids[url] = place_id
                    connection.execute(
                        "INSERT INTO moz_bookmarks "
                        "(type, fk, parent, position, title, dateAdded, lastModified, guid, syncStatus, syncChangeCounter) "
                        "VALUES (1, ?, ?, ?, ?, ?, ?, ?, 1, 1)",
                        (place_id, folder_id, position, str(node.get("name") or url)[:4096], now, now, firefox_guid()),
                    )
                    position += 1
                    added += 1
                    touched_places.add(place_id)
                for place_id in touched_places:
                    connection.execute(
                        "UPDATE moz_places SET foreign_count = "
                        "(SELECT COUNT(*) FROM moz_bookmarks WHERE fk = moz_places.id) + "
                        "(SELECT COUNT(*) FROM moz_keywords WHERE place_id = moz_places.id) WHERE id = ?",
                        (place_id,),
                    )
                connection.execute(
                    "UPDATE moz_bookmarks SET lastModified = ?, syncChangeCounter = syncChangeCounter + 1 WHERE id IN (?, ?)",
                    (now, folder_id, unfiled_id),
                )
            connection.commit()
            checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if checkpoint and int(checkpoint[0]) != 0:
                raise RuntimeError("The prepared Firefox database could not be checkpointed.")
            if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise RuntimeError("The prepared Firefox database did not pass SQLite integrity validation.")
        finally:
            connection.close()
        for suffix in ("-wal", "-shm"):
            staged.with_name(staged.name + suffix).unlink(missing_ok=True)
        read_firefox_database(staged)
        for suffix in ("-wal", "-shm"):
            staged.with_name(staged.name + suffix).unlink(missing_ok=True)
        return staged, added
    except Exception:
        staged.unlink(missing_ok=True)
        for suffix in ("-wal", "-shm"):
            staged.with_name(staged.name + suffix).unlink(missing_ok=True)
        raise


def prepare_json_write(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="Bookmarks.pending.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            with temporary_path.open(encoding="utf-8") as stream:
                prepared = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"The prepared bookmark file for {path} is not valid JSON.") from exc
        if prepared != data:
            raise RuntimeError(f"The prepared bookmark file for {path} did not pass content validation.")
        return temporary_path
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def transactional_json_write(chrome_path: Path, edge_path: Path, data: dict[str, Any]) -> None:
    chrome_staged: Path | None = None
    edge_staged: Path | None = None
    chrome_rollback: Path | None = None
    preserve_rollback = False
    try:
        chrome_staged = prepare_json_write(chrome_path, data)
        edge_staged = prepare_json_write(edge_path, data)

        fd, rollback = tempfile.mkstemp(prefix="Bookmarks.rollback.", dir=chrome_path.parent)
        os.close(fd)
        chrome_rollback = Path(rollback)
        shutil.copy2(chrome_path, chrome_rollback)

        try:
            os.replace(chrome_staged, chrome_path)
            chrome_staged = None
        except OSError as exc:
            raise RuntimeError("Could not replace Chrome bookmarks. Neither browser was changed.") from exc

        try:
            os.replace(edge_staged, edge_path)
            edge_staged = None
        except OSError as exc:
            try:
                os.replace(chrome_rollback, chrome_path)
                chrome_rollback = None
            except OSError as rollback_exc:
                preserve_rollback = True
                raise RuntimeError(
                    f"Could not replace Edge bookmarks or restore Chrome automatically. "
                    f"The Chrome rollback file is {chrome_rollback}."
                ) from rollback_exc
            raise RuntimeError("Could not replace Edge bookmarks. Chrome was restored automatically.") from exc
    finally:
        if chrome_staged is not None:
            chrome_staged.unlink(missing_ok=True)
        if edge_staged is not None:
            edge_staged.unlink(missing_ok=True)
        if chrome_rollback is not None and not preserve_rollback:
            chrome_rollback.unlink(missing_ok=True)


def checkpoint_firefox_database(path: Path) -> None:
    try:
        connection = sqlite3.connect(path)
        try:
            result = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if result and int(result[0]) != 0:
                raise RuntimeError("Firefox database checkpoint was blocked.")
        finally:
            connection.close()
        for suffix in ("-wal", "-shm"):
            path.with_name(path.name + suffix).unlink(missing_ok=True)
    except sqlite3.Error as exc:
        raise RuntimeError("Could not checkpoint the Firefox bookmark database before replacement.") from exc


def transactional_firefox_write(
    chrome_path: Path,
    edge_path: Path,
    firefox_path: Path,
    data: dict[str, Any],
    firefox_staged: Path,
) -> None:
    chrome_staged = prepare_json_write(chrome_path, data)
    edge_staged = prepare_json_write(edge_path, data)
    rollback_paths: dict[str, Path] = {}
    replaced: list[tuple[str, Path]] = []
    preserve_rollbacks = False
    try:
        for browser, path in (("Chrome", chrome_path), ("Edge", edge_path)):
            descriptor, temporary = tempfile.mkstemp(prefix="Bookmarks.rollback.", dir=path.parent)
            os.close(descriptor)
            rollback_paths[browser] = Path(temporary)
            shutil.copy2(path, rollback_paths[browser])
        try:
            os.replace(chrome_staged, chrome_path)
            replaced.append(("Chrome", chrome_path))
            chrome_staged = None
        except OSError as exc:
            raise RuntimeError("Could not replace Chrome bookmarks. No browser was changed.") from exc
        try:
            os.replace(edge_staged, edge_path)
            replaced.append(("Edge", edge_path))
            edge_staged = None
        except OSError as exc:
            try:
                os.replace(rollback_paths["Chrome"], chrome_path)
                rollback_paths.pop("Chrome")
            except OSError as rollback_exc:
                preserve_rollbacks = True
                raise RuntimeError(
                    "Could not replace Edge bookmarks or restore Chrome automatically. "
                    f"The Chrome rollback file is {rollback_paths['Chrome']}."
                ) from rollback_exc
            raise RuntimeError("Could not replace Edge bookmarks. Chrome was restored automatically.") from exc
        try:
            os.replace(firefox_staged, firefox_path)
        except OSError as exc:
            restoration_errors: list[str] = []
            for browser, path in reversed(replaced):
                try:
                    os.replace(rollback_paths[browser], path)
                    rollback_paths.pop(browser)
                except OSError:
                    restoration_errors.append(browser)
            if restoration_errors:
                preserve_rollbacks = True
                names = ", ".join(restoration_errors)
                raise RuntimeError(
                    f"Could not replace Firefox bookmarks or restore {names} automatically. "
                    "The rollback files were preserved in their profile directories."
                ) from exc
            raise RuntimeError("Could not replace Firefox bookmarks. Chrome and Edge were restored automatically.") from exc
    finally:
        if chrome_staged is not None:
            chrome_staged.unlink(missing_ok=True)
        if edge_staged is not None:
            edge_staged.unlink(missing_ok=True)
        firefox_staged.unlink(missing_ok=True)
        for suffix in ("-wal", "-shm"):
            firefox_staged.with_name(firefox_staged.name + suffix).unlink(missing_ok=True)
        if not preserve_rollbacks:
            for rollback in rollback_paths.values():
                rollback.unlink(missing_ok=True)


def iter_urls(node: dict[str, Any]) -> Iterable[dict[str, Any]]:
    if node.get("type") == "url" and node.get("url"):
        yield node
    for child in node.get("children", []):
        yield from iter_urls(child)


def normalized_url(url: str, mode: str = "conservative") -> str:
    if mode not in DUPLICATE_MODES:
        raise RuntimeError(f"Duplicate mode must be one of: {', '.join(DUPLICATE_MODES)}")
    value = url.strip()
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value.casefold() if mode == "aggressive" else value
    netloc = parsed.netloc
    if netloc:
        userinfo, separator, host_port = netloc.rpartition("@")
        prefix = f"{userinfo}@" if separator else ""
        if host_port.startswith("[") and "]" in host_port:
            end = host_port.index("]")
            host_port = host_port[: end + 1].casefold() + host_port[end + 1 :]
        elif host_port.count(":") == 1:
            host, port = host_port.rsplit(":", 1)
            host_port = f"{host.casefold()}:{port}"
        else:
            host_port = host_port.casefold()
        netloc = prefix + host_port
    normalized = urlunsplit((parsed.scheme.casefold(), netloc, parsed.path, parsed.query, parsed.fragment))
    if mode == "aggressive":
        if normalized.endswith("/") and normalized.count("/") > 2:
            normalized = normalized[:-1]
        normalized = normalized.casefold()
    return normalized


def max_numeric_id(data: dict[str, Any]) -> int:
    maximum = 0
    for root in data.get("roots", {}).values():
        for node in walk_nodes(root):
            try:
                maximum = max(maximum, int(node.get("id", 0)))
            except (TypeError, ValueError):
                pass
    return maximum


def walk_nodes(node: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield node
    for child in node.get("children", []):
        yield from walk_nodes(child)


def validate_unique_guids(data: dict[str, Any]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for root in data.get("roots", {}).values():
        for node in walk_nodes(root):
            guid = node.get("guid")
            if not guid:
                continue
            key = str(guid).casefold()
            if key in seen:
                duplicates.add(str(guid))
            seen.add(key)
    if duplicates:
        values = ", ".join(sorted(duplicates))
        raise RuntimeError(f"The bookmark data contains duplicate GUID values: {values}")


def deduplicate_bookmarks(data: dict[str, Any], mode: str = "conservative") -> int:
    known: set[str] = set()
    removed = 0

    def remove_duplicates(node: dict[str, Any]) -> None:
        nonlocal removed
        children = []
        for child in node.get("children", []):
            if child.get("type") == "url" and child.get("url"):
                key = normalized_url(child["url"], mode)
                if key in known:
                    removed += 1
                    continue
                known.add(key)
            elif child.get("type") == "folder":
                remove_duplicates(child)
            children.append(child)
        node["children"] = children

    for root_name in ROOT_NAMES:
        root = data.get("roots", {}).get(root_name)
        if root:
            remove_duplicates(root)
    return removed


def alphabetize_bookmarks(data: dict[str, Any]) -> int:
    reordered = 0

    def sort_children(node: dict[str, Any]) -> None:
        nonlocal reordered
        children = node.get("children", [])
        for child in children:
            if child.get("type") == "folder":
                sort_children(child)
        before = [str(child.get("guid") or child.get("id") or index) for index, child in enumerate(children)]
        children.sort(
            key=lambda child: (
                child.get("type") != "folder",
                str(child.get("name") or child.get("url") or "").casefold(),
            )
        )
        after = [str(child.get("guid") or child.get("id") or index) for index, child in enumerate(children)]
        if before != after:
            reordered += 1

    for root_name in ROOT_NAMES:
        root = data.get("roots", {}).get(root_name)
        if root:
            sort_children(root)
    return reordered


def merge_bookmarks(
    primary: dict[str, Any],
    secondary: dict[str, Any],
    duplicate_mode: str = "conservative",
    wrapper_name: str = "Imported from other browser",
    merge_matching_folders: bool = False,
) -> tuple[dict[str, Any], int]:
    """Return a conservative union, retaining primary folders and appending unique URLs."""
    merged = copy.deepcopy(primary)
    roots = merged.setdefault("roots", {})
    known = {normalized_url(n["url"], duplicate_mode) for root in roots.values() for n in iter_urls(root)}
    known_guids = {
        str(node["guid"]).casefold()
        for root in roots.values()
        for node in walk_nodes(root)
        if node.get("guid")
    }
    next_id = max(max_numeric_id(primary), max_numeric_id(secondary)) + 1
    added = 0

    def new_guid() -> str:
        while True:
            value = str(uuid.uuid4())
            if value.casefold() not in known_guids:
                known_guids.add(value.casefold())
                return value

    def clone_unique(node: dict[str, Any]) -> dict[str, Any] | None:
        nonlocal next_id, added
        if node.get("type") == "url":
            url = node.get("url", "")
            key = normalized_url(url, duplicate_mode)
            if not url or key in known:
                return None
            known.add(key)
            result = copy.deepcopy(node)
            result["id"] = str(next_id)
            result["guid"] = new_guid()
            next_id += 1
            added += 1
            return result
        if node.get("type") == "folder":
            children = [item for child in node.get("children", []) if (item := clone_unique(child)) is not None]
            if not children:
                return None
            result = copy.deepcopy(node)
            result["id"] = str(next_id)
            result["guid"] = new_guid()
            next_id += 1
            result["children"] = children
            return result
        return None

    imported_children: list[dict[str, Any]] = []

    def merge_children(destination: dict[str, Any], source_children: list[dict[str, Any]]) -> None:
        destination_children = destination.setdefault("children", [])
        for child in source_children:
            if child.get("type") == "folder":
                matching = next(
                    (
                        item
                        for item in destination_children
                        if item.get("type") == "folder"
                        and str(item.get("name", "")).casefold() == str(child.get("name", "")).casefold()
                    ),
                    None,
                )
                if matching is not None:
                    merge_children(matching, child.get("children", []))
                    continue
            cloned = clone_unique(child)
            if cloned is not None:
                destination_children.append(cloned)

    if merge_matching_folders:
        for root_name in ROOT_NAMES:
            source_root = secondary.get("roots", {}).get(root_name)
            destination_root = roots.get(root_name)
            if source_root and destination_root:
                merge_children(destination_root, source_root.get("children", []))
    else:
        destination = roots.get("other") or roots.get("bookmark_bar")
        if destination is None:
            raise RuntimeError("The primary browser file has no recognized bookmark roots.")
        for root_name in ROOT_NAMES:
            source_root = secondary.get("roots", {}).get(root_name)
            if source_root:
                for child in source_root.get("children", []):
                    cloned = clone_unique(child)
                    if cloned is not None:
                        imported_children.append(cloned)
    if imported_children:
        folder = {
            "children": imported_children,
            "date_added": str(int((dt.datetime.now(dt.timezone.utc).timestamp() + 11644473600) * 1_000_000)),
            "date_modified": "0",
            "guid": new_guid(),
            "id": str(next_id),
            "name": wrapper_name,
            "type": "folder",
        }
        destination.setdefault("children", []).append(folder)
    merged.pop("checksum", None)
    validate_unique_guids(merged)
    return merged, added


def export_html(data: dict[str, Any], destination: Path) -> int:
    count = 0
    lines = [
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        "<TITLE>Bookmarks</TITLE>",
        "<H1>Bookmarks</H1>",
        "<DL><p>",
    ]

    def render(node: dict[str, Any], indent: int) -> None:
        nonlocal count
        pad = "    " * indent
        if node.get("type") == "url":
            count += 1
            title = html.escape(node.get("name") or node.get("url", ""))
            url = html.escape(node.get("url", ""), quote=True)
            lines.append(f'{pad}<DT><A HREF="{url}">{title}</A>')
        elif node.get("type") == "folder":
            lines.append(f"{pad}<DT><H3>{html.escape(node.get('name', 'Folder'))}</H3>")
            lines.append(f"{pad}<DL><p>")
            for child in node.get("children", []):
                render(child, indent + 1)
            lines.append(f"{pad}</DL><p>")

    for name in ROOT_NAMES:
        root = data.get("roots", {}).get(name)
        if root:
            render(root, 1)
    lines.append("</DL><p>")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines), encoding="utf-8")
    return count


def prune_backups(directory: Path, keep: int) -> None:
    groups: dict[str, list[tuple[str, Path]]] = {"Chrome": [], "Edge": [], "Firefox": [], "Bookmarks": [], "Manifest": []}
    for path in directory.glob("*"):
        if not path.is_file() or not (match := BACKUP_NAME_PATTERN.fullmatch(path.name)):
            continue
        prefix = match.group("prefix")
        extension = match.group("extension")
        if prefix == "Bookmarks" and extension != "html":
            continue
        if prefix == "Firefox" and extension != "sqlite":
            continue
        if prefix not in ("Bookmarks", "Firefox") and extension != "json":
            continue
        groups[prefix].append((match.group("stamp"), path))
    for backups in groups.values():
        for _, old in sorted(backups, key=lambda item: item[0], reverse=True)[keep:]:
            old.unlink()


@dataclass
class SyncPreview:
    chrome_count: int
    edge_count: int
    chrome_only: int
    edge_only: int
    input_duplicates: int
    duplicates_removed: int
    merged_count: int
    folders_added: int
    folders_reordered: int
    merge_strategy: str
    duplicate_mode: str
    firefox_count: int = 0
    firefox_only: int = 0
    firefox_enabled: bool = False

    def render(self) -> str:
        firefox = (
            f"Firefox bookmarks: {self.firefox_count}\nFirefox-only URLs: {self.firefox_only}\n"
            if self.firefox_enabled
            else ""
        )
        return (
            f"Strategy: {self.merge_strategy}\n"
            f"Duplicate matching: {self.duplicate_mode}\n"
            f"Chrome bookmarks: {self.chrome_count}\n"
            f"Edge favorites: {self.edge_count}\n"
            f"Chrome-only URLs: {self.chrome_only}\n"
            f"Edge-only URLs: {self.edge_only}\n"
            f"{firefox}"
            f"Duplicates already in inputs: {self.input_duplicates}\n"
            f"Duplicates removed: {self.duplicates_removed}\n"
            f"Folders added: {self.folders_added}\n"
            f"Folders reordered: {self.folders_reordered}\n"
            f"Final bookmark count: {self.merged_count}"
        )


def count_bookmarks(data: dict[str, Any]) -> int:
    return sum(1 for root in data.get("roots", {}).values() for _ in iter_urls(root))


def count_folders(data: dict[str, Any]) -> int:
    return sum(
        1
        for root in data.get("roots", {}).values()
        for node in walk_nodes(root)
        if node.get("type") == "folder"
    )


@dataclass(frozen=True)
class BackupArtifactSummary:
    browser: str
    bookmark_count: int | None
    folder_count: int | None
    valid: bool


@dataclass(frozen=True)
class BackupSetSummary:
    stamp: str
    manifest_status: str
    missing_members: tuple[str, ...]
    extra_members: tuple[str, ...]
    artifacts: tuple[BackupArtifactSummary, ...]

    @property
    def complete(self) -> bool:
        return not self.missing_members and not self.extra_members

    @property
    def valid(self) -> bool:
        return self.complete and self.manifest_status == "valid" and all(
            artifact.valid for artifact in self.artifacts
        )


@dataclass(frozen=True)
class BackupCatalog:
    sets: tuple[BackupSetSummary, ...]

    def filtered(self, status: str = "all") -> tuple[BackupSetSummary, ...]:
        if status not in BACKUP_CATALOG_FILTERS:
            raise RuntimeError(f"Unknown backup catalog filter: {status}")
        if status == "all":
            return self.sets
        if status == "complete":
            return tuple(item for item in self.sets if item.complete)
        if status == "incomplete":
            return tuple(item for item in self.sets if not item.complete)
        if status == "valid":
            return tuple(item for item in self.sets if item.valid)
        return tuple(item for item in self.sets if not item.valid)

    def deltas(self) -> dict[tuple[str, str], tuple[int, int]]:
        result: dict[tuple[str, str], tuple[int, int]] = {}
        previous: dict[str, BackupArtifactSummary] = {}
        for backup_set in reversed(self.sets):
            if not backup_set.complete or not backup_set.valid:
                continue
            for artifact in backup_set.artifacts:
                older = previous.get(artifact.browser)
                if (
                    older
                    and older.bookmark_count is not None
                    and older.folder_count is not None
                    and artifact.bookmark_count is not None
                    and artifact.folder_count is not None
                ):
                    result[(backup_set.stamp, artifact.browser)] = (
                        artifact.bookmark_count - older.bookmark_count,
                        artifact.folder_count - older.folder_count,
                    )
                previous[artifact.browser] = artifact
        return result

    def render(self, status: str = "all") -> str:
        selected = self.filtered(status)
        lines = [f"Backup catalog: {len(selected)} set(s), filter {status}."]
        changes = self.deltas()
        for backup_set in selected:
            completeness = "complete" if backup_set.complete else "incomplete"
            validity = "valid" if backup_set.valid else "invalid"
            lines.append(
                f"\n{backup_set.stamp}: {completeness}, {validity}, manifest {backup_set.manifest_status}"
            )
            if backup_set.missing_members:
                lines.append(f"Missing: {', '.join(backup_set.missing_members)}")
            if backup_set.extra_members:
                lines.append(f"Extra: {', '.join(backup_set.extra_members)}")
            for artifact in backup_set.artifacts:
                if artifact.bookmark_count is None or artifact.folder_count is None:
                    lines.append(f"{artifact.browser}: content invalid")
                    continue
                change = changes.get((backup_set.stamp, artifact.browser))
                delta = ""
                if change:
                    delta = f", change {change[0]:+d} bookmarks, {change[1]:+d} folders"
                lines.append(
                    f"{artifact.browser}: {artifact.bookmark_count} bookmarks, "
                    f"{artifact.folder_count} folders{delta}"
                )
        lines.append("\nNo live browser files or backup files were changed.")
        return "\n".join(lines)


@dataclass(frozen=True)
class BackupComparison:
    older: BackupSetSummary
    newer: BackupSetSummary

    def render(self) -> str:
        older_artifacts = {artifact.browser: artifact for artifact in self.older.artifacts}
        newer_artifacts = {artifact.browser: artifact for artifact in self.newer.artifacts}
        lines = [f"Backup comparison: {self.older.stamp} to {self.newer.stamp}"]
        for browser in sorted(older_artifacts.keys() | newer_artifacts.keys()):
            old = older_artifacts.get(browser)
            new = newer_artifacts.get(browser)
            if old is None or new is None:
                lines.append(f"{browser}: not present in both sets")
                continue
            lines.append(
                f"{browser}: bookmarks {old.bookmark_count} to {new.bookmark_count} "
                f"({new.bookmark_count - old.bookmark_count:+d}), folders "
                f"{old.folder_count} to {new.folder_count} ({new.folder_count - old.folder_count:+d})"
            )
        lines.append("No live browser files or backup files were changed.")
        return "\n".join(lines)


def backup_member(path: Path) -> tuple[str, str] | None:
    match = BACKUP_NAME_PATTERN.fullmatch(path.name)
    if match is None:
        return None
    prefix = match.group("prefix")
    extension = match.group("extension")
    expected = {
        "Chrome": "json",
        "Edge": "json",
        "Firefox": "sqlite",
        "Bookmarks": "html",
        "Manifest": "json",
    }
    if expected[prefix] != extension:
        return None
    return prefix, match.group("stamp")


def catalog_manifest(path: Path, stamp: str) -> tuple[str, set[str]]:
    if not path.is_file():
        return "missing", set()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "invalid", set()
    if not isinstance(document, dict) or not isinstance(document.get("files"), list):
        return "invalid", set()
    referenced: set[str] = set()
    structurally_valid = True
    for entry in document["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            structurally_valid = False
            continue
        parsed = backup_member(path.parent / entry["name"])
        if parsed is None or parsed[1] != stamp or parsed[0] == "Manifest" or parsed[0] in referenced:
            structurally_valid = False
            continue
        referenced.add(parsed[0])
    if not {"Chrome", "Edge", "Bookmarks"}.issubset(referenced):
        structurally_valid = False
    try:
        validate_backup_manifest(path)
    except RuntimeError:
        return "invalid", referenced
    return ("valid" if structurally_valid else "invalid"), referenced


def summarize_backup_artifact(browser: str, path: Path) -> BackupArtifactSummary:
    try:
        if browser == "Firefox":
            data = read_firefox_database(path, immutable=True)
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            validate_chromium_bookmark_schema(data)
            validate_unique_guids(data)
        return BackupArtifactSummary(browser, count_bookmarks(data), count_folders(data), True)
    except (OSError, json.JSONDecodeError, RuntimeError):
        return BackupArtifactSummary(browser, None, None, False)


def catalog_backup_sets(directory: Path) -> BackupCatalog:
    if not directory.is_dir():
        raise RuntimeError(f"Backup directory {directory} does not exist.")
    grouped: dict[str, dict[str, Path]] = {}
    try:
        paths = tuple(directory.iterdir())
    except OSError as exc:
        raise RuntimeError(f"Could not read backup directory {directory}.") from exc
    for path in paths:
        if not path.is_file() or (parsed := backup_member(path)) is None:
            continue
        prefix, stamp = parsed
        grouped.setdefault(stamp, {})[prefix] = path

    summaries: list[BackupSetSummary] = []
    required = {"Chrome", "Edge", "Bookmarks", "Manifest"}
    for stamp, members in sorted(grouped.items(), reverse=True):
        manifest = members.get("Manifest", directory / f"Manifest_{stamp}.json")
        manifest_status, referenced = catalog_manifest(manifest, stamp)
        expected = required | ({"Firefox"} if "Firefox" in referenced else set())
        present = set(members)
        missing = tuple(sorted(expected - present))
        extra = tuple(sorted((present - {"Manifest"}) - referenced)) if manifest_status != "missing" else ()
        artifacts = tuple(
            summarize_backup_artifact(browser, members[browser])
            for browser in ("Chrome", "Edge", "Firefox")
            if browser in members
        )
        summaries.append(
            BackupSetSummary(stamp, manifest_status, missing, extra, artifacts)
        )
    return BackupCatalog(tuple(summaries))


def compare_backup_sets(catalog: BackupCatalog, older_stamp: str, newer_stamp: str) -> BackupComparison:
    by_stamp = {item.stamp: item for item in catalog.sets}
    missing = [stamp for stamp in (older_stamp, newer_stamp) if stamp not in by_stamp]
    if missing:
        raise RuntimeError(f"Unknown backup set timestamp(s): {', '.join(missing)}")
    older = by_stamp[older_stamp]
    newer = by_stamp[newer_stamp]
    if not older.complete or not older.valid or not newer.complete or not newer.valid:
        raise RuntimeError("Backup comparison requires two complete, valid sets.")
    return BackupComparison(older, newer)


def prepare_merged_data(
    chrome: dict[str, Any],
    edge: dict[str, Any],
    deduplicate: bool = False,
    alphabetize: bool = False,
    duplicate_mode: str = "conservative",
    merge_strategy: str = "chrome-wins",
    firefox: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], SyncPreview]:
    if merge_strategy not in MERGE_STRATEGIES:
        raise RuntimeError(f"Merge strategy must be one of: {', '.join(MERGE_STRATEGIES)}")
    chrome_urls = [normalized_url(node["url"], duplicate_mode) for root in chrome.get("roots", {}).values() for node in iter_urls(root)]
    edge_urls = [normalized_url(node["url"], duplicate_mode) for root in edge.get("roots", {}).values() for node in iter_urls(root)]
    chrome_keys = set(chrome_urls)
    edge_keys = set(edge_urls)
    firefox_urls = (
        [normalized_url(node["url"], duplicate_mode) for root in firefox.get("roots", {}).values() for node in iter_urls(root)]
        if firefox is not None
        else []
    )
    firefox_keys = set(firefox_urls)

    if merge_strategy == "edge-wins":
        primary, secondary = edge, chrome
        wrapper_name = "Imported from Chrome"
        merge_folders = False
    else:
        primary, secondary = chrome, edge
        wrapper_name = {
            "preserve-both": "Edge favorites",
            "dated-folder": f"Imported from Edge {dt.datetime.now().strftime('%Y-%m-%d')}",
        }.get(merge_strategy, "Imported from other browser")
        merge_folders = merge_strategy == "merge-folders"

    primary_folder_count = count_folders(primary)
    merged, _ = merge_bookmarks(
        primary,
        secondary,
        duplicate_mode=duplicate_mode,
        wrapper_name=wrapper_name,
        merge_matching_folders=merge_folders,
    )
    if firefox is not None:
        merged, _ = merge_bookmarks(
            merged,
            firefox,
            duplicate_mode=duplicate_mode,
            wrapper_name="Imported from Firefox",
            merge_matching_folders=merge_folders,
        )
    duplicates_removed = deduplicate_bookmarks(merged, duplicate_mode) if deduplicate else 0
    folders_reordered = alphabetize_bookmarks(merged) if alphabetize else 0
    preview = SyncPreview(
        chrome_count=len(chrome_urls),
        edge_count=len(edge_urls),
        chrome_only=len(chrome_keys - edge_keys),
        edge_only=len(edge_keys - chrome_keys),
        input_duplicates=(
            (len(chrome_urls) - len(chrome_keys))
            + (len(edge_urls) - len(edge_keys))
            + (len(firefox_urls) - len(firefox_keys))
        ),
        duplicates_removed=duplicates_removed,
        merged_count=count_bookmarks(merged),
        folders_added=max(0, count_folders(merged) - primary_folder_count),
        folders_reordered=folders_reordered,
        merge_strategy=merge_strategy,
        duplicate_mode=duplicate_mode,
        firefox_count=len(firefox_urls),
        firefox_only=len(firefox_keys - chrome_keys - edge_keys),
        firefox_enabled=firefox is not None,
    )
    return merged, preview


def preview_synchronization(
    chrome_profile: Path,
    edge_profile: Path,
    deduplicate: bool = False,
    alphabetize: bool = False,
    duplicate_mode: str = "conservative",
    merge_strategy: str = "chrome-wins",
    firefox_profile: Path | None = None,
) -> SyncPreview:
    _, preview = prepare_merged_data(
        read_bookmarks(chrome_profile),
        read_bookmarks(edge_profile),
        deduplicate=deduplicate,
        alphabetize=alphabetize,
        duplicate_mode=duplicate_mode,
        merge_strategy=merge_strategy,
        firefox=read_firefox_bookmarks(firefox_profile) if firefox_profile else None,
    )
    return preview


@dataclass
class SyncResult:
    chrome_count: int
    edge_count: int
    merged_count: int
    duplicates_removed: int
    alphabetized: bool
    closed_processes: tuple[str, ...]
    preview: SyncPreview
    html_path: Path
    manifest_path: Path
    log_path: Path
    backup_dir: Path
    firefox_count: int = 0
    firefox_added: int = 0


def synchronize(
    chrome_profile: Path,
    edge_profile: Path,
    backup_dir: Path,
    keep: int = MAX_BACKUPS,
    write: bool = True,
    deduplicate: bool = False,
    alphabetize: bool = False,
    force: bool = False,
    close_browsers: bool = False,
    duplicate_mode: str = "conservative",
    merge_strategy: str = "chrome-wins",
    log_file: Path | None = None,
    verbose: bool = False,
    firefox_profile: Path | None = None,
    firefox_export: bool = False,
) -> SyncResult:
    if not 1 <= keep <= MAX_BACKUPS:
        raise RuntimeError(f"Backup retention must be from 1 to {MAX_BACKUPS}.")
    if force and close_browsers:
        raise RuntimeError("--force and --close-browsers cannot be used together.")
    if firefox_export and firefox_profile is None:
        raise RuntimeError("Firefox export requires an enabled Firefox profile.")
    chrome = read_bookmarks(chrome_profile)
    edge = read_bookmarks(edge_profile)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    backup_dir.mkdir(parents=True, exist_ok=True)
    chrome_backup = backup_dir / f"Chrome_{stamp}.json"
    edge_backup = backup_dir / f"Edge_{stamp}.json"
    firefox_backup = backup_dir / f"Firefox_{stamp}.sqlite" if firefox_profile else None
    shutil.copy2(chrome_profile / "Bookmarks", chrome_backup)
    shutil.copy2(edge_profile / "Bookmarks", edge_backup)
    if firefox_profile and firefox_backup:
        backup_firefox_database(firefox_profile, firefox_backup)
    firefox = read_firefox_database(firefox_backup) if firefox_backup else None

    merged, preview = prepare_merged_data(
        chrome,
        edge,
        deduplicate=deduplicate,
        alphabetize=alphabetize,
        duplicate_mode=duplicate_mode,
        merge_strategy=merge_strategy,
        firefox=firefox,
    )
    html_path = backup_dir / f"Bookmarks_{stamp}.html"
    merged_count = export_html(merged, html_path)
    backup_files = [chrome_backup, edge_backup]
    if firefox_backup:
        backup_files.append(firefox_backup)
    backup_files.append(html_path)
    manifest_path = write_backup_manifest(
        backup_dir / f"Manifest_{stamp}.json",
        backup_files,
        preview,
    )
    log_path = log_file or backup_dir / "browser-bookmark-tool.log"
    log_details = {
        "chrome_count": preview.chrome_count,
        "edge_count": preview.edge_count,
        "merged_count": preview.merged_count,
        "manifest": manifest_path.name,
    }
    if preview.firefox_enabled:
        log_details["firefox_count"] = preview.firefox_count
    write_privacy_safe_log(log_path, "backup_export_complete", **log_details)
    prune_backups(backup_dir, keep)
    closed_processes: tuple[str, ...] = ()
    if write:
        if not force:
            try:
                running = running_browser_processes()
                if firefox_export:
                    running.extend(running_firefox_processes())
            except RuntimeError as exc:
                raise RuntimeError(
                    f"{exc} Backups and the HTML export were created in {backup_dir}."
                ) from exc
            if running and close_browsers:
                closed_processes = tuple(running)
                close_browser_processes(running)
                try:
                    running = wait_for_browsers_to_close()
                    if firefox_export:
                        running.extend(wait_for_firefox_to_close())
                except RuntimeError as exc:
                    raise RuntimeError(
                        f"{exc} Backups and the HTML export were created in {backup_dir}."
                    ) from exc
                if running:
                    names = ", ".join(running)
                    raise RuntimeError(
                        f"Could not close these browser processes: {names}. Synchronization was not performed. "
                        f"Backups and the HTML export were created in {backup_dir}. HTML: {html_path}"
                    )
            elif running:
                names = ", ".join(running)
                write_privacy_safe_log(log_path, "sync_blocked", processes=names)
                raise RuntimeError(
                    f"Synchronization blocked because these browser processes are running: {names}. "
                    f"Close them completely and try again. Backups and the HTML export were created in "
                    f"{backup_dir}. HTML: {html_path}"
                )
        firefox_added = 0
        if firefox_export and firefox_profile and firefox_backup:
            firefox_staged, firefox_added = prepare_firefox_write(
                firefox_profile,
                firefox_backup,
                merged,
                duplicate_mode,
            )
            firefox_path = firefox_database(firefox_profile)
            checkpoint_firefox_database(firefox_path)
            transactional_firefox_write(
                chrome_profile / "Bookmarks",
                edge_profile / "Bookmarks",
                firefox_path,
                merged,
                firefox_staged,
            )
        else:
            transactional_json_write(chrome_profile / "Bookmarks", edge_profile / "Bookmarks", merged)
        write_privacy_safe_log(
            log_path,
            "sync_complete",
            closed_processes=",".join(closed_processes) or "none",
            duplicates_removed=preview.duplicates_removed,
            strategy=merge_strategy,
        )
    else:
        firefox_added = 0
    if not write and verbose:
        write_privacy_safe_log(log_path, "verbose_summary", folders_added=preview.folders_added, folders_reordered=preview.folders_reordered)
    return SyncResult(
        chrome_count=preview.chrome_count,
        edge_count=preview.edge_count,
        merged_count=merged_count,
        duplicates_removed=preview.duplicates_removed,
        alphabetized=alphabetize,
        closed_processes=closed_processes,
        preview=preview,
        html_path=html_path,
        manifest_path=manifest_path,
        log_path=log_path,
        backup_dir=backup_dir,
        firefox_count=preview.firefox_count,
        firefox_added=firefox_added,
    )


def selected_automation_mappings(config: AutomationConfig) -> list[ProfileMapping]:
    available = load_profile_mappings(config.profile_map)
    names = list(config.mappings) or sorted(available)
    missing = [name for name in names if name not in available]
    if missing:
        raise RuntimeError(f"Unknown automation mapping(s): {', '.join(missing)}.")
    selected = [available[name] for name in names]
    if any(
        not path.is_absolute()
        for mapping in selected
        for path in (
            mapping.chrome_profile,
            mapping.edge_profile,
            mapping.backup_dir,
            *((mapping.firefox_profile,) if config.firefox_enabled and mapping.firefox_profile else ()),
        )
    ):
        raise RuntimeError("Automation profile mappings must use absolute browser and backup paths.")
    if config.firefox_enabled and any(mapping.firefox_profile is None for mapping in selected):
        raise RuntimeError("Firefox is enabled but a selected profile mapping has no firefox_profile.")
    return selected


def writable_existing_parent(path: Path) -> bool:
    candidate = path if path.is_dir() else path.parent
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate.is_dir() and os.access(candidate, os.W_OK)


def safe_automation_error(exc: Exception) -> str:
    message = str(exc)
    folded = message.casefold()
    if (
        folded.startswith("automation ")
        or folded.startswith("the automation ")
        or "private automation configuration" in folded
    ):
        return message
    if "already active" in folded or "automation lock" in folded:
        return "Another browser bookmark automation run is already active."
    if "process detection" in folded:
        return "Browser process detection is unavailable."
    if "browser process" in folded or "synchronization blocked" in folded:
        detected = [process for process in SUPPORTED_BROWSER_PROCESS_NAMES if process in folded]
        suffix = f": {', '.join(detected)}" if detected else ""
        return f"Synchronization was blocked by running browser processes{suffix}."
    if "no bookmarks file" in folded:
        return "A configured browser profile does not contain a Bookmarks file."
    if "no places.sqlite file" in folded:
        return "A configured Firefox profile does not contain a places.sqlite file."
    if "not valid json" in folded:
        return "A configured browser bookmark file is not valid JSON."
    if "unknown automation mapping" in folded:
        return message
    if "profile mapping" in folded:
        return "The private profile mapping configuration is invalid."
    return "Automation failed. Review the private local operation log for details."


HEALTH_COUNT_FIELDS = (
    "mapping_total",
    "mapping_succeeded",
    "mapping_failed",
    "chrome_bookmarks",
    "edge_bookmarks",
    "firefox_bookmarks",
    "firefox_bookmarks_added",
    "merged_bookmarks",
    "duplicates_removed",
    "folders_added",
    "folders_reordered",
    "backups_created",
    "html_exports_created",
    "manifests_validated",
    "mappings_synchronized",
    "stale_locks_replaced",
)


def automation_error_category(error: str) -> str:
    folded = error.casefold()
    if "already active" in folded or "automation lock" in folded:
        return "active_lock"
    if "blocked by running browser" in folded:
        return "browser_running"
    if "profile mapping" in folded or "automation configuration" in folded or "unknown automation mapping" in folded:
        return "configuration"
    if "does not contain a bookmarks file" in folded or "does not contain a places.sqlite file" in folded:
        return "profile_missing"
    if "not valid json" in folded:
        return "bookmark_json"
    if "process detection" in folded:
        return "process_detection"
    if "backup destination" in folded:
        return "backup_destination"
    return "automation"


def sanitize_health_record(record: dict[str, Any]) -> dict[str, Any]:
    counts = record.get("counts", {})
    if not isinstance(counts, dict):
        counts = {}
    mappings = record.get("mappings", [])
    if not isinstance(mappings, list):
        mappings = []
    processes = record.get("processes", [])
    if not isinstance(processes, list):
        processes = []
    try:
        duration_seconds = max(0.0, float(record.get("duration_seconds", 0.0)))
    except (TypeError, ValueError):
        duration_seconds = 0.0
    return {
        "operation": record.get("operation") if record.get("operation") in AUTOMATION_OPERATIONS else "unknown",
        "status": record.get("status") if record.get("status") in ("success", "failed", "blocked") else "failed",
        "mappings": [name for name in mappings if isinstance(name, str)],
        "counts": {
            name: value
            for name in HEALTH_COUNT_FIELDS
            if isinstance((value := counts.get(name)), int) and not isinstance(value, bool) and value >= 0
        },
        "duration_seconds": duration_seconds,
        "processes": [name for name in SUPPORTED_BROWSER_PROCESS_NAMES if name in processes],
        "error_category": (
            record.get("error_category")
            if record.get("error_category") in AUTOMATION_ERROR_CATEGORIES
            else "automation"
        ),
    }


def load_health_records(path: Path) -> list[dict[str, Any]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError):
        return []
    records = document.get("records", []) if isinstance(document, dict) else []
    if not isinstance(records, list):
        return []
    return [sanitize_health_record(record) for record in records if isinstance(record, dict)]


def automation_health_record(
    config: AutomationConfig,
    document: dict[str, Any],
    *,
    stale_lock_replaced: bool = False,
) -> dict[str, Any]:
    results = document.get("mappings", [])
    if not isinstance(results, list):
        results = []
    result_names = [
        result.get("name")
        for result in results
        if isinstance(result, dict) and isinstance(result.get("name"), str) and result.get("name") != "configuration"
    ]
    mapping_names = result_names or list(config.mappings)

    firefox_fields_present = any(
        isinstance(result, dict) and ("firefox_count" in result or "firefox_added" in result)
        for result in results
    )
    counts = {
        name: 0
        for name in HEALTH_COUNT_FIELDS
        if firefox_fields_present or name not in ("firefox_bookmarks", "firefox_bookmarks_added")
    }
    counts["mapping_total"] = len(mapping_names)
    numeric_fields = {
        "chrome_count": "chrome_bookmarks",
        "edge_count": "edge_bookmarks",
        "firefox_count": "firefox_bookmarks",
        "firefox_added": "firefox_bookmarks_added",
        "merged_count": "merged_bookmarks",
        "duplicates_removed": "duplicates_removed",
        "folders_added": "folders_added",
        "folders_reordered": "folders_reordered",
    }
    boolean_fields = {
        "backup_created": "backups_created",
        "html_created": "html_exports_created",
        "manifest_validated": "manifests_validated",
        "synchronized": "mappings_synchronized",
    }
    processes: set[str] = set()
    for result in results:
        if not isinstance(result, dict):
            continue
        if result.get("status") == "success":
            counts["mapping_succeeded"] += 1
        elif result.get("status") == "failed":
            counts["mapping_failed"] += 1
        for source, destination in numeric_fields.items():
            value = result.get(source)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                counts[destination] = counts.get(destination, 0) + value
        for source, destination in boolean_fields.items():
            counts[destination] += int(result.get(source) is True)
        closed = result.get("browsers_closed", [])
        if isinstance(closed, list):
            processes.update(name for name in closed if name in SUPPORTED_BROWSER_PROCESS_NAMES)
    counts["stale_locks_replaced"] = int(stale_lock_replaced)

    error = document.get("error", "")
    category = "none" if document.get("status") == "success" else automation_error_category(str(error))
    if category in ("active_lock", "browser_running"):
        status = "blocked"
    else:
        status = "success" if document.get("status") == "success" else "failed"
    folded_error = str(error).casefold()
    processes.update(name for name in SUPPORTED_BROWSER_PROCESS_NAMES if name in folded_error)
    return sanitize_health_record(
        {
            "operation": config.operation,
            "status": status,
            "mappings": mapping_names,
            "counts": counts,
            "duration_seconds": document.get("duration_seconds", 0.0),
            "processes": sorted(processes),
            "error_category": category,
        }
    )


def failure_signature(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["status"],
        record["operation"],
        tuple(record["mappings"]),
        tuple(record["processes"]),
        record["error_category"],
    )


def deliver_failure_notification(command: tuple[str, ...], record: dict[str, Any]) -> bool:
    try:
        completed = subprocess.run(
            list(command),
            input=json.dumps(sanitize_health_record(record)),
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except OSError:
        return False
    return completed.returncode == 0


def record_automation_health(config: AutomationConfig, record: dict[str, Any]) -> None:
    sanitized = sanitize_health_record(record)
    previous = load_health_records(config.health_file)
    write_json_atomic(
        config.health_file,
        {
            "schema_version": AUTOMATION_SCHEMA_VERSION,
            "kind": "automation-health-history",
            "records": (previous + [sanitized])[-config.health_history_limit :],
        },
    )
    if not config.notifications_enabled or sanitized["status"] == "success":
        return
    if previous and previous[-1]["status"] != "success" and failure_signature(previous[-1]) == failure_signature(sanitized):
        return
    deliver_failure_notification(config.notification_command, sanitized)


def automation_readiness(config: AutomationConfig) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    mapping_names: list[str] = []
    try:
        mappings = selected_automation_mappings(config)
    except RuntimeError as exc:
        mappings = []
        errors.append(safe_automation_error(exc))
    for mapping in mappings:
        mapping_names.append(mapping.name)
        try:
            preview_synchronization(
                mapping.chrome_profile,
                mapping.edge_profile,
                deduplicate=config.deduplicate,
                alphabetize=config.alphabetize,
                duplicate_mode=config.duplicate_mode,
                merge_strategy=config.merge_strategy,
                firefox_profile=mapping.firefox_profile if config.firefox_enabled else None,
            )
        except (OSError, RuntimeError) as exc:
            errors.append(f"{mapping.name}: {safe_automation_error(exc)}")
        if not writable_existing_parent(mapping.backup_dir):
            errors.append(f"{mapping.name}: The backup destination is not writable.")
    if not writable_existing_parent(config.result_file):
        errors.append("The automation result destination is not writable.")
    if not writable_existing_parent(config.lock_file):
        errors.append("The automation lock destination is not writable.")
    if not writable_existing_parent(config.health_file):
        errors.append("The automation health destination is not writable.")

    if config.lock_file.exists():
        age = time.time() - config.lock_file.stat().st_mtime
        if age <= config.lock_timeout_minutes * 60:
            errors.append("Another browser bookmark automation run is already active.")
        else:
            warnings.append("A stale automation lock will be replaced when the run starts.")

    try:
        processes = running_browser_processes()
        if config.firefox_enabled and config.firefox_export:
            processes.extend(running_firefox_processes())
    except RuntimeError:
        processes = []
        errors.append("Browser process detection is unavailable.")
    if processes and config.operation == "sync":
        if config.browser_behavior == "close":
            warnings.append("The scheduled run will force-close detected browser processes before synchronization.")
        else:
            warnings.append(
                "The scheduled run will create backups and an HTML export, then block synchronization if browsers remain open."
            )

    return {
        "schema_version": AUTOMATION_SCHEMA_VERSION,
        "kind": "automation-readiness",
        "status": "ready" if not errors else "not-ready",
        "operation": config.operation,
        "mappings": mapping_names,
        "detected_processes": processes,
        "warnings": warnings,
        "errors": errors,
    }


def preview_result(name: str, preview: SyncPreview) -> dict[str, Any]:
    return {
        "name": name,
        "status": "success",
        "chrome_count": preview.chrome_count,
        "edge_count": preview.edge_count,
        **({"firefox_count": preview.firefox_count, "firefox_added": 0} if preview.firefox_enabled else {}),
        "merged_count": preview.merged_count,
        "duplicates_removed": preview.duplicates_removed,
        "folders_added": preview.folders_added,
        "folders_reordered": preview.folders_reordered,
        "backup_created": False,
        "html_created": False,
        "manifest_validated": False,
        "synchronized": False,
        "browsers_closed": [],
    }


def sync_result(name: str, result: SyncResult, synchronized: bool) -> dict[str, Any]:
    return {
        "name": name,
        "status": "success",
        "chrome_count": result.chrome_count,
        "edge_count": result.edge_count,
        **(
            {"firefox_count": result.firefox_count, "firefox_added": result.firefox_added}
            if result.preview.firefox_enabled
            else {}
        ),
        "merged_count": result.merged_count,
        "duplicates_removed": result.duplicates_removed,
        "folders_added": result.preview.folders_added,
        "folders_reordered": result.preview.folders_reordered,
        "backup_created": True,
        "html_created": True,
        "manifest_validated": True,
        "synchronized": synchronized,
        "browsers_closed": list(result.closed_processes),
    }


def automation_artifact_names(backup_dir: Path) -> dict[str, set[str]]:
    artifacts = {prefix: set() for prefix in ("Chrome", "Edge", "Firefox", "Bookmarks", "Manifest")}
    if not backup_dir.is_dir():
        return artifacts
    for path in backup_dir.iterdir():
        match = BACKUP_NAME_PATTERN.fullmatch(path.name)
        if path.is_file() and match:
            artifacts[match.group("prefix")].add(path.name)
    return artifacts


def run_automation(config: AutomationConfig) -> tuple[int, dict[str, Any]]:
    started_at = dt.datetime.now(dt.timezone.utc)
    started_timer = time.monotonic()
    mapping_results: list[dict[str, Any]] = []
    current_mapping = "configuration"
    exit_code = 0
    error: str | None = None
    failure_artifacts = {
        "backup_created": False,
        "html_created": False,
        "manifest_validated": False,
    }
    run_lock = AutomationRunLock(config.lock_file, config.lock_timeout_minutes)
    try:
        run_lock.__enter__()
    except (OSError, RuntimeError) as exc:
        completed_at = dt.datetime.now(dt.timezone.utc)
        error = safe_automation_error(exc)
        document = {
            "schema_version": AUTOMATION_SCHEMA_VERSION,
            "kind": "automation-result",
            "status": "failed",
            "operation": config.operation,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": round(time.monotonic() - started_timer, 3),
            "exit_code": 1,
            "mappings": [],
            "error": error,
        }
        record_automation_health(config, automation_health_record(config, document))
        return 1, document

    try:
        try:
            mappings = selected_automation_mappings(config)
            for mapping in mappings:
                current_mapping = mapping.name
                if config.operation == "dry-run":
                    preview = preview_synchronization(
                        mapping.chrome_profile,
                        mapping.edge_profile,
                        deduplicate=config.deduplicate,
                        alphabetize=config.alphabetize,
                        duplicate_mode=config.duplicate_mode,
                        merge_strategy=config.merge_strategy,
                        firefox_profile=mapping.firefox_profile if config.firefox_enabled else None,
                    )
                    mapping_results.append(preview_result(mapping.name, preview))
                    continue
                before = automation_artifact_names(mapping.backup_dir)
                try:
                    result = synchronize(
                        mapping.chrome_profile,
                        mapping.edge_profile,
                        mapping.backup_dir,
                        firefox_profile=mapping.firefox_profile if config.firefox_enabled else None,
                        firefox_export=config.firefox_export,
                        keep=config.keep,
                        write=config.operation == "sync",
                        deduplicate=config.deduplicate,
                        alphabetize=config.alphabetize,
                        force=False,
                        close_browsers=config.browser_behavior == "close",
                        duplicate_mode=config.duplicate_mode,
                        merge_strategy=config.merge_strategy,
                    )
                except Exception:
                    after = automation_artifact_names(mapping.backup_dir)
                    failure_artifacts = {
                        "backup_created": bool(after["Chrome"] - before["Chrome"])
                        and bool(after["Edge"] - before["Edge"])
                        and (
                            not config.firefox_enabled
                            or bool(after["Firefox"] - before["Firefox"])
                        ),
                        "html_created": bool(after["Bookmarks"] - before["Bookmarks"]),
                        "manifest_validated": bool(after["Manifest"] - before["Manifest"]),
                    }
                    raise
                mapping_results.append(sync_result(mapping.name, result, config.operation == "sync"))
        except Exception as exc:
            exit_code = 1
            error = safe_automation_error(exc)
            mapping_results.append(
                {
                    "name": current_mapping,
                    "status": "failed",
                    **failure_artifacts,
                    "synchronized": False,
                    "browsers_closed": [],
                    "error": error,
                }
            )
        completed_at = dt.datetime.now(dt.timezone.utc)
        document: dict[str, Any] = {
            "schema_version": AUTOMATION_SCHEMA_VERSION,
            "kind": "automation-result",
            "status": "success" if exit_code == 0 else "failed",
            "operation": config.operation,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": round(time.monotonic() - started_timer, 3),
            "exit_code": exit_code,
            "mappings": mapping_results,
        }
        if error:
            document["error"] = error
        write_json_atomic(config.result_file, document)
        record_automation_health(
            config,
            automation_health_record(config, document, stale_lock_replaced=run_lock.stale_replaced),
        )
    finally:
        run_lock.__exit__(None, None, None)
    return exit_code, document


class App(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=18)
        self.master = master
        master.title(APP_NAME)
        master.minsize(900, 720)
        self.chrome = tk.StringVar()
        self.edge = tk.StringVar()
        self.firefox = tk.StringVar()
        self.firefox_enabled = tk.BooleanVar(value=False)
        self.firefox_export = tk.BooleanVar(value=False)
        self.backups = tk.StringVar(value=str(default_backup_dir()))
        self.keep = tk.IntVar(value=MAX_BACKUPS)
        self.deduplicate = tk.BooleanVar(value=False)
        self.alphabetize = tk.BooleanVar(value=False)
        self.duplicate_mode = tk.StringVar(value="conservative")
        self.merge_strategy = tk.StringVar(value="chrome-wins")
        self.catalog_filter = tk.StringVar(value="all")
        self.status = tk.StringVar(value="Select a Chrome and Edge profile.")
        self._build()
        self._detect()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text=APP_NAME, font=("Segoe UI", 18, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(self, text="Back up, export, and synchronize Chrome and Edge bookmarks, with optional Firefox support.").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 18))
        self.chrome_box = self._profile_row(2, "Chrome profile", self.chrome)
        self.edge_box = self._profile_row(3, "Edge profile", self.edge)
        self.firefox_box = self._profile_row(4, "Firefox profile", self.firefox)
        ttk.Label(self, text="Backup folder").grid(row=5, column=0, sticky="w", pady=8)
        ttk.Entry(self, textvariable=self.backups).grid(row=5, column=1, sticky="ew", padx=10)
        ttk.Button(self, text="Browse…", command=self._browse).grid(row=5, column=2)
        ttk.Label(self, text="Backup sets to keep").grid(row=6, column=0, sticky="w", pady=8)
        ttk.Spinbox(self, from_=1, to=MAX_BACKUPS, textvariable=self.keep, width=8).grid(row=6, column=1, sticky="w", padx=10)
        options = ttk.Frame(self)
        options.grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Checkbutton(options, text="Remove duplicate bookmarks", variable=self.deduplicate).pack(side="left")
        ttk.Checkbutton(options, text="Alphabetize bookmarks", variable=self.alphabetize).pack(side="left", padx=16)
        ttk.Checkbutton(options, text="Include Firefox", variable=self.firefox_enabled).pack(side="left")
        ttk.Checkbutton(options, text="Write to Firefox", variable=self.firefox_export).pack(side="left", padx=16)
        ttk.Label(self, text="Duplicate matching").grid(row=8, column=0, sticky="w", pady=8)
        ttk.Combobox(
            self,
            textvariable=self.duplicate_mode,
            values=DUPLICATE_MODES,
            state="readonly",
            width=20,
        ).grid(row=8, column=1, sticky="w", padx=10)
        ttk.Label(self, text="Merge strategy").grid(row=9, column=0, sticky="w", pady=8)
        ttk.Combobox(
            self,
            textvariable=self.merge_strategy,
            values=MERGE_STRATEGIES,
            state="readonly",
            width=24,
        ).grid(row=9, column=1, sticky="w", padx=10)
        note = "Close every browser selected for writing. Raw Chrome and Edge files and an enabled Firefox database are backed up before changes."
        ttk.Label(self, text=note, wraplength=760, foreground="#8a4b08").grid(row=10, column=0, columnspan=3, sticky="w", pady=(18, 12))
        buttons = ttk.Frame(self)
        buttons.grid(row=11, column=0, columnspan=3, sticky="ew")
        ttk.Button(buttons, text="Preview Changes", command=self._preview).pack(side="left")
        ttk.Button(buttons, text="Back Up + Export HTML", command=lambda: self._run(False)).pack(side="left")
        ttk.Button(buttons, text="Back Up + Sync", command=lambda: self._run(True)).pack(side="left", padx=8)
        ttk.Button(buttons, text="Open Backup Folder", command=self._open_backups).pack(side="left")
        management = ttk.Frame(self)
        management.grid(row=12, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(management, text="Verify Backup", command=self._verify_backup).pack(side="left")
        ttk.Button(management, text="Restore Chrome", command=lambda: self._restore("Chrome")).pack(side="left", padx=8)
        ttk.Button(management, text="Restore Edge", command=lambda: self._restore("Edge")).pack(side="left")
        ttk.Button(management, text="Save Profile Mapping", command=self._save_mapping).pack(side="left")
        ttk.Button(management, text="Load Profile Mapping", command=self._load_mapping).pack(side="left", padx=8)
        catalog = ttk.Frame(self)
        catalog.grid(row=13, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(catalog, text="Catalog Backups", command=self._catalog_backups).pack(side="left")
        ttk.Label(catalog, text="Filter").pack(side="left", padx=(12, 6))
        ttk.Combobox(
            catalog,
            textvariable=self.catalog_filter,
            values=BACKUP_CATALOG_FILTERS,
            state="readonly",
            width=12,
        ).pack(side="left")
        ttk.Label(catalog, text="Count changes use the previous complete, valid set.").pack(side="left", padx=12)
        ttk.Separator(self).grid(row=14, column=0, columnspan=3, sticky="ew", pady=18)
        ttk.Label(self, textvariable=self.status, wraplength=840).grid(row=15, column=0, columnspan=3, sticky="w")
        self.pack(fill="both", expand=True)

    def _profile_row(self, row: int, label: str, variable: tk.StringVar) -> ttk.Combobox:
        ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", pady=8)
        box = ttk.Combobox(self, textvariable=variable, state="readonly")
        box.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(10, 0))
        return box

    def _detect(self) -> None:
        try:
            chrome = [str(p) for p in discover_profiles("Chrome")]
            edge = [str(p) for p in discover_profiles("Edge")]
            self.chrome_box["values"] = chrome
            self.edge_box["values"] = edge
            if chrome:
                self.chrome.set(chrome[0])
            if edge:
                self.edge.set(edge[0])
        except Exception as exc:
            self.status.set(str(exc))
            return
        try:
            firefox = [str(p) for p in discover_firefox_profiles()]
            self.firefox_box["values"] = firefox
            if firefox:
                self.firefox.set(firefox[0])
            self.status.set(
                f"Detected {len(chrome)} Chrome, {len(edge)} Edge, and {len(firefox)} Firefox profile(s). Firefox remains disabled until selected."
            )
        except Exception as exc:
            self.status.set(
                f"Detected {len(chrome)} Chrome and {len(edge)} Edge profile(s). Firefox remains disabled. {exc}"
            )

    def _browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.backups.get())
        if chosen:
            self.backups.set(chosen)

    def _run(self, write: bool) -> None:
        if not self.chrome.get() or not self.edge.get():
            messagebox.showerror(APP_NAME, "Chrome and Edge profiles are required.")
            return
        firefox_enabled = bool(getattr(self, "firefox_enabled", None) and self.firefox_enabled.get())
        firefox_export = bool(getattr(self, "firefox_export", None) and self.firefox_export.get())
        firefox_profile = Path(self.firefox.get()) if firefox_enabled and self.firefox.get() else None
        if firefox_enabled and firefox_profile is None:
            messagebox.showerror(APP_NAME, "A Firefox profile is required when Firefox support is enabled.")
            return
        if firefox_export and not firefox_enabled:
            messagebox.showerror(APP_NAME, "Enable Firefox before selecting Write to Firefox.")
            return
        browser_names = "Chrome, Edge, and Firefox" if firefox_export else "Chrome and Edge"
        if write and not messagebox.askyesno(APP_NAME, f"Are {browser_names} completely closed?\n\nBookmark data will be synchronized after backups are created."):
            return
        try:
            result = synchronize(
                Path(self.chrome.get()),
                Path(self.edge.get()),
                Path(self.backups.get()),
                firefox_profile=firefox_profile,
                firefox_export=firefox_export,
                keep=self.keep.get(),
                write=write,
                deduplicate=self.deduplicate.get(),
                alphabetize=self.alphabetize.get(),
                duplicate_mode=self.duplicate_mode.get(),
                merge_strategy=self.merge_strategy.get(),
            )
            action = "Synchronized" if write else "Exported"
            details = [f"{action} {result.merged_count} bookmarks."]
            if self.deduplicate.get():
                details.append(f"Removed {result.duplicates_removed} duplicate(s).")
            if result.alphabetized:
                details.append("Alphabetized folders and bookmarks.")
            details.append(f"HTML: {result.html_path}")
            self.status.set(" ".join(details))
            messagebox.showinfo(APP_NAME, self.status.get())
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def _preview(self) -> None:
        if not self.chrome.get() or not self.edge.get():
            messagebox.showerror(APP_NAME, "Chrome and Edge profiles are required.")
            return
        firefox_enabled = bool(getattr(self, "firefox_enabled", None) and self.firefox_enabled.get())
        firefox_profile = Path(self.firefox.get()) if firefox_enabled and self.firefox.get() else None
        if firefox_enabled and firefox_profile is None:
            messagebox.showerror(APP_NAME, "A Firefox profile is required when Firefox support is enabled.")
            return
        try:
            preview = preview_synchronization(
                Path(self.chrome.get()),
                Path(self.edge.get()),
                deduplicate=self.deduplicate.get(),
                alphabetize=self.alphabetize.get(),
                duplicate_mode=self.duplicate_mode.get(),
                merge_strategy=self.merge_strategy.get(),
                firefox_profile=firefox_profile,
            )
            messagebox.showinfo(f"{APP_NAME} Preview", preview.render())
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def _open_backups(self) -> None:
        directory = Path(self.backups.get())
        directory.mkdir(parents=True, exist_ok=True)
        webbrowser.open(directory.as_uri())

    def _catalog_backups(self) -> None:
        try:
            status = self.catalog_filter.get()
            catalog = catalog_backup_sets(Path(self.backups.get()))
            selected = catalog.filtered(status)
            self.status.set(
                f"Cataloged {len(selected)} backup set(s) with the {status} filter. "
                "No files were changed."
            )
            messagebox.showinfo(f"{APP_NAME} Backup Catalog", catalog.render(status))
        except Exception as exc:
            messagebox.showerror(f"{APP_NAME} Backup Catalog", str(exc))

    def _verify_backup(self) -> None:
        selected = filedialog.askopenfilename(
            initialdir=self.backups.get(),
            title="Select JSON recovery snapshot to verify",
            filetypes=[("JSON recovery snapshots", "*.json")],
        )
        if not selected:
            return
        try:
            report = verify_json_backup(Path(selected))
            self.status.set(
                f"Verified {report.bookmark_count} bookmarks and {report.folder_count} folders. "
                "No live browser files were changed."
            )
            messagebox.showinfo(f"{APP_NAME} Verification", report.render())
        except Exception as exc:
            messagebox.showerror(f"{APP_NAME} Verification", str(exc))

    def _restore(self, browser: str) -> None:
        profile_value = self.chrome.get() if browser == "Chrome" else self.edge.get()
        if not profile_value:
            messagebox.showerror(APP_NAME, f"A {browser} profile is required.")
            return
        selected = filedialog.askopenfilename(
            initialdir=self.backups.get(),
            title=f"Select {browser} JSON recovery snapshot",
            filetypes=[("JSON recovery snapshots", "*.json")],
        )
        if not selected:
            return
        if not messagebox.askyesno(APP_NAME, f"Restore {browser} from {selected}?\n\nThe current file will be preserved first."):
            return
        try:
            preserved = restore_json_backup(
                Path(selected),
                Path(profile_value),
                browser,
                Path(self.backups.get()),
            )
            messagebox.showinfo(APP_NAME, f"{browser} was restored. Previous file: {preserved}")
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def _save_mapping(self) -> None:
        if not self.chrome.get() or not self.edge.get():
            messagebox.showerror(APP_NAME, "Chrome and Edge profiles are required.")
            return
        name = simpledialog.askstring(APP_NAME, "Mapping name:")
        if not name:
            return
        destination = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile="profile-mappings.json",
            filetypes=[("JSON mapping files", "*.json")],
        )
        if not destination:
            return
        try:
            save_profile_mapping(
                Path(destination),
                ProfileMapping(
                    name,
                    Path(self.chrome.get()),
                    Path(self.edge.get()),
                    Path(self.backups.get()),
                    Path(self.firefox.get()) if getattr(self, "firefox_enabled", None) and self.firefox_enabled.get() and self.firefox.get() else None,
                ),
            )
            messagebox.showinfo(APP_NAME, f"Saved profile mapping: {name}")
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def _load_mapping(self) -> None:
        selected = filedialog.askopenfilename(filetypes=[("JSON mapping files", "*.json")])
        if not selected:
            return
        try:
            mappings = load_profile_mappings(Path(selected))
            names = sorted(mappings)
            name = names[0] if len(names) == 1 else simpledialog.askstring(APP_NAME, f"Mapping name ({', '.join(names)}):")
            if not name:
                return
            mapping = mappings.get(name)
            if mapping is None:
                raise RuntimeError(f"No mapping named {name} exists in {selected}.")
            self.chrome.set(str(mapping.chrome_profile))
            self.edge.set(str(mapping.edge_profile))
            if mapping.firefox_profile and hasattr(self, "firefox"):
                self.firefox.set(str(mapping.firefox_profile))
                self.firefox_enabled.set(True)
            elif hasattr(self, "firefox"):
                self.firefox.set("")
                self.firefox_enabled.set(False)
                self.firefox_export.set(False)
            self.backups.set(str(mapping.backup_dir))
            self.status.set(f"Loaded profile mapping: {mapping.name}")
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_NAME)
    operation_options = parser.add_mutually_exclusive_group()
    operation_options.add_argument("--sync", action="store_true", help="Synchronize instead of backup/export only")
    operation_options.add_argument("--dry-run", action="store_true", help="Preview changes without backups, exports, or writes")
    operation_options.add_argument(
        "--check-automation",
        type=Path,
        help="Validate a private scheduler configuration without changing browser files",
    )
    operation_options.add_argument(
        "--run-automation",
        type=Path,
        help="Run a private scheduler configuration and write a privacy-safe JSON result",
    )
    operation_options.add_argument(
        "--verify-backup",
        type=Path,
        help="Verify a raw JSON recovery snapshot without changing browser files",
    )
    operation_options.add_argument(
        "--catalog-backups",
        action="store_true",
        help="Inventory generated backup sets without changing files",
    )
    operation_options.add_argument(
        "--compare-backups",
        nargs=2,
        metavar=("OLDER_STAMP", "NEWER_STAMP"),
        help="Compare counts in two complete, valid backup sets",
    )
    parser.add_argument("--chrome-profile", type=Path)
    parser.add_argument("--edge-profile", type=Path)
    parser.add_argument("--firefox-profile", type=Path, help="Explicit Firefox profile to import")
    parser.add_argument(
        "--enable-firefox",
        action="store_true",
        help="Enable the firefox_profile paths in named profile mappings",
    )
    parser.add_argument(
        "--firefox-export",
        action="store_true",
        help="Also write missing merged bookmarks to Firefox during --sync",
    )
    parser.add_argument("--backup-dir", type=Path, default=default_backup_dir())
    parser.add_argument("--profile-map", type=Path, help="Private JSON file containing named profile mappings")
    parser.add_argument("--mapping", action="append", help="Named mapping to run; repeat for multiple mappings")
    parser.add_argument(
        "--keep",
        type=backup_retention,
        default=MAX_BACKUPS,
        help="Number of backup sets to keep from 1 to 50",
    )
    parser.add_argument("--deduplicate", action="store_true", help="Remove duplicate URLs from the merged collection")
    parser.add_argument("--alphabetize", action="store_true", help="Sort folders and bookmarks alphabetically")
    parser.add_argument("--duplicate-mode", choices=DUPLICATE_MODES, default="conservative")
    parser.add_argument("--merge-strategy", choices=MERGE_STRATEGIES, default="chrome-wins")
    parser.add_argument("--restore-backup", type=Path, help="Raw JSON recovery snapshot to restore")
    parser.add_argument("--restore-browser", choices=("Chrome", "Edge"))
    parser.add_argument("--verify-manifest", type=Path, help="Manifest to use with --verify-backup")
    parser.add_argument("--catalog-filter", choices=BACKUP_CATALOG_FILTERS, default="all")
    parser.add_argument("--log-file", type=Path, help="Privacy-safe operation log path")
    parser.add_argument("--verbose", action="store_true", help="Print and log additional count-only details")
    parser.add_argument("--write-task-script", type=Path, help="Write a PowerShell scheduled-task registration script")
    parser.add_argument("--task-name", default=APP_NAME)
    parser.add_argument("--task-time", default="02:00")
    parser.add_argument("--task-sync", action="store_true", help="Opt in to synchronization in the generated task")
    process_options = parser.add_mutually_exclusive_group()
    process_options.add_argument("--force", action="store_true", help="Synchronize without checking for running browser processes")
    process_options.add_argument(
        "--close-browsers",
        action="store_true",
        help="Force-close selected write-target browsers before synchronization",
    )
    parser.add_argument("--gui", action="store_true", help="Open the desktop interface")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    has_cli_operation = any(
        (
            args.chrome_profile,
            args.edge_profile,
            args.firefox_profile,
            args.enable_firefox,
            args.firefox_export,
            args.profile_map,
            args.restore_backup,
            args.write_task_script,
            args.dry_run,
            args.sync,
            args.check_automation,
            args.run_automation,
            args.verify_backup,
            args.verify_manifest,
            args.catalog_backups,
            args.compare_backups,
            args.catalog_filter != "all",
        )
    )
    if args.gui or not has_cli_operation:
        root = tk.Tk()
        App(root)
        root.mainloop()
        return 0

    automation_path = args.check_automation or args.run_automation
    if automation_path:
        if args.force or args.close_browsers:
            document = {
                "schema_version": AUTOMATION_SCHEMA_VERSION,
                "kind": "automation-result" if args.run_automation else "automation-readiness",
                "status": "failed" if args.run_automation else "not-ready",
                "exit_code": 1,
                "error": "Automation process behavior must be defined only in the private configuration.",
            }
            print(json.dumps(document, indent=2))
            return 1
        try:
            config = load_automation_config(automation_path)
            if args.check_automation:
                document = automation_readiness(config)
                print(json.dumps(document, indent=2))
                return 0 if document["status"] == "ready" else 1
            exit_code, document = run_automation(config)
            print(json.dumps(document, indent=2))
            return exit_code
        except (OSError, RuntimeError) as exc:
            document = {
                "schema_version": AUTOMATION_SCHEMA_VERSION,
                "kind": "automation-result" if args.run_automation else "automation-readiness",
                "status": "failed" if args.run_automation else "not-ready",
                "exit_code": 1,
                "error": safe_automation_error(exc),
            }
            print(json.dumps(document, indent=2))
            return 1

    catalog_operation = args.catalog_backups or args.compare_backups
    if args.catalog_filter != "all" and not args.catalog_backups:
        print("Error: --catalog-filter requires --catalog-backups.", file=sys.stderr)
        return 1
    if catalog_operation:
        if args.restore_backup or args.restore_browser or args.write_task_script or args.verify_manifest:
            print("Error: backup catalog operations cannot be combined with restore, verification, or task generation.", file=sys.stderr)
            return 1
        try:
            catalog = catalog_backup_sets(args.backup_dir)
            if args.compare_backups:
                report = compare_backup_sets(catalog, *args.compare_backups).render()
            else:
                report = catalog.render(args.catalog_filter)
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(report)
        return 0

    if args.verify_manifest and not args.verify_backup:
        print("Error: --verify-manifest requires --verify-backup.", file=sys.stderr)
        return 1
    if args.verify_backup:
        if args.restore_backup or args.restore_browser or args.write_task_script:
            print("Error: backup verification cannot be combined with restore or task-script operations.", file=sys.stderr)
            return 1
        try:
            report = verify_json_backup(args.verify_backup, args.verify_manifest)
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(report.render())
        return 0

    try:
        firefox_enabled = args.enable_firefox or args.firefox_profile is not None
        if args.firefox_export and (
            not firefox_enabled or (not args.sync and not (args.write_task_script and args.task_sync))
        ):
            raise RuntimeError("--firefox-export requires Firefox to be enabled with --sync.")
        if args.profile_map and args.firefox_profile:
            raise RuntimeError("--firefox-profile cannot be combined with --profile-map; store the path in the mapping.")
        if args.profile_map:
            available = load_profile_mappings(args.profile_map)
            names = args.mapping or sorted(available)
            missing = [name for name in names if name not in available]
            if missing:
                raise RuntimeError(f"Unknown profile mapping(s): {', '.join(missing)}")
            mappings = [available[name] for name in names]
            if firefox_enabled and any(mapping.firefox_profile is None for mapping in mappings):
                raise RuntimeError("Firefox is enabled but a selected profile mapping has no firefox_profile.")
        else:
            if not args.chrome_profile or not args.edge_profile:
                raise RuntimeError("Both --chrome-profile and --edge-profile are required.")
            if firefox_enabled and args.firefox_profile is None:
                raise RuntimeError("--enable-firefox requires --firefox-profile for a direct run.")
            mappings = [ProfileMapping("direct", args.chrome_profile, args.edge_profile, args.backup_dir, args.firefox_profile)]
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if (args.restore_backup or args.write_task_script) and len(mappings) != 1:
        print("Error: restore and task-script operations require exactly one profile mapping.", file=sys.stderr)
        return 1

    if args.restore_backup:
        if not args.restore_browser:
            print("Error: --restore-browser is required with --restore-backup.", file=sys.stderr)
            return 1
        mapping = mappings[0]
        profile = mapping.chrome_profile if args.restore_browser == "Chrome" else mapping.edge_profile
        try:
            preserved = restore_json_backup(
                args.restore_backup,
                profile,
                args.restore_browser,
                mapping.backup_dir,
                force=args.force,
            )
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Restored {args.restore_browser}. Previous file: {preserved}")
        return 0

    if args.write_task_script:
        mapping = mappings[0]
        path = write_task_scheduler_script(
            args.write_task_script,
            mapping.chrome_profile,
            mapping.edge_profile,
            mapping.backup_dir,
            args.task_name,
            args.task_time,
            synchronize_task=args.task_sync,
            firefox_profile=mapping.firefox_profile if firefox_enabled else None,
            firefox_export=args.firefox_export,
        )
        print(f"Task Scheduler script: {path}")
        return 0

    for index, mapping in enumerate(mappings):
        if len(mappings) > 1:
            print(f"[{mapping.name}]")
        if args.dry_run:
            try:
                preview = preview_synchronization(
                    mapping.chrome_profile,
                    mapping.edge_profile,
                    deduplicate=args.deduplicate,
                    alphabetize=args.alphabetize,
                    duplicate_mode=args.duplicate_mode,
                    merge_strategy=args.merge_strategy,
                    firefox_profile=mapping.firefox_profile if firefox_enabled else None,
                )
            except RuntimeError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
            print(preview.render())
        else:
            try:
                result = synchronize(
                    mapping.chrome_profile,
                    mapping.edge_profile,
                    mapping.backup_dir,
                    firefox_profile=mapping.firefox_profile if firefox_enabled else None,
                    firefox_export=args.firefox_export,
                    keep=args.keep,
                    write=args.sync,
                    deduplicate=args.deduplicate,
                    alphabetize=args.alphabetize,
                    force=args.force,
                    close_browsers=args.close_browsers,
                    duplicate_mode=args.duplicate_mode,
                    merge_strategy=args.merge_strategy,
                    log_file=args.log_file,
                    verbose=args.verbose,
                )
            except RuntimeError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
            output = [f"Bookmarks: {result.merged_count}"]
            if firefox_enabled:
                output.append(f"Firefox bookmarks read: {result.firefox_count}")
                output.append(
                    f"Firefox bookmarks added: {result.firefox_added if args.firefox_export else 'Disabled'}"
                )
            output.extend(
                [
                    f"Duplicates removed: {result.duplicates_removed}",
                    f"Alphabetized: {'Yes' if result.alphabetized else 'No'}",
                    f"Browsers closed: {', '.join(result.closed_processes) if result.closed_processes else 'No'}",
                    f"HTML: {result.html_path}",
                    f"Manifest: {result.manifest_path}",
                    f"Log: {result.log_path}",
                    f"Backups: {result.backup_dir}",
                ]
            )
            print("\n".join(output))
            if args.verbose:
                print(result.preview.render())
        if index < len(mappings) - 1:
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
