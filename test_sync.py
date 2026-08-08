import json
import os
from pathlib import Path
import uuid

import pytest

import browser_bookmark_sync as sync_module
from browser_bookmark_sync import (
    App,
    alphabetize_bookmarks,
    close_browser_processes,
    deduplicate_bookmarks,
    export_html,
    iter_urls,
    main,
    merge_bookmarks,
    parse_args,
    prune_backups,
    running_browser_processes,
    synchronize,
    validate_unique_guids,
)


def data(*urls: str) -> dict:
    children = [{"type": "url", "id": str(i + 10), "name": url, "url": url} for i, url in enumerate(urls)]
    return {"roots": {"bookmark_bar": {"type": "folder", "id": "1", "name": "Bookmarks bar", "children": children}, "other": {"type": "folder", "id": "2", "name": "Other bookmarks", "children": []}}, "version": 1, "checksum": "old"}


@pytest.fixture(autouse=True)
def no_running_browsers(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sync_module, "running_browser_processes", lambda: [])


def test_merge_deduplicates_and_retains_unique_links():
    merged, added = merge_bookmarks(data("https://a.test/", "https://b.test"), data("https://a.test", "https://c.test"))
    urls = [node["url"] for root in merged["roots"].values() for node in iter_urls(root)]
    assert added == 1
    assert urls.count("https://c.test") == 1
    assert "checksum" not in merged


def test_merge_regenerates_imported_guids_and_preserves_primary_guids():
    primary = data("https://chrome.test")
    primary["roots"]["bookmark_bar"]["guid"] = "00000000-0000-4000-a000-000000000002"
    primary["roots"]["bookmark_bar"]["children"][0]["guid"] = "11111111-1111-4111-8111-111111111111"
    primary["roots"]["other"]["guid"] = "00000000-0000-4000-a000-000000000003"
    secondary = data()
    secondary["roots"]["bookmark_bar"]["children"] = [
        {
            "type": "folder",
            "id": "20",
            "guid": "22222222-2222-4222-8222-222222222222",
            "name": "Edge folder",
            "children": [
                {
                    "type": "url",
                    "id": "21",
                    "guid": "33333333-3333-4333-8333-333333333333",
                    "name": "Edge link",
                    "url": "https://edge.test",
                }
            ],
        }
    ]

    merged, added = merge_bookmarks(primary, secondary)
    guids = [
        node["guid"]
        for root in merged["roots"].values()
        for node in sync_module.walk_nodes(root)
        if node.get("guid")
    ]

    assert added == 1
    assert "11111111-1111-4111-8111-111111111111" in guids
    assert "22222222-2222-4222-8222-222222222222" not in guids
    assert "33333333-3333-4333-8333-333333333333" not in guids
    assert len(guids) == len(set(guid.casefold() for guid in guids))
    for guid in guids:
        uuid.UUID(guid)


def test_guid_validation_rejects_duplicates():
    bookmarks = data("https://one.test", "https://two.test")
    for child in bookmarks["roots"]["bookmark_bar"]["children"]:
        child["guid"] = "11111111-1111-4111-8111-111111111111"

    with pytest.raises(RuntimeError, match="duplicate GUID values"):
        validate_unique_guids(bookmarks)


def test_export_html(tmp_path: Path):
    destination = tmp_path / "bookmarks.html"
    count = export_html(data("https://example.test/?a=1&b=2"), destination)
    assert count == 1
    assert "NETSCAPE-Bookmark-file-1" in destination.read_text()
    assert "&amp;" in destination.read_text()


def test_deduplicate_bookmarks_removes_normalized_urls_across_folders():
    bookmarks = data("https://first.test", "https://duplicate.test/")
    bookmarks["roots"]["other"]["children"] = [
        {
            "type": "folder",
            "id": "20",
            "name": "Nested",
            "children": [
                {"type": "url", "id": "21", "name": "Duplicate", "url": "https://duplicate.test"},
                {"type": "url", "id": "22", "name": "Unique", "url": "https://unique.test"},
            ],
        }
    ]

    removed = deduplicate_bookmarks(bookmarks)
    urls = [node["url"] for root in bookmarks["roots"].values() for node in iter_urls(root)]

    assert removed == 1
    assert urls == ["https://first.test", "https://duplicate.test/", "https://unique.test"]


