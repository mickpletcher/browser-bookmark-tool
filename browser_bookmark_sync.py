from __future__ import annotations

import argparse
import copy
import csv
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
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
MAX_BACKUPS = 50
DUPLICATE_MODES = ("conservative", "aggressive")
MERGE_STRATEGIES = ("chrome-wins", "edge-wins", "preserve-both", "merge-folders", "dated-folder")
AUTOMATION_SCHEMA_VERSION = 1
AUTOMATION_OPERATIONS = ("backup", "sync", "dry-run")
AUTOMATION_BROWSER_BEHAVIORS = ("block", "close")
BACKUP_NAME_PATTERN = re.compile(
    r"^(?P<prefix>Chrome|Edge|Bookmarks|Manifest)_"
    r"(?P<stamp>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:_\d{6})?)"
    r"\.(?P<extension>json|html)$"
)


def local_app_data() -> Path:
    value = os.environ.get("LOCALAPPDATA")
    if not value:
        raise RuntimeError("LOCALAPPDATA is unavailable. This app currently supports Windows.")
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


def close_browser_processes(processes: Iterable[str]) -> None:
    requested = {process.casefold() for process in processes}
    for process in BROWSER_PROCESS_NAMES:
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
    result_file: Path
    lock_file: Path
    lock_timeout_minutes: int


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
    for option in ("deduplicate", "alphabetize"):
        if not isinstance(document.get(option, False), bool):
            raise RuntimeError(f"Automation {option} must be true or false.")

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
    if not isinstance(result_value, str) or not result_value.strip():
        raise RuntimeError("Automation result_file must be a non-empty path string.")
    if not isinstance(lock_value, str) or not lock_value.strip():
        raise RuntimeError("Automation lock_file must be a non-empty path string.")
    result_file = config_relative_path(result_value, source)
    lock_file = config_relative_path(lock_value, source)
    if result_file == lock_file:
        raise RuntimeError("Automation result_file and lock_file must be different paths.")

    lock_timeout = document.get("lock_timeout_minutes", 180)
    if isinstance(lock_timeout, bool) or not isinstance(lock_timeout, int) or not 5 <= lock_timeout <= 1440:
        raise RuntimeError("Automation lock_timeout_minutes must be from 5 to 1440.")

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
        result_file=result_file,
        lock_file=lock_file,
        lock_timeout_minutes=lock_timeout,
    )


