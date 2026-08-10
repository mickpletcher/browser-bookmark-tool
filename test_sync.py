import json
import os
import shutil
import sqlite3
import subprocess
import uuid
from pathlib import Path

import pytest

import browser_bookmark_sync as sync_module
from browser_bookmark_sync import (
    App,
    AutomationRunLock,
    ProfileMapping,
    alphabetize_bookmarks,
    automation_readiness,
    catalog_backup_sets,
    close_browser_processes,
    compare_backup_sets,
    deduplicate_bookmarks,
    discover_firefox_profiles,
    export_html,
    iter_urls,
    load_automation_config,
    load_profile_mappings,
    main,
    merge_bookmarks,
    normalized_url,
    parse_args,
    prepare_merged_data,
    prune_backups,
    read_firefox_bookmarks,
    restore_json_backup,
    run_automation,
    running_browser_processes,
    save_profile_mapping,
    synchronize,
    transactional_firefox_write,
    validate_backup_manifest,
    validate_unique_guids,
    verify_json_backup,
    write_task_scheduler_script,
)


def data(*urls: str) -> dict:
    children = [{"type": "url", "id": str(i + 10), "name": url, "url": url} for i, url in enumerate(urls)]
    return {"roots": {"bookmark_bar": {"type": "folder", "id": "1", "name": "Bookmarks bar", "children": children}, "other": {"type": "folder", "id": "2", "name": "Other bookmarks", "children": []}}, "version": 1, "checksum": "old"}


def firefox_profile(tmp_path: Path, *urls: str) -> Path:
    profile = tmp_path / "Firefox" / "Profiles" / "test.default-release"
    profile.mkdir(parents=True)
    connection = sqlite3.connect(profile / "places.sqlite")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript(
        """
        CREATE TABLE moz_places (
            id INTEGER PRIMARY KEY,
            url TEXT UNIQUE,
            url_hash INTEGER NOT NULL,
            title TEXT,
            rev_host TEXT NOT NULL DEFAULT '',
            hidden INTEGER NOT NULL DEFAULT 0,
            typed INTEGER NOT NULL DEFAULT 0,
            frecency INTEGER NOT NULL DEFAULT -1,
            guid TEXT UNIQUE NOT NULL,
            foreign_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE moz_bookmarks (
            id INTEGER PRIMARY KEY,
            type INTEGER NOT NULL,
            fk INTEGER,
            parent INTEGER NOT NULL,
            position INTEGER NOT NULL,
            title TEXT,
            dateAdded INTEGER NOT NULL DEFAULT 0,
            lastModified INTEGER NOT NULL DEFAULT 0,
            guid TEXT UNIQUE NOT NULL,
            syncStatus INTEGER NOT NULL DEFAULT 0,
            syncChangeCounter INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE moz_keywords (place_id INTEGER);
        INSERT INTO moz_bookmarks (id, type, parent, position, title, guid)
        VALUES
            (1, 2, 0, 0, '', 'root________'),
            (2, 2, 1, 0, 'Bookmarks Menu', 'menu________'),
            (3, 2, 1, 1, 'Bookmarks Toolbar', 'toolbar_____'),
            (4, 2, 1, 2, 'Other Bookmarks', 'unfiled_____'),
            (5, 2, 1, 3, 'Mobile Bookmarks', 'mobile______');
        """
    )
    for index, url in enumerate(urls, start=1):
        place_id = 100 + index
        connection.execute(
            "INSERT INTO moz_places (id, url, url_hash, title, rev_host, guid, foreign_count) VALUES (?, ?, ?, ?, '', ?, 1)",
            (place_id, url, sync_module.places_url_hash(url), url, f"placeguid{index:03d}"),
        )
        connection.execute(
            "INSERT INTO moz_bookmarks (id, type, fk, parent, position, title, guid) VALUES (?, 1, ?, 3, ?, ?, ?)",
            (200 + index, place_id, index - 1, url, f"bookmark{index:03d}"),
        )
    connection.commit()
    connection.close()
    return profile


@pytest.fixture(autouse=True)
def no_running_browsers(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sync_module, "running_browser_processes", lambda: [])
    monkeypatch.setattr(sync_module, "running_firefox_processes", lambda: [])


def test_merge_deduplicates_and_retains_unique_links():
    merged, added = merge_bookmarks(
        data("https://a.test/", "https://b.test"),
        data("https://a.test", "https://c.test"),
        duplicate_mode="aggressive",
    )
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


def test_firefox_profile_discovery_uses_explicit_profiles_ini(tmp_path: Path):
    source_profile = firefox_profile(tmp_path / "source", "https://firefox.test")
    firefox_root = tmp_path / "Mozilla" / "Firefox"
    relative_profile = firefox_root / "Profiles" / "default-release"
    absolute_profile = tmp_path / "absolute-profile"
    shutil.copytree(source_profile, relative_profile)
    shutil.copytree(source_profile, absolute_profile)
    profiles_ini = firefox_root / "profiles.ini"
    profiles_ini.write_text(
        "[Profile0]\nName=Default\nIsRelative=1\nPath=Profiles/default-release\nDefault=1\n\n"
        f"[Profile1]\nName=Absolute\nIsRelative=0\nPath={absolute_profile.as_posix()}\n"
    )

    assert discover_firefox_profiles(profiles_ini) == [relative_profile.resolve(), absolute_profile.resolve()]


