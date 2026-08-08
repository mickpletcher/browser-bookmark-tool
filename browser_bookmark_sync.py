from __future__ import annotations

import argparse
import copy
import csv
import datetime as dt
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import uuid
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Iterable


APP_NAME = "Browser Bookmark Tool"
ROOT_NAMES = ("bookmark_bar", "other", "synced")
BROWSER_PROCESS_NAMES = ("chrome.exe", "msedge.exe")
MAX_BACKUPS = 50


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


def normalized_url(url: str) -> str:
    value = url.strip()
    if value.endswith("/") and value.count("/") > 2:
        value = value[:-1]
    return value.casefold()


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


def deduplicate_bookmarks(data: dict[str, Any]) -> int:
    known: set[str] = set()
    removed = 0

    def remove_duplicates(node: dict[str, Any]) -> None:
        nonlocal removed
        children = []
        for child in node.get("children", []):
            if child.get("type") == "url" and child.get("url"):
                key = normalized_url(child["url"])
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


def alphabetize_bookmarks(data: dict[str, Any]) -> None:
    def sort_children(node: dict[str, Any]) -> None:
        children = node.get("children", [])
        for child in children:
            if child.get("type") == "folder":
                sort_children(child)
        children.sort(
            key=lambda child: (
                child.get("type") != "folder",
                str(child.get("name") or child.get("url") or "").casefold(),
            )
        )

    for root_name in ROOT_NAMES:
        root = data.get("roots", {}).get(root_name)
        if root:
            sort_children(root)


def merge_bookmarks(primary: dict[str, Any], secondary: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Return a conservative union, retaining primary folders and appending unique URLs."""
    merged = copy.deepcopy(primary)
    roots = merged.setdefault("roots", {})
    known = {normalized_url(n["url"]) for root in roots.values() for n in iter_urls(root)}
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
            key = normalized_url(url)
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

    destination = roots.get("other") or roots.get("bookmark_bar")
    if destination is None:
        raise RuntimeError("The primary browser file has no recognized bookmark roots.")
    imported_children: list[dict[str, Any]] = []
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
            "name": "Imported from other browser",
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
    groups: dict[str, list[Path]] = {"Chrome": [], "Edge": [], "Bookmarks": []}
    for path in directory.glob("*"):
        for prefix in groups:
            if path.name.startswith(prefix + "_"):
                groups[prefix].append(path)
    for paths in groups.values():
        for old in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)[keep:]:
            old.unlink()


@dataclass
class SyncResult:
    chrome_count: int
    edge_count: int
    merged_count: int
    duplicates_removed: int
    alphabetized: bool
    closed_processes: tuple[str, ...]
    html_path: Path
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
) -> SyncResult:
    if not 1 <= keep <= MAX_BACKUPS:
        raise RuntimeError(f"Backup retention must be from 1 to {MAX_BACKUPS}.")
    if force and close_browsers:
        raise RuntimeError("--force and --close-browsers cannot be used together.")
    chrome = read_bookmarks(chrome_profile)
    edge = read_bookmarks(edge_profile)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(chrome_profile / "Bookmarks", backup_dir / f"Chrome_{stamp}.json")
    shutil.copy2(edge_profile / "Bookmarks", backup_dir / f"Edge_{stamp}.json")

    merged, _ = merge_bookmarks(chrome, edge)
    duplicates_removed = deduplicate_bookmarks(merged) if deduplicate else 0
    if alphabetize:
        alphabetize_bookmarks(merged)
    html_path = backup_dir / f"Bookmarks_{stamp}.html"
    merged_count = export_html(merged, html_path)
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
                raise RuntimeError(
                    f"Synchronization blocked because these browser processes are running: {names}. "
                    f"Close them completely and try again. Backups and the HTML export were created in "
                    f"{backup_dir}. HTML: {html_path}"
                )
        transactional_json_write(chrome_profile / "Bookmarks", edge_profile / "Bookmarks", merged)
    return SyncResult(
        chrome_count=sum(1 for root in chrome.get("roots", {}).values() for _ in iter_urls(root)),
        edge_count=sum(1 for root in edge.get("roots", {}).values() for _ in iter_urls(root)),
        merged_count=merged_count,
        duplicates_removed=duplicates_removed,
        alphabetized=alphabetize,
        closed_processes=closed_processes,
        html_path=html_path,
        backup_dir=backup_dir,
    )


class App(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=18)
        self.master = master
        master.title(APP_NAME)
        master.minsize(680, 470)
        self.chrome = tk.StringVar()
        self.edge = tk.StringVar()
        self.backups = tk.StringVar(value=str(default_backup_dir()))
        self.keep = tk.IntVar(value=MAX_BACKUPS)
        self.deduplicate = tk.BooleanVar(value=False)
        self.alphabetize = tk.BooleanVar(value=False)
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
        note = "Close Chrome and Edge before syncing. A raw backup of each browser is created before any changes are written."
        ttk.Label(self, text=note, wraplength=620, foreground="#8a4b08").grid(row=7, column=0, columnspan=3, sticky="w", pady=(18, 12))
        buttons = ttk.Frame(self)
        buttons.grid(row=8, column=0, columnspan=3, sticky="ew")
        ttk.Button(buttons, text="Back Up + Export HTML", command=lambda: self._run(False)).pack(side="left")
        ttk.Button(buttons, text="Back Up + Sync", command=lambda: self._run(True)).pack(side="left", padx=8)
        ttk.Button(buttons, text="Open Backup Folder", command=self._open_backups).pack(side="left")
        ttk.Separator(self).grid(row=9, column=0, columnspan=3, sticky="ew", pady=18)
        ttk.Label(self, textvariable=self.status, wraplength=630).grid(row=10, column=0, columnspan=3, sticky="w")
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

    def _open_backups(self) -> None:
        directory = Path(self.backups.get())
        directory.mkdir(parents=True, exist_ok=True)
        webbrowser.open(directory.as_uri())


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--sync", action="store_true", help="Synchronize instead of backup/export only")
    parser.add_argument("--chrome-profile", type=Path)
    parser.add_argument("--edge-profile", type=Path)
    parser.add_argument("--backup-dir", type=Path, default=default_backup_dir())
    parser.add_argument(
        "--keep",
        type=backup_retention,
        default=MAX_BACKUPS,
        help="Number of backup sets to keep from 1 to 50",
    )
    parser.add_argument("--deduplicate", action="store_true", help="Remove duplicate URLs from the merged collection")
    parser.add_argument("--alphabetize", action="store_true", help="Sort folders and bookmarks alphabetically")
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
    if args.gui or (not args.chrome_profile and not args.edge_profile):
        root = tk.Tk()
        App(root)
        root.mainloop()
        return 0
    if not args.chrome_profile or not args.edge_profile:
        raise SystemExit("Both --chrome-profile and --edge-profile are required.")
    try:
        result = synchronize(
            args.chrome_profile,
            args.edge_profile,
            args.backup_dir,
            keep=args.keep,
            write=args.sync,
            deduplicate=args.deduplicate,
            alphabetize=args.alphabetize,
            force=args.force,
            close_browsers=args.close_browsers,
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
        f"Backups: {result.backup_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