def test_alphabetize_bookmarks_sorts_folders_first_and_recursively():
    bookmarks = data()
    bookmarks["roots"]["bookmark_bar"]["children"] = [
        {"type": "url", "id": "10", "name": "Zulu", "url": "https://zulu.test"},
        {
            "type": "folder",
            "id": "11",
            "name": "beta folder",
            "children": [
                {"type": "url", "id": "12", "name": "Zulu", "url": "https://nested-zulu.test"},
                {"type": "url", "id": "13", "name": "Alpha", "url": "https://nested-alpha.test"},
            ],
        },
        {"type": "url", "id": "14", "name": "alpha", "url": "https://alpha.test"},
        {"type": "folder", "id": "15", "name": "Alpha folder", "children": []},
    ]

    alphabetize_bookmarks(bookmarks)
    children = bookmarks["roots"]["bookmark_bar"]["children"]

    assert [child["name"] for child in children] == ["Alpha folder", "beta folder", "alpha", "Zulu"]
    assert [child["name"] for child in children[1]["children"]] == ["Alpha", "Zulu"]


def test_organization_options_are_disabled_by_default():
    args = parse_args([])

    assert args.keep == 50
    assert not args.deduplicate
    assert not args.alphabetize
    assert not args.force
    assert not args.close_browsers


def test_backup_retention_rejects_values_above_50():
    with pytest.raises(SystemExit):
        parse_args(["--keep", "51"])


def test_backup_retention_keeps_at_most_50_html_backups(tmp_path: Path):
    for index in range(51):
        path = tmp_path / f"Bookmarks_{index:02}.html"
        path.write_text(str(index))
        os.utime(path, (index + 1, index + 1))

    prune_backups(tmp_path, 50)

    backups = sorted(tmp_path.glob("Bookmarks_*.html"))
    assert len(backups) == 50
    assert not (tmp_path / "Bookmarks_00.html").exists()


def test_force_and_close_browsers_are_mutually_exclusive():
    assert parse_args(["--close-browsers"]).close_browsers
    with pytest.raises(SystemExit):
        parse_args(["--force", "--close-browsers"])


def test_synchronize_backs_up_and_writes_both(tmp_path: Path):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    (chrome / "Bookmarks").write_text(json.dumps(data("https://chrome.test")))
    (edge / "Bookmarks").write_text(json.dumps(data("https://edge.test")))
    result = synchronize(chrome, edge, tmp_path / "backups", keep=10, write=True)
    assert result.merged_count == 2
    assert json.loads((chrome / "Bookmarks").read_text()) == json.loads((edge / "Bookmarks").read_text())
    assert len(list((tmp_path / "backups").glob("*.json"))) == 2
    assert result.html_path.exists()


def test_synchronize_applies_optional_deduplication_and_alphabetizing(tmp_path: Path):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    (chrome / "Bookmarks").write_text(
        json.dumps(data("https://zulu.test", "https://alpha.test/", "https://alpha.test"))
    )
    (edge / "Bookmarks").write_text(json.dumps(data("https://bravo.test")))

    result = synchronize(
        chrome,
        edge,
        tmp_path / "backups",
        write=True,
        deduplicate=True,
        alphabetize=True,
    )
    written = json.loads((chrome / "Bookmarks").read_text())
    bookmark_bar = written["roots"]["bookmark_bar"]["children"]
    imported = written["roots"]["other"]["children"][0]["children"]

    assert result.duplicates_removed == 1
    assert result.alphabetized
    assert [child["name"] for child in bookmark_bar] == ["https://alpha.test/", "https://zulu.test"]
    assert [child["name"] for child in imported] == ["https://bravo.test"]
    assert written == json.loads((edge / "Bookmarks").read_text())


