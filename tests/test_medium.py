from ghostlog.lineage import build_lineage
from ghostlog.logparse import read_remains
from ghostlog.medium import ask_ollama, channel, facts, grounded, template_seance


def _parts(path):
    r = read_remains(path)
    return r, build_lineage(r.sql_statements)


def test_template_matches_mockup(etl_log):
    s = template_seance(*_parts(etl_log))
    assert s.testimony == [
        "I was nightly_orders_etl. I ran at 02:00 for 1,424 nights.",
        "I read raw.orders and wrote mart.daily_revenue.",
        "I died on 2025-03-14: upstream column 'cust_id' vanished.",
    ]
    assert s.epitaph == ["Faithfully fed", "mart.daily_revenue", "until cust_id left us."]
    assert not s.channeled


def test_facts_are_grounded(etl_log):
    f = facts(*_parts(etl_log))
    assert f["read_from"] == ["raw.orders"]
    assert f["wrote_to"] == ["mart.daily_revenue"]
    assert f["nights_run"] == 1424


def test_channel_uses_model_answer(etl_log):
    seen = {}

    def fake(payload, model, host):
        seen.update(payload=payload, model=model)
        return {
            "testimony": ["I was nightly_orders_etl, waking at 02:00.", "b", "c"],
            "epitaph": ["x", "y", "z"],
        }

    s = channel(*_parts(etl_log), model="gemma3:4b", asker=fake)
    assert s.channeled and s.voice == "gemma3:4b via ollama"
    assert s.testimony[0] == "I was nightly_orders_etl, waking at 02:00."
    assert seen["payload"]["job_name"] == "nightly_orders_etl"


def test_channel_falls_back_when_unreachable(etl_log):
    s = channel(*_parts(etl_log), model="gemma3:4b", asker=lambda *a, **k: None)
    assert not s.channeled and s.voice == "offline template"
    assert s.note == "gemma3:4b unreachable"


def test_channel_falls_back_on_malformed_answer(etl_log):
    for bad in [
        {"testimony": "nope"},
        {"testimony": ["a"], "epitaph": ["b"]},
        [],
        "x",
        {"testimony": ["", "", ""], "epitaph": ["a", "b", "c"]},
    ]:
        s = channel(*_parts(etl_log), asker=lambda *a, b=bad, **k: b)
        assert not s.channeled
        assert s.note.endswith("malformed")


def test_channel_rejects_ungrounded_answer(etl_log):
    invented = {
        "testimony": ["I was nightly_orders_etl.", "I ran for 9,999 nights.", "Then I slept."],
        "epitaph": ["a", "b", "c"],
    }
    s = channel(*_parts(etl_log), asker=lambda *a, **k: invented)
    assert not s.channeled and s.note.endswith("not grounded in the facts")


def test_grounded_rules(etl_log):
    known = facts(*_parts(etl_log))
    ok = ["I was nightly_orders_etl at 02:00 for 1,424 nights; died 2025-03-14."]
    assert grounded(ok, known)
    assert grounded(["nightly_orders_etl ran 1424 nights"], known)
    assert not grounded(["I was a nightly orders job"], known)  # never named itself
    assert not grounded(["nightly_orders_etl ran 99 nights"], known)  # invented number


def test_offline_flag_never_calls_model(etl_log):
    def explode(*a, **k):
        raise AssertionError("should not be called")

    assert not channel(*_parts(etl_log), offline=True, asker=explode).channeled


def test_ask_ollama_returns_none_when_server_down(monkeypatch):
    import urllib.error
    import urllib.request

    def refuse(*a, **k):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    assert ask_ollama({"job_name": "x"}, host="http://127.0.0.1:9") is None


def test_ask_ollama_parses_response(monkeypatch):
    import io
    import json
    import urllib.request

    inner = json.dumps({"testimony": ["1", "2", "3"], "epitaph": ["4", "5", "6"]})

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    captured = {}

    def fake(req, timeout):
        captured["body"] = json.loads(req.data)
        return Resp(json.dumps({"response": inner}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    out = ask_ollama({"job_name": "x"}, model="gemma3:1b")
    assert out["epitaph"] == ["4", "5", "6"]
    assert captured["body"]["model"] == "gemma3:1b"
    assert captured["body"]["format"]["required"] == ["testimony", "epitaph"]
    assert captured["body"]["stream"] is False


def test_ask_ollama_handles_non_json(monkeypatch):
    import io
    import json
    import urllib.request

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda req, timeout: Resp(json.dumps({"response": "not json"}).encode()),
    )
    assert ask_ollama({}) is None