def test_firefox_import_uses_selected_duplicate_mode(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    profile = firefox_profile(tmp_path, "https://EXAMPLE.test/Path/")
    firefox = read_firefox_bookmarks(profile)

    conservative, conservative_preview = prepare_merged_data(
        data("https://example.test/path"),
        data(),
        duplicate_mode="conservative",
        firefox=firefox,
    )
    aggressive, aggressive_preview = prepare_merged_data(
        data("https://example.test/path"),
        data(),
        duplicate_mode="aggressive",
        firefox=firefox,
    )

    assert len([node for root in conservative["roots"].values() for node in iter_urls(root)]) == 2
    assert len([node for root in aggressive["roots"].values() for node in iter_urls(root)]) == 1
    assert conservative_preview.firefox_count == aggressive_preview.firefox_count == 1
    assert conservative_preview.firefox_enabled and aggressive_preview.firefox_enabled

    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    (chrome / "Bookmarks").write_text(json.dumps(data("https://chrome.test")))
    (edge / "Bookmarks").write_text(json.dumps(data("https://edge.test")))
    assert main(
        [
            "--dry-run",
            "--chrome-profile",
            str(chrome),
            "--edge-profile",
            str(edge),
            "--firefox-profile",
            str(profile),
        ]
    ) == 0
    assert "Firefox bookmarks: 1" in capsys.readouterr().out


def test_firefox_can_be_disabled_without_entering_firefox_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    (chrome / "Bookmarks").write_text(json.dumps(data("https://chrome.test")))
    (edge / "Bookmarks").write_text(json.dumps(data("https://edge.test")))
    monkeypatch.setattr(sync_module, "read_firefox_bookmarks", lambda _profile: pytest.fail("Firefox was read"))

    result = synchronize(chrome, edge, tmp_path / "backups", write=False)

    assert result.firefox_count == 0
    assert not list((tmp_path / "backups").glob("Firefox_*.sqlite"))
    assert "firefox_count" not in json.loads(result.manifest_path.read_text())["summary"]
    assert "firefox_count" not in result.log_path.read_text()
    assert result.preview.render() == prepare_merged_data(data("https://chrome.test"), data("https://edge.test"))[1].render()


def test_firefox_export_backs_up_before_write_and_adds_missing_bookmarks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    (chrome / "Bookmarks").write_text(json.dumps(data("https://chrome.test")))
    (edge / "Bookmarks").write_text(json.dumps(data("https://edge.test")))
    firefox = firefox_profile(tmp_path, "https://firefox.test")
    backup_dir = tmp_path / "backups"
    original_checkpoint = sync_module.checkpoint_firefox_database

    def assert_backup_precedes_write(path: Path):
        firefox_backups = list(backup_dir.glob("Firefox_*.sqlite"))
        manifests = list(backup_dir.glob("Manifest_*.json"))
        assert len(firefox_backups) == len(manifests) == 1
        validate_backup_manifest(manifests[0])
        assert firefox_backups[0].name in {
            entry["name"] for entry in json.loads(manifests[0].read_text())["files"]
        }
        original_checkpoint(path)

    monkeypatch.setattr(sync_module, "checkpoint_firefox_database", assert_backup_precedes_write)

    result = synchronize(
        chrome,
        edge,
        backup_dir,
        write=True,
        firefox_profile=firefox,
        firefox_export=True,
    )

    assert result.firefox_added == 2
    assert {node["url"] for root in read_firefox_bookmarks(firefox)["roots"].values() for node in iter_urls(root)} == {
        "https://chrome.test",
        "https://edge.test",
        "https://firefox.test",
    }
    firefox_backups = list(backup_dir.glob("Firefox_*.sqlite"))
    assert len(firefox_backups) == 1
    manifest = json.loads(result.manifest_path.read_text())
    assert firefox_backups[0].name in {entry["name"] for entry in manifest["files"]}
    validate_backup_manifest(result.manifest_path)
    assert not list(firefox.glob("places.pending.*"))


def test_firefox_running_blocks_export_after_backups(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    (chrome / "Bookmarks").write_text(json.dumps(data("https://chrome.test")))
    (edge / "Bookmarks").write_text(json.dumps(data("https://edge.test")))
    firefox = firefox_profile(tmp_path, "https://firefox.test")
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(sync_module, "running_firefox_processes", lambda: ["firefox.exe"])

    with pytest.raises(RuntimeError, match="firefox.exe"):
        synchronize(
            chrome,
            edge,
            backup_dir,
            write=True,
            firefox_profile=firefox,
            firefox_export=True,
        )

    assert len(list(backup_dir.glob("Firefox_*.sqlite"))) == 1
    assert len(list(backup_dir.glob("Manifest_*.json"))) == 1


def test_firefox_replacement_failure_restores_chrome_and_edge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    chrome_file = chrome / "Bookmarks"
    edge_file = edge / "Bookmarks"
    chrome_original = data("https://chrome.test")
    edge_original = data("https://edge.test")
    chrome_file.write_text(json.dumps(chrome_original))
    edge_file.write_text(json.dumps(edge_original))
    firefox = firefox_profile(tmp_path, "https://firefox.test")
    firefox_file = firefox / "places.sqlite"
    firefox_staged = firefox / "places.pending.sqlite"
    shutil.copy2(firefox_file, firefox_staged)
    original_replace = sync_module.os.replace

    def fail_firefox(source: Path | str, destination: Path | str):
        if Path(destination) == firefox_file:
            raise OSError("simulated Firefox replacement failure")
        return original_replace(source, destination)

    monkeypatch.setattr(sync_module.os, "replace", fail_firefox)

    with pytest.raises(RuntimeError, match="Chrome and Edge were restored automatically"):
        transactional_firefox_write(chrome_file, edge_file, firefox_file, data("https://merged.test"), firefox_staged)

    assert json.loads(chrome_file.read_text()) == chrome_original
    assert json.loads(edge_file.read_text()) == edge_original


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

    removed = deduplicate_bookmarks(bookmarks, mode="aggressive")
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


def test_conservative_url_matching_preserves_potentially_distinct_urls():
    assert normalized_url(" HTTPS://Example.Test/Path?Value=One ") == "https://example.test/Path?Value=One"
    assert normalized_url("https://example.test/Path") != normalized_url("https://example.test/path")
    assert normalized_url("https://example.test/") != normalized_url("https://example.test")
    assert normalized_url("https://example.test/Path/", mode="aggressive") == normalized_url(
        "https://example.test/path",
        mode="aggressive",
    )


def test_sync_and_dry_run_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        parse_args(["--sync", "--dry-run"])


def test_backup_retention_rejects_values_above_50():
    with pytest.raises(SystemExit):
        parse_args(["--keep", "51"])


def test_backup_retention_keeps_at_most_50_html_backups(tmp_path: Path):
    for index in range(51):
        path = tmp_path / f"Bookmarks_2026-08-07_12-00-00_{index:06}.html"
        path.write_text(str(index))
        os.utime(path, (index + 1, index + 1))

    prune_backups(tmp_path, 50)

    backups = sorted(tmp_path.glob("Bookmarks_*.html"))
    assert len(backups) == 50
    assert not (tmp_path / "Bookmarks_2026-08-07_12-00-00_000000.html").exists()


def test_backup_retention_uses_filename_timestamp_instead_of_file_mtime(tmp_path: Path):
    older = tmp_path / "Chrome_2026-08-07_12-00-00_000001.json"
    newer = tmp_path / "Chrome_2026-08-07_12-00-00_000002.json"
    older.write_text("older")
    newer.write_text("newer")
    os.utime(older, (200, 200))
    os.utime(newer, (100, 100))

    prune_backups(tmp_path, 1)

    assert not older.exists()
    assert newer.exists()


def test_backup_retention_ignores_unrecognized_files_and_directories(tmp_path: Path):
    unrelated = [
        tmp_path / "Chrome_notes.json",
        tmp_path / "Edge_backup.json",
        tmp_path / "Bookmarks_readme.html",
    ]
    for path in unrelated:
        path.write_text("keep")
    directory = tmp_path / "Chrome_2026-08-07_12-00-00_000001.json"
    directory.mkdir()

    prune_backups(tmp_path, 1)

    assert all(path.exists() for path in unrelated)
    assert directory.is_dir()


def test_backup_retention_prunes_old_manifests(tmp_path: Path):
    older = tmp_path / "Manifest_2026-08-07_12-00-00_000001.json"
    newer = tmp_path / "Manifest_2026-08-07_12-00-00_000002.json"
    older.write_text("{}")
    newer.write_text("{}")

    prune_backups(tmp_path, 1)

    assert not older.exists()
    assert newer.exists()


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
    assert len(list((tmp_path / "backups").glob("Chrome_*.json"))) == 1
    assert len(list((tmp_path / "backups").glob("Edge_*.json"))) == 1
    assert result.manifest_path.exists()
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
        duplicate_mode="aggressive",
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
    assert len(list(backup_dir.glob("Chrome_*.json"))) == 1
    assert len(list(backup_dir.glob("Edge_*.json"))) == 1
    assert len(list(backup_dir.glob("Manifest_*.json"))) == 1
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
    assert len(list(backup_dir.glob("Chrome_*.json"))) == 2
    assert len(list(backup_dir.glob("Edge_*.json"))) == 2
    assert len(list(backup_dir.glob("Manifest_*.json"))) == 2


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


def test_edge_wins_uses_edge_as_primary_structure():
    chrome = data("https://chrome.test")
    edge = data("https://edge.test")

    merged, preview = prepare_merged_data(chrome, edge, merge_strategy="edge-wins")
    bookmark_bar_urls = [node["url"] for node in iter_urls(merged["roots"]["bookmark_bar"])]
    imported_urls = [node["url"] for node in iter_urls(merged["roots"]["other"])]

    assert bookmark_bar_urls == ["https://edge.test"]
    assert imported_urls == ["https://chrome.test"]
    assert merged["roots"]["other"]["children"][0]["name"] == "Imported from Chrome"
    assert preview.merge_strategy == "edge-wins"


def test_merge_folders_reports_no_new_wrapper_folder():
    chrome = data()
    edge = data()
    chrome["roots"]["bookmark_bar"]["children"] = [
        {
            "type": "folder",
            "id": "10",
            "name": "Shared",
            "children": [{"type": "url", "id": "11", "name": "Chrome", "url": "https://chrome.test"}],
        }
    ]
    edge["roots"]["bookmark_bar"]["children"] = [
        {
            "type": "folder",
            "id": "20",
            "name": "shared",
            "children": [{"type": "url", "id": "21", "name": "Edge", "url": "https://edge.test"}],
        }
    ]

    merged, preview = prepare_merged_data(chrome, edge, merge_strategy="merge-folders")
    shared = merged["roots"]["bookmark_bar"]["children"][0]

    assert [node["url"] for node in iter_urls(shared)] == ["https://chrome.test", "https://edge.test"]
    assert not merged["roots"]["other"]["children"]
    assert preview.folders_added == 0


def test_cli_dry_run_does_not_create_backups_or_write_profiles(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
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

    exit_code = main(
        [
            "--dry-run",
            "--chrome-profile",
            str(chrome),
            "--edge-profile",
            str(edge),
            "--backup-dir",
            str(backup_dir),
        ]
    )

    assert exit_code == 0
    assert "Strategy: chrome-wins" in capsys.readouterr().out
    assert chrome_path.read_text() == chrome_original
    assert edge_path.read_text() == edge_original
    assert not backup_dir.exists()


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
    app.duplicate_mode = Value("conservative")
    app.merge_strategy = Value("chrome-wins")
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(sync_module.messagebox, "askyesno", lambda *args: True)
    monkeypatch.setattr(sync_module.messagebox, "showerror", lambda title, message: errors.append((title, message)))

    def blocked_sync(*args, **kwargs):
        raise RuntimeError("Synchronization blocked: chrome.exe, msedge.exe")

    monkeypatch.setattr(sync_module, "synchronize", blocked_sync)

    App._run(app, True)

    assert errors == [(sync_module.APP_NAME, "Synchronization blocked: chrome.exe, msedge.exe")]


def test_conservative_url_matching_preserves_case_and_trailing_slash():
    assert normalized_url("HTTPS://Example.COM/Reports/Q1") == "https://example.com/Reports/Q1"
    assert normalized_url("https://example.com/reports/q1") != normalized_url("https://example.com/Reports/Q1")
    assert normalized_url("https://example.com/") != normalized_url("https://example.com")


def test_aggressive_url_matching_is_explicit():
    assert normalized_url("HTTPS://Example.COM/Reports/Q1/", "aggressive") == normalized_url(
        "https://example.com/reports/q1", "aggressive"
    )


@pytest.mark.parametrize("strategy", sync_module.MERGE_STRATEGIES)
def test_all_merge_strategies_produce_a_union(strategy: str):
    merged, preview = prepare_merged_data(
        data("https://chrome.test"),
        data("https://edge.test"),
        merge_strategy=strategy,
    )
    urls = {node["url"] for root in merged["roots"].values() for node in iter_urls(root)}

    assert urls == {"https://chrome.test", "https://edge.test"}
    assert preview.merge_strategy == strategy
    assert preview.merged_count == 2


def test_merge_folders_combines_matching_folder_names():
    chrome = data()
    edge = data()
    chrome["roots"]["bookmark_bar"]["children"] = [
        {"type": "folder", "id": "10", "name": "Shared", "children": [{"type": "url", "id": "11", "name": "A", "url": "https://a.test"}]}
    ]
    edge["roots"]["bookmark_bar"]["children"] = [
        {"type": "folder", "id": "20", "name": "shared", "children": [{"type": "url", "id": "21", "name": "B", "url": "https://b.test"}]}
    ]

    merged, _ = prepare_merged_data(chrome, edge, merge_strategy="merge-folders")
    folders = merged["roots"]["bookmark_bar"]["children"]

    assert len(folders) == 1
    assert {node["url"] for node in iter_urls(folders[0])} == {"https://a.test", "https://b.test"}


def test_dry_run_creates_no_backup_or_write(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
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

    exit_code = main(["--dry-run", "--chrome-profile", str(chrome), "--edge-profile", str(edge), "--backup-dir", str(tmp_path / "backups")])

    assert exit_code == 0
    assert "Final bookmark count: 2" in capsys.readouterr().out
    assert not (tmp_path / "backups").exists()
    assert chrome_path.read_text() == chrome_original
    assert edge_path.read_text() == edge_original


def test_manifest_validates_and_detects_tampering(tmp_path: Path):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    (chrome / "Bookmarks").write_text(json.dumps(data("https://chrome.test")))
    (edge / "Bookmarks").write_text(json.dumps(data("https://edge.test")))

    result = synchronize(chrome, edge, tmp_path / "backups", write=False)
    validate_backup_manifest(result.manifest_path)
    result.html_path.write_text("tampered")

    with pytest.raises(RuntimeError, match="integrity validation failed"):
        validate_backup_manifest(result.manifest_path)

    result.manifest_path.write_text(
        json.dumps({"files": [{"name": "../outside.json", "size": 0, "sha256": "0" * 64}]})
    )
    with pytest.raises(RuntimeError, match="invalid file entry"):
        validate_backup_manifest(result.manifest_path)


def verification_files(tmp_path: Path, document: dict | str) -> tuple[Path, Path]:
    stamp = "2026-08-08_12-00-00_000001"
    backup = tmp_path / f"Chrome_{stamp}.json"
    backup.write_text(document if isinstance(document, str) else json.dumps(document))
    manifest = tmp_path / f"Manifest_{stamp}.json"
    sync_module.write_backup_manifest(manifest, [backup])
    return backup, manifest


def catalog_files(
    directory: Path,
    stamp: str,
    chrome_urls: tuple[str, ...] = ("https://chrome.test",),
    edge_urls: tuple[str, ...] = ("https://edge.test",),
    firefox: Path | None = None,
) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "Chrome": directory / f"Chrome_{stamp}.json",
        "Edge": directory / f"Edge_{stamp}.json",
        "Bookmarks": directory / f"Bookmarks_{stamp}.html",
    }
    files["Chrome"].write_text(json.dumps(data(*chrome_urls)))
    files["Edge"].write_text(json.dumps(data(*edge_urls)))
    files["Bookmarks"].write_text("<!DOCTYPE NETSCAPE-Bookmark-file-1>")
    if firefox:
        files["Firefox"] = directory / f"Firefox_{stamp}.sqlite"
        shutil.copy2(firefox / "places.sqlite", files["Firefox"])
    files["Manifest"] = sync_module.write_backup_manifest(
        directory / f"Manifest_{stamp}.json",
        [path for name, path in files.items() if name != "Manifest"],
    )
    return files


def test_backup_catalog_groups_complete_sets_and_compares_verified_counts(tmp_path: Path):
    older_stamp = "2026-08-08_12-00-00_000001"
    newer_stamp = "2026-08-08_13-00-00_000001"
    catalog_files(tmp_path, older_stamp)
    firefox = firefox_profile(tmp_path / "firefox-source", "https://firefox.test")
    catalog_files(
        tmp_path,
        newer_stamp,
        chrome_urls=("https://chrome.test", "https://new.test"),
        firefox=firefox,
    )
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}

    catalog = catalog_backup_sets(tmp_path)
    comparison = compare_backup_sets(catalog, older_stamp, newer_stamp)

    assert [item.stamp for item in catalog.sets] == [newer_stamp, older_stamp]
    assert all(item.complete and item.valid for item in catalog.sets)
    assert [(item.browser, item.bookmark_count, item.folder_count) for item in catalog.sets[0].artifacts] == [
        ("Chrome", 2, 2),
        ("Edge", 1, 2),
        ("Firefox", 1, 3),
    ]
    rendered = catalog.render()
    assert "change +1 bookmarks, +0 folders" in rendered
    assert "https://" not in rendered
    assert "Chrome: bookmarks 1 to 2 (+1)" in comparison.render()
    assert before == {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}


def test_backup_catalog_flags_missing_and_extra_members(tmp_path: Path):
    missing_stamp = "2026-08-08_12-00-00_000001"
    extra_stamp = "2026-08-08_13-00-00_000001"
    missing = catalog_files(tmp_path, missing_stamp)
    missing["Edge"].unlink()
    catalog_files(tmp_path, extra_stamp)
    firefox = firefox_profile(tmp_path / "extra-firefox", "https://firefox.test")
    shutil.copy2(firefox / "places.sqlite", tmp_path / f"Firefox_{extra_stamp}.sqlite")

    catalog = catalog_backup_sets(tmp_path)
    by_stamp = {item.stamp: item for item in catalog.sets}

    assert by_stamp[missing_stamp].missing_members == ("Edge",)
    assert not by_stamp[missing_stamp].complete
    assert by_stamp[extra_stamp].extra_members == ("Firefox",)
    assert not by_stamp[extra_stamp].complete
    assert catalog.filtered("incomplete") == catalog.sets
    with pytest.raises(RuntimeError, match="complete, valid"):
        compare_backup_sets(catalog, missing_stamp, extra_stamp)


def test_backup_catalog_filters_manifest_mismatch_as_invalid(tmp_path: Path):
    stamp = "2026-08-08_12-00-00_000001"
    files = catalog_files(tmp_path, stamp)
    files["Chrome"].write_text(json.dumps(data("https://tampered.test")))

    catalog = catalog_backup_sets(tmp_path)

    assert catalog.sets[0].complete
    assert not catalog.sets[0].valid
    assert catalog.sets[0].manifest_status == "invalid"
    assert catalog.filtered("invalid") == catalog.sets
    assert catalog.filtered("valid") == ()


def test_backup_catalog_ignores_unrelated_files_and_directories(tmp_path: Path):
    stamp = "2026-08-08_12-00-00_000001"
    catalog_files(tmp_path, stamp)
    (tmp_path / "Chrome_backup.json").write_text("private")
    (tmp_path / "notes.txt").write_text("private")
    (tmp_path / f"Edge_{stamp}.sqlite").write_text("not a generated member")
    (tmp_path / "Manifest_2026-08-08_14-00-00_000001.json").mkdir()

    catalog = catalog_backup_sets(tmp_path)

    assert len(catalog.sets) == 1
    assert catalog.sets[0].complete
    assert catalog.sets[0].valid


def test_cli_backup_catalog_filters_and_compares(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    older_stamp = "2026-08-08_12-00-00_000001"
    newer_stamp = "2026-08-08_13-00-00_000001"
    catalog_files(tmp_path, older_stamp)
    catalog_files(tmp_path, newer_stamp, chrome_urls=("https://one.test", "https://two.test"))

    assert main(["--catalog-backups", "--catalog-filter", "complete", "--backup-dir", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "Backup catalog: 2 set(s), filter complete" in output
    assert "No live browser files or backup files were changed" in output

    assert main(["--compare-backups", older_stamp, newer_stamp, "--backup-dir", str(tmp_path)]) == 0
    assert "Chrome: bookmarks 1 to 2 (+1)" in capsys.readouterr().out

    assert main(["--catalog-filter", "valid"]) == 1
    assert "--catalog-filter requires --catalog-backups" in capsys.readouterr().err


def test_gui_backup_catalog_uses_selected_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    class Value:
        def __init__(self, value: str):
            self.value = value

        def get(self):
            return self.value

        def set(self, value: str):
            self.value = value

    catalog_files(tmp_path, "2026-08-08_12-00-00_000001")
    app = object.__new__(App)
    app.backups = Value(str(tmp_path))
    app.catalog_filter = Value("valid")
    app.status = Value("")
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(sync_module.messagebox, "showinfo", lambda title, message: messages.append((title, message)))

    App._catalog_backups(app)

    assert app.status.get() == "Cataloged 1 backup set(s) with the valid filter. No files were changed."
    assert messages[0][0] == f"{sync_module.APP_NAME} Backup Catalog"
    assert "filter valid" in messages[0][1]


def test_verify_json_backup_is_non_destructive_and_reports_counts(tmp_path: Path):
    backup, manifest = verification_files(tmp_path, data("https://verified.test"))
    live_profile = tmp_path / "Live" / "Default"
    live_profile.mkdir(parents=True)
    live_file = live_profile / "Bookmarks"
    live_content = json.dumps(data("https://live.test"))
    live_file.write_text(live_content)

    report = verify_json_backup(backup)

    assert report.backup_path == backup
    assert report.manifest_path == manifest
    assert report.bookmark_count == 1
    assert report.folder_count == 2
    assert live_file.read_text() == live_content
    assert "No live browser files were changed" in report.render()


def test_verify_json_backup_rejects_invalid_json(tmp_path: Path):
    backup, _ = verification_files(tmp_path, "{invalid")

    with pytest.raises(RuntimeError, match="not valid JSON"):
        verify_json_backup(backup)


def test_verify_json_backup_rejects_invalid_chromium_schema(tmp_path: Path):
    backup, _ = verification_files(
        tmp_path,
        {"roots": {"bookmark_bar": {"type": "folder", "id": "1", "name": "Bookmarks bar", "children": []}}},
    )

    with pytest.raises(RuntimeError, match="missing required Chromium root"):
        verify_json_backup(backup)


def test_verify_json_backup_rejects_duplicate_guids(tmp_path: Path):
    document = data("https://one.test", "https://two.test")
    for child in document["roots"]["bookmark_bar"]["children"]:
        child["guid"] = "11111111-1111-4111-8111-111111111111"
    backup, _ = verification_files(tmp_path, document)

    with pytest.raises(RuntimeError, match="duplicate GUID values"):
        verify_json_backup(backup)


def test_verify_json_backup_rejects_manifest_mismatch(tmp_path: Path):
    backup, _ = verification_files(tmp_path, data("https://original.test"))
    backup.write_text(json.dumps(data("https://changed.test")))

    with pytest.raises(RuntimeError, match="integrity validation failed"):
        verify_json_backup(backup)


def test_verify_json_backup_checks_selected_file_against_explicit_manifest(tmp_path: Path):
    manifest_dir = tmp_path / "manifest-set"
    manifest_dir.mkdir()
    original, manifest = verification_files(manifest_dir, data("https://original.test"))
    selected_dir = tmp_path / "selected"
    selected_dir.mkdir()
    selected = selected_dir / original.name
    selected.write_text(json.dumps(data("https://different.test")))

    with pytest.raises(RuntimeError, match="integrity validation failed"):
        verify_json_backup(selected, manifest)


def test_cli_verify_backup_prints_concise_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    backup, manifest = verification_files(tmp_path, data("https://verified.test"))

    exit_code = main(["--verify-backup", str(backup)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert "Backup verification passed" in captured.out
    assert "Bookmarks: 1" in captured.out
    assert "Folders: 2" in captured.out
    assert "No live browser files were changed" in captured.out

    assert main(["--verify-manifest", str(manifest)]) == 1
    assert "--verify-manifest requires --verify-backup" in capsys.readouterr().err


def test_gui_verify_backup_shows_concise_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    class Value:
        def __init__(self, value: str):
            self.value = value

        def get(self):
            return self.value

        def set(self, value: str):
            self.value = value

    backup, _ = verification_files(tmp_path, data("https://verified.test"))
    app = object.__new__(App)
    app.backups = Value(str(tmp_path))
    app.status = Value("")
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(sync_module.filedialog, "askopenfilename", lambda **_kwargs: str(backup))
    monkeypatch.setattr(sync_module.messagebox, "showinfo", lambda title, message: messages.append((title, message)))

    App._verify_backup(app)

    assert app.status.get() == "Verified 1 bookmarks and 2 folders. No live browser files were changed."
    assert messages == [(f"{sync_module.APP_NAME} Verification", sync_module.verify_json_backup(backup).render())]


def test_operation_log_does_not_include_bookmark_urls(tmp_path: Path):
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    (chrome / "Bookmarks").write_text(json.dumps(data("https://private.example/token=secret")))
    (edge / "Bookmarks").write_text(json.dumps(data("https://edge.test")))

    result = synchronize(chrome, edge, tmp_path / "backups", write=False, verbose=True)
    log = result.log_path.read_text()

    assert "backup_export_complete" in log
    assert "private.example" not in log
    assert "secret" not in log


def test_profile_mapping_round_trip(tmp_path: Path):
    path = tmp_path / "profile-mappings.json"
    save_profile_mapping(
        path,
        ProfileMapping(
            "Personal",
            Path("C:/Chrome"),
            Path("C:/Edge"),
            Path("D:/Backups"),
            Path("C:/Firefox"),
        ),
    )
    save_profile_mapping(path, ProfileMapping("Work", Path("W:/Chrome"), Path("W:/Edge"), Path("W:/Backups")))

    mappings = load_profile_mappings(path)

    assert sorted(mappings) == ["Personal", "Work"]
    assert mappings["Personal"].backup_dir == Path("D:/Backups")
    assert mappings["Personal"].firefox_profile == Path("C:/Firefox")
    assert mappings["Work"].firefox_profile is None


def test_profile_mapping_rejects_invalid_document_shape(tmp_path: Path):
    path = tmp_path / "profile-mappings.json"
    path.write_text("[]")

    with pytest.raises(RuntimeError, match="must contain a mappings list"):
        load_profile_mappings(path)


def test_restore_json_backup_preserves_current_file(tmp_path: Path):
    profile = tmp_path / "Chrome" / "Default"
    profile.mkdir(parents=True)
    current = data("https://current.test")
    replacement = data("https://restored.test")
    (profile / "Bookmarks").write_text(json.dumps(current))
    backup = tmp_path / "Chrome_backup.json"
    backup.write_text(json.dumps(replacement))

    preserved = restore_json_backup(backup, profile, "Chrome", tmp_path / "recovery")

    assert json.loads((profile / "Bookmarks").read_text()) == replacement
    assert json.loads(preserved.read_text()) == current


def test_restore_rejects_html_backup(tmp_path: Path):
    html_backup = tmp_path / "Bookmarks_backup.html"
    html_backup.write_text("<html></html>")

    with pytest.raises(RuntimeError, match="requires a raw JSON"):
        restore_json_backup(html_backup, tmp_path, "Chrome", tmp_path)


def test_task_scheduler_script_defaults_to_backup_only(tmp_path: Path):
    destination = tmp_path / "register-task.ps1"
    write_task_scheduler_script(
        destination,
        Path("C:/Chrome Profile"),
        Path("C:/Edge Profile"),
        Path("D:/Backups"),
        "Bookmark Backup",
        "03:30",
    )
    script = destination.read_text()

    assert "Register-ScheduledTask" in script
    assert "--sync" not in script
    assert "03:30" in script


def test_task_scheduler_sync_requires_explicit_opt_in(tmp_path: Path):
    destination = tmp_path / "register-sync-task.ps1"
    write_task_scheduler_script(
        destination,
        Path("C:/Chrome"),
        Path("C:/Edge"),
        Path("D:/Backups"),
        "Bookmark Sync",
        "04:00",
        synchronize_task=True,
    )

    assert "--sync" in destination.read_text()


def test_task_scheduler_uses_standalone_executable_when_frozen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    destination = tmp_path / "standalone-task.ps1"
    monkeypatch.setattr(sync_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(sync_module.sys, "executable", "C:/Tools/BrowserBookmarkTool.exe")

    write_task_scheduler_script(
        destination,
        Path("C:/Chrome"),
        Path("C:/Edge"),
        Path("D:/Backups"),
        "Bookmark Backup",
        "02:00",
    )
    script = destination.read_text()

    assert "C:/Tools/BrowserBookmarkTool.exe" in script
    assert "browser_bookmark_sync" not in script


def test_task_scheduler_rejects_invalid_time(tmp_path: Path):
    with pytest.raises(RuntimeError, match="24-hour HH:MM"):
        write_task_scheduler_script(
            tmp_path / "task.ps1",
            Path("C:/Chrome"),
            Path("C:/Edge"),
            Path("D:/Backups"),
            "Bookmark Backup",
            "25:99",
        )


def test_cli_dry_run_processes_multiple_named_mappings(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    mapping_file = tmp_path / "profile-mappings.json"
    for name in ("Personal", "Work"):
        chrome = tmp_path / name / "Chrome"
        edge = tmp_path / name / "Edge"
        chrome.mkdir(parents=True)
        edge.mkdir(parents=True)
        (chrome / "Bookmarks").write_text(json.dumps(data(f"https://{name.casefold()}-chrome.test")))
        (edge / "Bookmarks").write_text(json.dumps(data(f"https://{name.casefold()}-edge.test")))
        save_profile_mapping(mapping_file, ProfileMapping(name, chrome, edge, tmp_path / name / "Backups"))

    exit_code = main(["--dry-run", "--profile-map", str(mapping_file)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "[Personal]" in output
    assert "[Work]" in output
    assert output.count("Final bookmark count: 2") == 2


def automation_files(
    tmp_path: Path,
    operation: str = "backup",
    browser_behavior: str = "block",
) -> tuple[Path, Path, Path, Path, Path]:
    chrome = tmp_path / "Chrome" / "Default"
    edge = tmp_path / "Edge" / "Default"
    chrome.mkdir(parents=True)
    edge.mkdir(parents=True)
    (chrome / "Bookmarks").write_text(json.dumps(data("https://chrome.private.test")))
    (edge / "Bookmarks").write_text(json.dumps(data("https://edge.private.test")))
    backup_dir = tmp_path / "Backups"
    mapping_file = tmp_path / "profile-mappings.private.json"
    save_profile_mapping(mapping_file, ProfileMapping("Personal", chrome, edge, backup_dir))
    result_file = tmp_path / "automation-result.json"
    lock_file = tmp_path / "automation.lock"
    config_file = tmp_path / "automation-config.private.json"
    config_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operation": operation,
                "profile_map": mapping_file.name,
                "mappings": ["Personal"],
                "keep": 50,
                "deduplicate": False,
                "alphabetize": False,
                "duplicate_mode": "conservative",
                "merge_strategy": "chrome-wins",
                "browser_behavior": browser_behavior,
                "result_file": result_file.name,
                "lock_file": lock_file.name,
                "lock_timeout_minutes": 5,
            }
        )
    )
    return config_file, chrome, edge, backup_dir, result_file


def test_load_automation_config_resolves_private_relative_paths(tmp_path: Path):
    config_file, _, _, _, result_file = automation_files(tmp_path)

    config = load_automation_config(config_file)

    assert config.operation == "backup"
    assert config.profile_map == tmp_path / "profile-mappings.private.json"
    assert config.result_file == result_file
    assert config.lock_file == tmp_path / "automation.lock"
    assert config.mappings == ("Personal",)
    assert config.health_file == tmp_path / "browser-bookmark-automation-health.json"
    assert config.health_history_limit == 100
    assert not config.firefox_enabled
    assert not config.firefox_export
    assert not config.notifications_enabled
    assert config.notification_command == ()


def test_automation_requires_absolute_profile_mapping_paths(tmp_path: Path):
    config_file, _, _, _, _ = automation_files(tmp_path)
    mapping_file = tmp_path / "profile-mappings.private.json"
    mapping_file.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "name": "Personal",
                        "chrome_profile": "relative/chrome",
                        "edge_profile": "relative/edge",
                        "backup_dir": "relative/backups",
                    }
                ]
            }
        )
    )

    with pytest.raises(RuntimeError, match="absolute"):
        sync_module.selected_automation_mappings(load_automation_config(config_file))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", 2, "schema_version"),
        ("operation", "delete", "operation"),
        ("keep", 51, "keep"),
        ("mappings", ["Personal", "Personal"], "unique"),
        ("duplicate_mode", "unsafe", "duplicate_mode"),
        ("merge_strategy", "replace", "merge_strategy"),
        ("lock_timeout_minutes", 1, "lock_timeout_minutes"),
    ],
)
def test_automation_config_rejects_invalid_values(tmp_path: Path, field: str, value: object, message: str):
    config_file, _, _, _, _ = automation_files(tmp_path)
    document = json.loads(config_file.read_text())
    document[field] = value
    config_file.write_text(json.dumps(document))

    with pytest.raises(RuntimeError, match=message):
        load_automation_config(config_file)


def test_automation_config_allows_close_only_for_sync(tmp_path: Path):
    config_file, _, _, _, _ = automation_files(tmp_path, browser_behavior="close")

    with pytest.raises(RuntimeError, match="only when operation is sync"):
        load_automation_config(config_file)

    document = json.loads(config_file.read_text())
    document["operation"] = "sync"
    config_file.write_text(json.dumps(document))
    assert load_automation_config(config_file).browser_behavior == "close"


def test_automation_lock_blocks_concurrent_runs_and_cleans_up(tmp_path: Path):
    lock_file = tmp_path / "automation.lock"

    with AutomationRunLock(lock_file, 5):
        assert lock_file.exists()
        with pytest.raises(RuntimeError, match="already active"):
            with AutomationRunLock(lock_file, 5):
                pass

    assert not lock_file.exists()


def test_automation_lock_replaces_stale_lock(tmp_path: Path):
    lock_file = tmp_path / "automation.lock"
    lock_file.write_text("stale")
    old = sync_module.time.time() - 600
    os.utime(lock_file, (old, old))

    with AutomationRunLock(lock_file, 5):
        assert json.loads(lock_file.read_text())["pid"] == os.getpid()

    assert not lock_file.exists()


def test_automation_readiness_reports_process_warning_without_private_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    config_file, chrome, _, _, _ = automation_files(tmp_path, operation="sync")
    monkeypatch.setattr(sync_module, "running_browser_processes", lambda: ["chrome.exe"])

    document = automation_readiness(load_automation_config(config_file))
    serialized = json.dumps(document)

    assert document["status"] == "ready"
    assert document["detected_processes"] == ["chrome.exe"]
    assert "block synchronization" in document["warnings"][0]
    assert str(chrome) not in serialized


def test_run_backup_automation_writes_privacy_safe_result(tmp_path: Path):
    config_file, chrome, edge, backup_dir, result_file = automation_files(tmp_path)
    chrome_before = (chrome / "Bookmarks").read_text()
    edge_before = (edge / "Bookmarks").read_text()

    exit_code, document = run_automation(load_automation_config(config_file))
    written = json.loads(result_file.read_text())
    serialized = json.dumps(written)

    assert exit_code == 0
    assert document == written
    assert written["status"] == "success"
    assert written["mappings"][0]["backup_created"]
    assert not written["mappings"][0]["synchronized"]
    assert (chrome / "Bookmarks").read_text() == chrome_before
    assert (edge / "Bookmarks").read_text() == edge_before
    assert len(list(backup_dir.glob("Chrome_*.json"))) == 1
    assert "https://" not in serialized
    assert str(chrome) not in serialized
    health = json.loads((tmp_path / "browser-bookmark-automation-health.json").read_text())
    health_serialized = json.dumps(health)
    record = health["records"][-1]
    assert record["status"] == "success"
    assert record["operation"] == "backup"
    assert record["mappings"] == ["Personal"]
    assert record["counts"]["mapping_succeeded"] == 1
    assert record["error_category"] == "none"
    assert set(record) == {
        "operation",
        "status",
        "mappings",
        "counts",
        "duration_seconds",
        "processes",
        "error_category",
    }
    assert "https://" not in health_serialized
    assert str(chrome) not in health_serialized
    assert str(edge) not in health_serialized
    assert str(backup_dir) not in health_serialized


def test_run_dry_run_automation_creates_no_backups(tmp_path: Path):
    config_file, _, _, backup_dir, result_file = automation_files(tmp_path, operation="dry-run")

    exit_code, document = run_automation(load_automation_config(config_file))

    assert exit_code == 0
    assert document["mappings"][0]["merged_count"] == 2
    assert not backup_dir.exists()
    assert result_file.exists()


def test_run_sync_automation_blocks_browsers_after_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    config_file, _, _, backup_dir, result_file = automation_files(tmp_path, operation="sync")
    monkeypatch.setattr(sync_module, "running_browser_processes", lambda: ["chrome.exe"])

    exit_code, document = run_automation(load_automation_config(config_file))

    assert exit_code == 1
    assert document["status"] == "failed"
    assert document["mappings"][0]["backup_created"]
    assert not document["mappings"][0]["synchronized"]
    assert "chrome.exe" in document["error"]
    assert len(list(backup_dir.glob("Chrome_*.json"))) == 1
    assert json.loads(result_file.read_text()) == document
    record = json.loads((tmp_path / "browser-bookmark-automation-health.json").read_text())["records"][-1]
    assert record["status"] == "blocked"
    assert record["processes"] == ["chrome.exe"]
    assert record["error_category"] == "browser_running"
    assert record["counts"]["backups_created"] == 1


def test_run_automation_records_stale_lock_recovery(tmp_path: Path):
    config_file, _, _, _, _ = automation_files(tmp_path)
    config = load_automation_config(config_file)
    config.lock_file.write_text("stale")
    old = sync_module.time.time() - 600
    os.utime(config.lock_file, (old, old))

    exit_code, _ = run_automation(config)

    record = json.loads(config.health_file.read_text())["records"][-1]
    assert exit_code == 0
    assert record["status"] == "success"
    assert record["counts"]["stale_locks_replaced"] == 1
    assert record["error_category"] == "none"


def test_repeated_failures_are_suppressed_until_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    config_file, _, _, _, _ = automation_files(tmp_path, operation="sync")
    config_document = json.loads(config_file.read_text())
    config_document["notifications_enabled"] = True
    config_document["notification_command"] = ["local-notifier"]
    config_file.write_text(json.dumps(config_document))
    detections = iter([["chrome.exe"], ["chrome.exe"], [], ["chrome.exe"]])
    monkeypatch.setattr(sync_module, "running_browser_processes", lambda: next(detections))
    notifications: list[dict[str, object]] = []
    monkeypatch.setattr(
        sync_module,
        "deliver_failure_notification",
        lambda _command, record: notifications.append(record) or True,
    )
    config = load_automation_config(config_file)

    assert run_automation(config)[0] == 1
    assert run_automation(config)[0] == 1
    assert len(notifications) == 1
    assert run_automation(config)[0] == 0
    assert run_automation(config)[0] == 1

    assert len(notifications) == 2
    assert notifications[0]["error_category"] == "browser_running"
    statuses = [record["status"] for record in json.loads(config.health_file.read_text())["records"]]
    assert statuses == ["blocked", "blocked", "success", "blocked"]


def test_notification_payload_redacts_private_failure_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    config_file, chrome, _, backup_dir, _ = automation_files(tmp_path, operation="sync")
    config_document = json.loads(config_file.read_text())
    config_document["notifications_enabled"] = True
    config_document["notification_command"] = ["local-notifier", "credential-value"]
    config_file.write_text(json.dumps(config_document))
    private_url = "https://secret.example.test/private"
    private_title = "Confidential bookmark title"
    (chrome / "Bookmarks").write_text(json.dumps(data(private_url, private_title)))
    private_failure = f"write failed for {chrome} into {backup_dir}: {private_url} credential-value"
    monkeypatch.setattr(
        sync_module,
        "synchronize",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(private_failure)),
    )
    notifications: list[dict[str, object]] = []
    monkeypatch.setattr(
        sync_module,
        "deliver_failure_notification",
        lambda _command, record: notifications.append(record) or True,
    )

    exit_code, _ = run_automation(load_automation_config(config_file))

    config = load_automation_config(config_file)
    serialized = json.dumps(notifications[0])
    health_serialized = config.health_file.read_text()
    assert exit_code == 1
    assert private_url not in serialized
    assert private_title not in serialized
    assert str(chrome) not in serialized
    assert str(backup_dir) not in serialized
    assert "credential-value" not in serialized
    assert "notification_command" not in serialized
    assert notifications[0]["error_category"] == "automation"
    assert private_url not in health_serialized
    assert private_title not in health_serialized
    assert str(chrome) not in health_serialized
    assert str(backup_dir) not in health_serialized
    assert "credential-value" not in health_serialized