def test_repeated_synchronization_preserves_unique_guids(tmp_path: Path):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    chrome_data = data("https://chrome.test")
    edge_data = data("https://edge.test")
    chrome_data["roots"]["bookmark_bar"]["guid"] = "00000000-0000-4000-a000-000000000002"
    chrome_data["roots"]["other"]["guid"] = "00000000-0000-4000-a000-000000000003"
    chrome_data["roots"]["bookmark_bar"]["children"][0]["guid"] = "11111111-1111-4111-8111-111111111111"
    edge_data["roots"]["bookmark_bar"]["guid"] = "00000000-0000-4000-a000-000000000002"
    edge_data["roots"]["other"]["guid"] = "00000000-0000-4000-a000-000000000003"
    edge_data["roots"]["bookmark_bar"]["children"][0]["guid"] = "22222222-2222-4222-8222-222222222222"
    (chrome / "Bookmarks").write_text(json.dumps(chrome_data))
    (edge / "Bookmarks").write_text(json.dumps(edge_data))

    synchronize(chrome, edge, tmp_path / "backups", write=True)
    first = json.loads((chrome / "Bookmarks").read_text())
    first_guids = [
        node["guid"]
        for root in first["roots"].values()
        for node in sync_module.walk_nodes(root)
        if node.get("guid")
    ]
    synchronize(chrome, edge, tmp_path / "backups", write=True)
    second = json.loads((chrome / "Bookmarks").read_text())
    second_guids = [
        node["guid"]
        for root in second["roots"].values()
        for node in sync_module.walk_nodes(root)
        if node.get("guid")
    ]

    assert second == json.loads((edge / "Bookmarks").read_text())
    assert second_guids == first_guids
    assert len(second_guids) == len(set(guid.casefold() for guid in second_guids))
    assert json.dumps(second).count("Imported from other browser") == 1


def test_synchronize_first_write_failure_changes_neither_browser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    chrome_path = chrome / "Bookmarks"
    edge_path = edge / "Bookmarks"
    chrome_original = json.dumps(data("https://chrome.test"))
    edge_original = json.dumps(data("https://edge.test"))
    chrome_path.write_text(chrome_original)
    edge_path.write_text(edge_original)
    real_replace = os.replace

    def fail_chrome_replace(source: str | Path, destination: str | Path) -> None:
        if Path(source).name.startswith("Bookmarks.pending.") and Path(destination) == chrome_path:
            raise OSError("simulated Chrome replacement failure")
        real_replace(source, destination)

    monkeypatch.setattr(sync_module.os, "replace", fail_chrome_replace)

    with pytest.raises(RuntimeError, match="Neither browser was changed"):
        synchronize(chrome, edge, tmp_path / "backups", write=True)

    assert chrome_path.read_text() == chrome_original
    assert edge_path.read_text() == edge_original
    assert not list(chrome.glob("Bookmarks.pending.*"))
    assert not list(edge.glob("Bookmarks.pending.*"))
    assert not list(chrome.glob("Bookmarks.rollback.*"))


