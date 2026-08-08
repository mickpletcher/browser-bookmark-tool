import json
from pathlib import Path

from browser_bookmark_sync import export_html, merge_bookmarks, synchronize


def data(*urls: str) -> dict:
    children = [{"type": "url", "id": str(i + 10), "name": url, "url": url} for i, url in enumerate(urls)]
    return {"roots": {"bookmark_bar": {"type": "folder", "id": "1", "name": "Bookmarks bar", "children": children}, "other": {"type": "folder", "id": "2", "name": "Other bookmarks", "children": []}}, "version": 1, "checksum": "old"}


def test_merge_deduplicates_and_retains_unique_links():
    merged, added = merge_bookmarks(data("https://a.test/", "https://b.test"), data("https://a.test", "https://c.test"))
    text = json.dumps(merged)
    assert added == 1
    assert text.count("https://c.test") == 1
    assert "checksum" not in merged


def test_export_html(tmp_path: Path):
    destination = tmp_path / "bookmarks.html"
    count = export_html(data("https://example.test/?a=1&b=2"), destination)
    assert count == 1
    assert "NETSCAPE-Bookmark-file-1" in destination.read_text()
    assert "&amp;" in destination.read_text()


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