def test_run_sync_automation_reports_backups_after_transaction_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    config_file, _, _, _, _ = automation_files(tmp_path, operation="sync")

    def fail_write(*_args: object) -> None:
        raise RuntimeError("simulated write failure")

    monkeypatch.setattr(sync_module, "transactional_json_write", fail_write)

    exit_code, document = run_automation(load_automation_config(config_file))

    result = document["mappings"][0]
    assert exit_code == 1
    assert result["backup_created"]
    assert result["html_created"]
    assert result["manifest_validated"]
    assert not result["synchronized"]


def test_run_sync_automation_can_explicitly_close_browsers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    config_file, chrome, edge, _, _ = automation_files(tmp_path, operation="sync", browser_behavior="close")
    process_checks = iter([["chrome.exe", "msedge.exe"], []])
    closed: list[str] = []
    monkeypatch.setattr(sync_module, "running_browser_processes", lambda: next(process_checks, []))
    monkeypatch.setattr(sync_module, "close_browser_processes", lambda processes: closed.extend(processes))

    exit_code, document = run_automation(load_automation_config(config_file))

    assert exit_code == 0
    assert closed == ["chrome.exe", "msedge.exe"]
    assert document["mappings"][0]["synchronized"]
    assert document["mappings"][0]["browsers_closed"] == ["chrome.exe", "msedge.exe"]
    assert json.loads((chrome / "Bookmarks").read_text()) == json.loads((edge / "Bookmarks").read_text())


