from datetime import date

import pytest

from ghostlog.logparse import explain_error, read_remains


def test_reads_example_log(etl_log):
    r = read_remains(etl_log)
    assert r.job_name == "nightly_orders_etl"
    assert r.first_seen == date(2021, 4, 21)
    assert r.died_on == date(2025, 3, 14)
    assert r.run_nights == 1424
    assert r.usual_start == "02:00"
    assert r.lifespan == "2021 - 2025"
    assert r.cause_of_death == "upstream column 'cust_id' vanished"
    assert len(r.sql_statements) == 2  # deduplicated across nights


def test_reads_sql_file(churn_sql):
    r = read_remains(churn_sql)
    assert r.job_name == "churn_scores"
    assert len(r.sql_statements) == 2
    assert r.lifespan == "date unknown"
    assert r.died_on is None


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_remains(tmp_path / "nope.log")


def test_log_without_errors(tmp_path):
    p = tmp_path / "quiet.log"
    p.write_text(
        "2024-01-01 03:00:00 INFO [quiet_job] run started\n"
        "2024-01-02 03:00:00 INFO [quiet_job] run started\n"
    )
    r = read_remains(p)
    assert r.run_nights == 2
    assert r.usual_start == "03:00"
    assert r.cause_of_death is None


def test_iso_t_timestamps_and_no_job_tag(tmp_path):
    p = tmp_path / "legacy_export.log"
    p.write_text("2023-05-01T01:15:00 INFO starting run\n2023-05-01T01:16 ERROR timed out\n")
    r = read_remains(p)
    assert r.job_name == "legacy_export"
    assert r.run_nights == 1
    assert r.cause_of_death == "it waited too long and timed out"


def test_empty_log(tmp_path):
    p = tmp_path / "empty.log"
    p.write_text("")
    r = read_remains(p)
    assert r.run_nights == 0 and r.sql_statements == [] and r.first_seen is None


@pytest.mark.parametrize(
    "msg,expected",
    [
        ('column "cust_id" does not exist', "upstream column 'cust_id' vanished"),
        ("Column orders.cust_id not found", "upstream column 'cust_id' vanished"),
        ("permission denied for schema raw", "its permissions were revoked"),
        ("relation 'raw.orders' does not exist", "'raw.orders' disappeared"),
        ("worker killed: out of memory", "it ran out of memory"),
        ("something odd happened", "something odd happened"),
    ],
)
def test_explain_error(msg, expected):
    assert explain_error(msg) == expected