def test_synchronize_second_write_failure_restores_chrome(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    chrome_path = chrome / "Bookmarks"
    edge_path = edge / "Bookmarks"
    chrome_original = json.dumps(data("https://chrome.test"))
    edge_original = json.dumps(data("https://edge.test"))
    chrome_path.write_text(chrome_original)
    edge_path.write_text(edge_original)
    real_replace = os.replace

    def fail_edge_replace(source: str | Path, destination: str | Path) -> None:
        if Path(source).name.startswith("Bookmarks.pending.") and Path(destination) == edge_path:
            raise OSError("simulated Edge replacement failure")
        real_replace(source, destination)

    monkeypatch.setattr(sync_module.os, "replace", fail_edge_replace)

    with pytest.raises(RuntimeError, match="Chrome was restored automatically"):
        synchronize(chrome, edge, tmp_path / "backups", write=True)

    assert chrome_path.read_text() == chrome_original
    assert edge_path.read_text() == edge_original
    assert not list(chrome.glob("Bookmarks.pending.*"))
    assert not list(edge.glob("Bookmarks.pending.*"))
    assert not list(chrome.glob("Bookmarks.rollback.*"))


def test_running_browser_processes_detects_chrome_and_edge(monkeypatch: pytest.MonkeyPatch):
    output = (
        '"chrome.exe","100","Console","1","10,000 K"\n'
        '"unrelated.exe","200","Console","1","10,000 K"\n'
        '"msedge.exe","300","Console","1","10,000 K"\n'
        '"chrome.exe","400","Console","1","10,000 K"\n'
    )
    completed = sync_module.subprocess.CompletedProcess([], 0, stdout=output, stderr="")
    monkeypatch.setattr(sync_module.subprocess, "run", lambda *args, **kwargs: completed)

    assert running_browser_processes() == ["chrome.exe", "msedge.exe"]


@pytest.mark.parametrize(
    "processes",
    [["chrome.exe"], ["msedge.exe"], ["chrome.exe", "msedge.exe"]],
    ids=["chrome-running", "edge-running", "both-running"],
)
def test_synchronize_blocks_running_browsers_after_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    processes: list[str],
):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    backup_dir = tmp_path / "backups"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    chrome_path = chrome / "Bookmarks"
    edge_path = edge / "Bookmarks"
    chrome_original = json.dumps(data("https://chrome.test"))
    edge_original = json.dumps(data("https://edge.test"))
    chrome_path.write_text(chrome_original)
    edge_path.write_text(edge_original)
    monkeypatch.setattr(sync_module, "running_browser_processes", lambda: processes)

    with pytest.raises(RuntimeError) as error:
        synchronize(chrome, edge, backup_dir, write=True)

    assert all(process in str(error.value) for process in processes)
    assert chrome_path.read_text() == chrome_original
    assert edge_path.read_text() == edge_original
    assert len(list(backup_dir.glob("*.json"))) == 2
    assert len(list(backup_dir.glob("*.html"))) == 1


def test_export_only_ignores_running_browsers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    chrome_path = chrome / "Bookmarks"
    edge_path = edge / "Bookmarks"
    chrome_original = json.dumps(data("https://chrome.test"))
    edge_original = json.dumps(data("https://edge.test"))
    chrome_path.write_text(chrome_original)
    edge_path.write_text(edge_original)

    def unexpected_detection() -> list[str]:
        raise AssertionError("Export-only mode must not check browser processes")

    monkeypatch.setattr(sync_module, "running_browser_processes", unexpected_detection)

    result = synchronize(chrome, edge, tmp_path / "backups", write=False, close_browsers=True)

    assert result.html_path.exists()
    assert chrome_path.read_text() == chrome_original
    assert edge_path.read_text() == edge_original


def test_rapid_exports_create_distinct_html_backups(tmp_path: Path):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    backup_dir = tmp_path / "backups"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    (chrome / "Bookmarks").write_text(json.dumps(data("https://chrome.test")))
    (edge / "Bookmarks").write_text(json.dumps(data("https://edge.test")))

    first = synchronize(chrome, edge, backup_dir, write=False)
    second = synchronize(chrome, edge, backup_dir, write=False)

    assert first.html_path != second.html_path
    assert len(list(backup_dir.glob("Bookmarks_*.html"))) == 2
    assert len(list(backup_dir.glob("*.json"))) == 4


def test_force_synchronizes_without_process_detection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    chrome_path = chrome / "Bookmarks"
    edge_path = edge / "Bookmarks"
    chrome_path.write_text(json.dumps(data("https://chrome.test")))
    edge_path.write_text(json.dumps(data("https://edge.test")))

    def unexpected_detection() -> list[str]:
        raise AssertionError("Forced synchronization must bypass process detection")

    monkeypatch.setattr(sync_module, "running_browser_processes", unexpected_detection)

    synchronize(chrome, edge, tmp_path / "backups", write=True, force=True)

    assert json.loads(chrome_path.read_text()) == json.loads(edge_path.read_text())


