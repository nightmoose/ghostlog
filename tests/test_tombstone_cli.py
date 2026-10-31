from ghostlog.cli import main
from ghostlog.lineage import build_lineage
from ghostlog.logparse import Remains, read_remains
from ghostlog.medium import Seance, template_seance
from ghostlog.tombstone import render


def test_render_contains_mockup_text(etl_log):
    r = read_remains(etl_log)
    lin = build_lineage(r.sql_statements)
    page = render(r, lin, template_seance(r, lin))
    for text in [
        "R.I.P.",
        "nightly_orders_etl",
        "2021 - 2025",
        "Faithfully fed",
        "mart.daily_revenue",
        "until cust_id left us.",
        "Ghostlog - Tombstone",
    ]:
        assert text in page
    assert "http://" not in page and "https://" not in page  # fully offline page


def test_render_escapes_html():
    r = Remains(job_name="<script>alert(1)</script>", source_path="x")
    lin = build_lineage([])
    page = render(r, lin, Seance(["<b>hi</b>"] * 3, ["<i>"] * 3, "test", False))
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page and "&lt;b&gt;hi" in page


def test_cli_summon_offline(etl_log, tmp_path, capsys):
    out = tmp_path / "t.html"
    assert main(["summon", str(etl_log), "--offline", "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "I was nightly_orders_etl" in text
    assert "lineage: raw.orders -> stg.orders -> mart.daily_revenue" in text
    assert "\033[" not in text  # no colour when not a TTY
    assert "R.I.P." in out.read_text()


def test_cli_summon_degrades_without_ollama(etl_log, tmp_path, capsys, monkeypatch):
    import urllib.error
    import urllib.request

    def refuse(*a, **k):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    out = tmp_path / "t.html"
    rc = main(["summon", str(etl_log), "--host", "http://127.0.0.1:9", "--out", str(out)])
    assert rc == 0
    assert "unreachable" in capsys.readouterr().out
    assert out.exists()


def test_cli_lineage(churn_sql, capsys):
    assert main(["lineage", str(churn_sql)]) == 0
    assert "analytics.churn_scores -> reports.churn_weekly" in capsys.readouterr().out


def test_cli_missing_file(tmp_path, capsys):
    assert main(["lineage", str(tmp_path / "gone.log")]) == 2
    assert "no remains found" in capsys.readouterr().err