class AutomationRunLock:
    def __init__(self, path: Path, stale_minutes: int) -> None:
        self.path = path
        self.stale_seconds = stale_minutes * 60
        self.token = str(uuid.uuid4())
        self.acquired = False

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
        document["summary"] = {
            "chrome_count": preview.chrome_count,
            "edge_count": preview.edge_count,
            "merged_count": preview.merged_count,
            "duplicates_removed": preview.duplicates_removed,
            "merge_strategy": preview.merge_strategy,
            "duplicate_mode": preview.duplicate_mode,
        }
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
) -> Path:
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", task_time):
        raise RuntimeError("Task time must use 24-hour HH:MM format.")
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
    if synchronize_task:
        arguments.append("--sync")
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
        raise RuntimeError(f"The merged bookmark data contains duplicate GUID values: {values}")


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
    groups: dict[str, list[tuple[str, Path]]] = {"Chrome": [], "Edge": [], "Bookmarks": [], "Manifest": []}
    for path in directory.glob("*"):
        if not path.is_file() or not (match := BACKUP_NAME_PATTERN.fullmatch(path.name)):
            continue
        prefix = match.group("prefix")
        extension = match.group("extension")
        if prefix == "Bookmarks" and extension != "html":
            continue
        if prefix != "Bookmarks" and extension != "json":
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

    def render(self) -> str:
        return (
            f"Strategy: {self.merge_strategy}\n"
            f"Duplicate matching: {self.duplicate_mode}\n"
            f"Chrome bookmarks: {self.chrome_count}\n"
            f"Edge favorites: {self.edge_count}\n"
            f"Chrome-only URLs: {self.chrome_only}\n"
            f"Edge-only URLs: {self.edge_only}\n"
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


def prepare_merged_data(
    chrome: dict[str, Any],
    edge: dict[str, Any],
    deduplicate: bool = False,
    alphabetize: bool = False,
    duplicate_mode: str = "conservative",
    merge_strategy: str = "chrome-wins",
) -> tuple[dict[str, Any], SyncPreview]:
    if merge_strategy not in MERGE_STRATEGIES:
        raise RuntimeError(f"Merge strategy must be one of: {', '.join(MERGE_STRATEGIES)}")
    chrome_urls = [normalized_url(node["url"], duplicate_mode) for root in chrome.get("roots", {}).values() for node in iter_urls(root)]
    edge_urls = [normalized_url(node["url"], duplicate_mode) for root in edge.get("roots", {}).values() for node in iter_urls(root)]
    chrome_keys = set(chrome_urls)
    edge_keys = set(edge_urls)

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
    duplicates_removed = deduplicate_bookmarks(merged, duplicate_mode) if deduplicate else 0
    folders_reordered = alphabetize_bookmarks(merged) if alphabetize else 0
    preview = SyncPreview(
        chrome_count=len(chrome_urls),
        edge_count=len(edge_urls),
        chrome_only=len(chrome_keys - edge_keys),
        edge_only=len(edge_keys - chrome_keys),
        input_duplicates=(len(chrome_urls) - len(chrome_keys)) + (len(edge_urls) - len(edge_keys)),
        duplicates_removed=duplicates_removed,
        merged_count=count_bookmarks(merged),
        folders_added=max(0, count_folders(merged) - primary_folder_count),
        folders_reordered=folders_reordered,
        merge_strategy=merge_strategy,
        duplicate_mode=duplicate_mode,
    )
    return merged, preview


def preview_synchronization(
    chrome_profile: Path,
    edge_profile: Path,
    deduplicate: bool = False,
    alphabetize: bool = False,
    duplicate_mode: str = "conservative",
    merge_strategy: str = "chrome-wins",
) -> SyncPreview:
    _, preview = prepare_merged_data(
        read_bookmarks(chrome_profile),
        read_bookmarks(edge_profile),
        deduplicate=deduplicate,
        alphabetize=alphabetize,
        duplicate_mode=duplicate_mode,
        merge_strategy=merge_strategy,
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
) -> SyncResult:
    if not 1 <= keep <= MAX_BACKUPS:
        raise RuntimeError(f"Backup retention must be from 1 to {MAX_BACKUPS}.")
    if force and close_browsers:
        raise RuntimeError("--force and --close-browsers cannot be used together.")
    chrome = read_bookmarks(chrome_profile)
    edge = read_bookmarks(edge_profile)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    backup_dir.mkdir(parents=True, exist_ok=True)
    chrome_backup = backup_dir / f"Chrome_{stamp}.json"
    edge_backup = backup_dir / f"Edge_{stamp}.json"
    shutil.copy2(chrome_profile / "Bookmarks", chrome_backup)
    shutil.copy2(edge_profile / "Bookmarks", edge_backup)

    merged, preview = prepare_merged_data(
        chrome,
        edge,
        deduplicate=deduplicate,
        alphabetize=alphabetize,
        duplicate_mode=duplicate_mode,
        merge_strategy=merge_strategy,
    )
    html_path = backup_dir / f"Bookmarks_{stamp}.html"
    merged_count = export_html(merged, html_path)
    manifest_path = write_backup_manifest(
        backup_dir / f"Manifest_{stamp}.json",
        [chrome_backup, edge_backup, html_path],
        preview,
    )
    log_path = log_file or backup_dir / "browser-bookmark-tool.log"
    write_privacy_safe_log(
        log_path,
        "backup_export_complete",
        chrome_count=preview.chrome_count,
        edge_count=preview.edge_count,
        merged_count=preview.merged_count,
        manifest=manifest_path.name,
    )
    prune_backups(backup_dir, keep)
    closed_processes: tuple[str, ...] = ()
    if write:
        if not force:
            try:
                running = running_browser_processes()
            except RuntimeError as exc:
                raise RuntimeError(
                    f"{exc} Backups and the HTML export were created in {backup_dir}."
                ) from exc
            if running and close_browsers:
                closed_processes = tuple(running)
                close_browser_processes(running)
                try:
                    running = wait_for_browsers_to_close()
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
        transactional_json_write(chrome_profile / "Bookmarks", edge_profile / "Bookmarks", merged)
        write_privacy_safe_log(
            log_path,
            "sync_complete",
            closed_processes=",".join(closed_processes) or "none",
            duplicates_removed=preview.duplicates_removed,
            strategy=merge_strategy,
        )
    elif verbose:
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
        for path in (mapping.chrome_profile, mapping.edge_profile, mapping.backup_dir)
    ):
        raise RuntimeError("Automation profile mappings must use absolute browser and backup paths.")
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
    if "browser process" in folded or "synchronization blocked" in folded:
        detected = [process for process in BROWSER_PROCESS_NAMES if process in folded]
        suffix = f": {', '.join(detected)}" if detected else ""
        return f"Synchronization was blocked by running browser processes{suffix}."
    if "no bookmarks file" in folded:
        return "A configured browser profile does not contain a Bookmarks file."
    if "not valid json" in folded:
        return "A configured browser bookmark file is not valid JSON."
    if "unknown automation mapping" in folded:
        return message
    if "profile mapping" in folded:
        return "The private profile mapping configuration is invalid."
    return "Automation failed. Review the private local operation log for details."


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
            )
        except (OSError, RuntimeError) as exc:
            errors.append(f"{mapping.name}: {safe_automation_error(exc)}")
        if not writable_existing_parent(mapping.backup_dir):
            errors.append(f"{mapping.name}: The backup destination is not writable.")
    if not writable_existing_parent(config.result_file):
        errors.append("The automation result destination is not writable.")
    if not writable_existing_parent(config.lock_file):
        errors.append("The automation lock destination is not writable.")

    if config.lock_file.exists():
        age = time.time() - config.lock_file.stat().st_mtime
        if age <= config.lock_timeout_minutes * 60:
            errors.append("Another browser bookmark automation run is already active.")
        else:
            warnings.append("A stale automation lock will be replaced when the run starts.")

    try:
        processes = running_browser_processes()
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
    artifacts = {prefix: set() for prefix in ("Chrome", "Edge", "Bookmarks", "Manifest")}
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
    with AutomationRunLock(config.lock_file, config.lock_timeout_minutes):
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
                    )
                    mapping_results.append(preview_result(mapping.name, preview))
                    continue
                before = automation_artifact_names(mapping.backup_dir)
                try:
                    result = synchronize(
                        mapping.chrome_profile,
                        mapping.edge_profile,
                        mapping.backup_dir,
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
                        and bool(after["Edge"] - before["Edge"]),
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
    return exit_code, document


class App(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=18)
        self.master = master
        master.title(APP_NAME)
        master.minsize(760, 620)
        self.chrome = tk.StringVar()
        self.edge = tk.StringVar()
        self.backups = tk.StringVar(value=str(default_backup_dir()))
        self.keep = tk.IntVar(value=MAX_BACKUPS)
        self.deduplicate = tk.BooleanVar(value=False)
        self.alphabetize = tk.BooleanVar(value=False)
        self.duplicate_mode = tk.StringVar(value="conservative")
        self.merge_strategy = tk.StringVar(value="chrome-wins")
        self.status = tk.StringVar(value="Select a Chrome and Edge profile.")
        self._build()
        self._detect()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text=APP_NAME, font=("Segoe UI", 18, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(self, text="Back up, export, and synchronize Chrome and Edge bookmarks.").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 18))
        self.chrome_box = self._profile_row(2, "Chrome profile", self.chrome)
        self.edge_box = self._profile_row(3, "Edge profile", self.edge)
        ttk.Label(self, text="Backup folder").grid(row=4, column=0, sticky="w", pady=8)
        ttk.Entry(self, textvariable=self.backups).grid(row=4, column=1, sticky="ew", padx=10)
        ttk.Button(self, text="Browse…", command=self._browse).grid(row=4, column=2)
        ttk.Label(self, text="Backup sets to keep").grid(row=5, column=0, sticky="w", pady=8)
        ttk.Spinbox(self, from_=1, to=MAX_BACKUPS, textvariable=self.keep, width=8).grid(row=5, column=1, sticky="w", padx=10)
        options = ttk.Frame(self)
        options.grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Checkbutton(options, text="Remove duplicate bookmarks", variable=self.deduplicate).pack(side="left")
        ttk.Checkbutton(options, text="Alphabetize bookmarks", variable=self.alphabetize).pack(side="left", padx=16)
        ttk.Label(self, text="Duplicate matching").grid(row=7, column=0, sticky="w", pady=8)
        ttk.Combobox(
            self,
            textvariable=self.duplicate_mode,
            values=DUPLICATE_MODES,
            state="readonly",
            width=20,
        ).grid(row=7, column=1, sticky="w", padx=10)
        ttk.Label(self, text="Merge strategy").grid(row=8, column=0, sticky="w", pady=8)
        ttk.Combobox(
            self,
            textvariable=self.merge_strategy,
            values=MERGE_STRATEGIES,
            state="readonly",
            width=24,
        ).grid(row=8, column=1, sticky="w", padx=10)
        note = "Close Chrome and Edge before syncing. A raw backup of each browser is created before any changes are written."
        ttk.Label(self, text=note, wraplength=700, foreground="#8a4b08").grid(row=9, column=0, columnspan=3, sticky="w", pady=(18, 12))
        buttons = ttk.Frame(self)
        buttons.grid(row=10, column=0, columnspan=3, sticky="ew")
        ttk.Button(buttons, text="Preview Changes", command=self._preview).pack(side="left")
        ttk.Button(buttons, text="Back Up + Export HTML", command=lambda: self._run(False)).pack(side="left")
        ttk.Button(buttons, text="Back Up + Sync", command=lambda: self._run(True)).pack(side="left", padx=8)
        ttk.Button(buttons, text="Open Backup Folder", command=self._open_backups).pack(side="left")
        management = ttk.Frame(self)
        management.grid(row=11, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(management, text="Restore Chrome", command=lambda: self._restore("Chrome")).pack(side="left")
        ttk.Button(management, text="Restore Edge", command=lambda: self._restore("Edge")).pack(side="left", padx=8)
        ttk.Button(management, text="Save Profile Mapping", command=self._save_mapping).pack(side="left")
        ttk.Button(management, text="Load Profile Mapping", command=self._load_mapping).pack(side="left", padx=8)
        ttk.Separator(self).grid(row=12, column=0, columnspan=3, sticky="ew", pady=18)
        ttk.Label(self, textvariable=self.status, wraplength=700).grid(row=13, column=0, columnspan=3, sticky="w")
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
            self.status.set(f"Detected {len(chrome)} Chrome profile(s) and {len(edge)} Edge profile(s).")
        except Exception as exc:
            self.status.set(str(exc))

    def _browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.backups.get())
        if chosen:
            self.backups.set(chosen)

    def _run(self, write: bool) -> None:
        if not self.chrome.get() or not self.edge.get():
            messagebox.showerror(APP_NAME, "Chrome and Edge profiles are required.")
            return
        if write and not messagebox.askyesno(APP_NAME, "Are Chrome and Edge completely closed?\n\nTheir bookmark files will be synchronized after backups are created."):
            return
        try:
            result = synchronize(
                Path(self.chrome.get()),
                Path(self.edge.get()),
                Path(self.backups.get()),
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
        try:
            preview = preview_synchronization(
                Path(self.chrome.get()),
                Path(self.edge.get()),
                deduplicate=self.deduplicate.get(),
                alphabetize=self.alphabetize.get(),
                duplicate_mode=self.duplicate_mode.get(),
                merge_strategy=self.merge_strategy.get(),
            )
            messagebox.showinfo(f"{APP_NAME} Preview", preview.render())
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def _open_backups(self) -> None:
        directory = Path(self.backups.get())
        directory.mkdir(parents=True, exist_ok=True)
        webbrowser.open(directory.as_uri())

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
                ProfileMapping(name, Path(self.chrome.get()), Path(self.edge.get()), Path(self.backups.get())),
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
    parser.add_argument("--chrome-profile", type=Path)
    parser.add_argument("--edge-profile", type=Path)
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
        help="Force-close Chrome and Edge before synchronization",
    )
    parser.add_argument("--gui", action="store_true", help="Open the desktop interface")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    has_cli_operation = any(
        (
            args.chrome_profile,
            args.edge_profile,
            args.profile_map,
            args.restore_backup,
            args.write_task_script,
            args.dry_run,
            args.sync,
            args.check_automation,
            args.run_automation,
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

    try:
        if args.profile_map:
            available = load_profile_mappings(args.profile_map)
            names = args.mapping or sorted(available)
            missing = [name for name in names if name not in available]
            if missing:
                raise RuntimeError(f"Unknown profile mapping(s): {', '.join(missing)}")
            mappings = [available[name] for name in names]
        else:
            if not args.chrome_profile or not args.edge_profile:
                raise RuntimeError("Both --chrome-profile and --edge-profile are required.")
            mappings = [ProfileMapping("direct", args.chrome_profile, args.edge_profile, args.backup_dir)]
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
            print(
                f"Bookmarks: {result.merged_count}\n"
                f"Duplicates removed: {result.duplicates_removed}\n"
                f"Alphabetized: {'Yes' if result.alphabetized else 'No'}\n"
                f"Browsers closed: {', '.join(result.closed_processes) if result.closed_processes else 'No'}\n"
                f"HTML: {result.html_path}\n"
                f"Manifest: {result.manifest_path}\n"
                f"Log: {result.log_path}\n"
                f"Backups: {result.backup_dir}"
            )
            if args.verbose:
                print(result.preview.render())
        if index < len(mappings) - 1:
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