def test_cli_checks_and_runs_automation_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    config_file, _, _, _, result_file = automation_files(tmp_path)

    assert main(["--check-automation", str(config_file)]) == 0
    readiness = json.loads(capsys.readouterr().out)
    assert readiness["status"] == "ready"

    assert main(["--run-automation", str(config_file)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "success"
    assert result_file.exists()


def test_cli_concurrent_automation_does_not_replace_active_result(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    config_file, _, _, _, result_file = automation_files(tmp_path)
    result_file.write_text(json.dumps({"active_run": True}))
    config = load_automation_config(config_file)

    with AutomationRunLock(config.lock_file, config.lock_timeout_minutes):
        exit_code = main(["--run-automation", str(config_file)])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["status"] == "failed"
    assert "already active" in output["error"]
    assert json.loads(result_file.read_text()) == {"active_run": True}


def test_cli_automation_rejects_process_overrides(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    config_file, _, _, _, result_file = automation_files(tmp_path)

    exit_code = main(["--run-automation", str(config_file), "--force"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert "private configuration" in output["error"]
    assert not result_file.exists()


def test_powershell_automation_wrapper_runs_readiness_check(tmp_path: Path):
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        pytest.skip("PowerShell is unavailable")
    config_file, _, _, _, _ = automation_files(tmp_path)
    script = Path(__file__).with_name("Invoke-BrowserBookmarkAutomation.ps1")

    completed = subprocess.run(
        [powershell, "-NoProfile", "-File", script, "-ConfigPath", config_file, "-Mode", "Check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "ready"

    completed = subprocess.run(
        [powershell, "-NoProfile", "-File", script, "-ConfigPath", config_file, "-Mode", "Run"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "success"
    assert (tmp_path / "automation-result.json").exists()

