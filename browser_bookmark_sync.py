from __future__ import annotations

import argparse
import copy
import datetime as dt
import html
import json
import os
import shutil
import sys
import tempfile
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Iterable


APP_NAME = "Browser Bookmark Tool"
ROOT_NAMES = ("bookmark_bar", "other", "synced")


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


def read_bookmarks(profile: Path) -> dict[str, Any]:
    path = profile / "Bookmarks"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"No Bookmarks file exists in {profile}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"The Bookmarks file in {profile} is not valid JSON") from exc


def atomic_json_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="Bookmarks.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


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


def merge_bookmarks(primary: dict[str, Any], secondary: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Return a conservative union, retaining primary folders and appending unique URLs."""
    merged = copy.deepcopy(primary)
    roots = merged.setdefault("roots", {})
    known = {normalized_url(n["url"]) for root in roots.values() for n in iter_urls(root)}
    next_id = max(max_numeric_id(primary), max_numeric_id(secondary)) + 1
    added = 0

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
            next_id += 1
            added += 1
            return result
        if node.get("type") == "folder":
            children = [item for child in node.get("children", []) if (item := clone_unique(child)) is not None]
            if not children:
                return None
            result = copy.deepcopy(node)
            result["id"] = str(next_id)
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
            "guid": "00000000-0000-4000-8000-000000000000",
            "id": str(next_id),
            "name": "Imported from other browser",
            "type": "folder",
        }
        destination.setdefault("children", []).append(folder)
    merged.pop("checksum", None)
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
    html_path: Path
    backup_dir: Path


def synchronize(chrome_profile: Path, edge_profile: Path, backup_dir: Path, keep: int = 30, write: bool = True) -> SyncResult:
    chrome = read_bookmarks(chrome_profile)
    edge = read_bookmarks(edge_profile)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(chrome_profile / "Bookmarks", backup_dir / f"Chrome_{stamp}.json")
    shutil.copy2(edge_profile / "Bookmarks", backup_dir / f"Edge_{stamp}.json")

    merged, _ = merge_bookmarks(chrome, edge)
    merged, _ = merge_bookmarks(merged, chrome)
    html_path = backup_dir / f"Bookmarks_{stamp}.html"
    merged_count = export_html(merged, html_path)
    if write:
        atomic_json_write(chrome_profile / "Bookmarks", merged)
        atomic_json_write(edge_profile / "Bookmarks", merged)
    prune_backups(backup_dir, max(1, keep))
    return SyncResult(
        chrome_count=sum(1 for root in chrome.get("roots", {}).values() for _ in iter_urls(root)),
        edge_count=sum(1 for root in edge.get("roots", {}).values() for _ in iter_urls(root)),
        merged_count=merged_count,
        html_path=html_path,
        backup_dir=backup_dir,
    )


class App(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=18)
        self.master = master
        master.title(APP_NAME)
        master.minsize(680, 430)
        self.chrome = tk.StringVar()
        self.edge = tk.StringVar()
        self.backups = tk.StringVar(value=str(default_backup_dir()))
        self.keep = tk.IntVar(value=30)
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
        ttk.Label(self, text="Copies to keep").grid(row=5, column=0, sticky="w", pady=8)
        ttk.Spinbox(self, from_=1, to=365, textvariable=self.keep, width=8).grid(row=5, column=1, sticky="w", padx=10)
        note = "Close Chrome and Edge before syncing. A raw backup of each browser is created before any changes are written."
        ttk.Label(self, text=note, wraplength=620, foreground="#8a4b08").grid(row=6, column=0, columnspan=3, sticky="w", pady=(18, 12))
        buttons = ttk.Frame(self)
        buttons.grid(row=7, column=0, columnspan=3, sticky="ew")
        ttk.Button(buttons, text="Back Up + Export HTML", command=lambda: self._run(False)).pack(side="left")
        ttk.Button(buttons, text="Back Up + Sync", command=lambda: self._run(True)).pack(side="left", padx=8)
        ttk.Button(buttons, text="Open Backup Folder", command=self._open_backups).pack(side="left")
        ttk.Separator(self).grid(row=8, column=0, columnspan=3, sticky="ew", pady=18)
        ttk.Label(self, textvariable=self.status, wraplength=630).grid(row=9, column=0, columnspan=3, sticky="w")
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
            result = synchronize(Path(self.chrome.get()), Path(self.edge.get()), Path(self.backups.get()), self.keep.get(), write)
            action = "Synchronized" if write else "Exported"
            self.status.set(f"{action} {result.merged_count} unique bookmarks. HTML: {result.html_path}")
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
    parser.add_argument("--keep", type=int, default=30)
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
    result = synchronize(args.chrome_profile, args.edge_profile, args.backup_dir, args.keep, args.sync)
    print(f"Bookmarks: {result.merged_count}\nHTML: {result.html_path}\nBackups: {result.backup_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