def test_close_browsers_terminates_detected_processes_then_synchronizes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    chrome_path = chrome / "Bookmarks"
    edge_path = edge / "Bookmarks"
    chrome_path.write_text(json.dumps(data("https://chrome.test")))
    edge_path.write_text(json.dumps(data("https://edge.test")))
    detections = iter([["chrome.exe", "msedge.exe"], []])
    closed: list[str] = []
    monkeypatch.setattr(sync_module, "running_browser_processes", lambda: next(detections))
    monkeypatch.setattr(sync_module, "close_browser_processes", lambda processes: closed.extend(processes))

    result = synchronize(chrome, edge, tmp_path / "backups", write=True, close_browsers=True)

    assert closed == ["chrome.exe", "msedge.exe"]
    assert result.closed_processes == ("chrome.exe", "msedge.exe")
    assert json.loads(chrome_path.read_text()) == json.loads(edge_path.read_text())


def test_close_browsers_blocks_when_processes_remain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    backup_dir = tmp_path / "backups"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    chrome_path = chrome / "Bookmarks"
    edge_path = edge / "Bookmarks"
    chrome_original = json.dumps(data("https://chrome.test"))
    edge_original = json.dumps(data("https://edge.test"))
    chrome_path.write_text(chrome_original)
    edge_path.write_text(edge_original)
    monkeypatch.setattr(sync_module, "running_browser_processes", lambda: ["chrome.exe"])
    monkeypatch.setattr(sync_module, "close_browser_processes", lambda processes: None)
    monkeypatch.setattr(sync_module, "wait_for_browsers_to_close", lambda: ["chrome.exe"])

    with pytest.raises(RuntimeError, match="Could not close these browser processes: chrome.exe"):
        synchronize(chrome, edge, backup_dir, write=True, close_browsers=True)

    assert chrome_path.read_text() == chrome_original
    assert edge_path.read_text() == edge_original
    assert len(list(backup_dir.glob("Bookmarks_*.html"))) == 1


def test_close_browser_processes_uses_forceful_taskkill(monkeypatch: pytest.MonkeyPatch):
    commands: list[list[str]] = []
    completed = sync_module.subprocess.CompletedProcess([], 0, stdout="", stderr="")

    def record_run(command, **kwargs):
        commands.append(command)
        return completed

    monkeypatch.setattr(sync_module.subprocess, "run", record_run)

    close_browser_processes(["chrome.exe", "msedge.exe", "notepad.exe"])

    assert commands == [
        ["taskkill", "/IM", "chrome.exe", "/T", "/F"],
        ["taskkill", "/IM", "msedge.exe", "/T", "/F"],
    ]


def test_cli_running_browser_error_returns_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    (chrome / "Bookmarks").write_text(json.dumps(data("https://chrome.test")))
    (edge / "Bookmarks").write_text(json.dumps(data("https://edge.test")))
    monkeypatch.setattr(sync_module, "running_browser_processes", lambda: ["chrome.exe"])

    exit_code = main(
        [
            "--sync",
            "--chrome-profile",
            str(chrome),
            "--edge-profile",
            str(edge),
            "--backup-dir",
            str(tmp_path / "backups"),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Error: Synchronization blocked" in captured.err
    assert "chrome.exe" in captured.err


def test_gui_error_shows_detected_browser_processes(monkeypatch: pytest.MonkeyPatch):
    class Value:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

    app = object.__new__(App)
    app.chrome = Value("Chrome profile")
    app.edge = Value("Edge profile")
    app.backups = Value("Backup directory")
    app.keep = Value(30)
    app.deduplicate = Value(False)
    app.alphabetize = Value(False)
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(sync_module.messagebox, "askyesno", lambda *args: True)
    monkeypatch.setattr(sync_module.messagebox, "showerror", lambda title, message: errors.append((title, message)))

    def blocked_sync(*args, **kwargs):
        raise RuntimeError("Synchronization blocked: chrome.exe, msedge.exe")

    monkeypatch.setattr(sync_module, "synchronize", blocked_sync)

    App._run(app, True)

    assert errors == [(sync_module.APP_NAME, "Synchronization blocked: chrome.exe, msedge.exe")]

