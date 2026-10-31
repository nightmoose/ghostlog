from ghostlog.lineage import build_lineage, statement_edges
from ghostlog.logparse import read_remains


def test_example_chain(etl_log):
    lin = build_lineage(read_remains(etl_log).sql_statements)
    assert lin.chain() == ["raw.orders", "stg.orders", "mart.daily_revenue"]
    assert lin.sources == ["raw.orders"]
    assert lin.sinks == ["mart.daily_revenue"]
    assert lin.describe() == "raw.orders -> stg.orders -> mart.daily_revenue"


def test_ctes_are_not_tables(churn_sql):
    lin = build_lineage(read_remains(churn_sql).sql_statements)
    assert ("active", "analytics.churn_scores") not in lin.edges
    assert ("crm.customers", "analytics.churn_scores") in lin.edges
    assert ("raw.orders", "analytics.churn_scores") in lin.edges
    assert ("analytics.churn_scores", "reports.churn_weekly") in lin.edges
    assert lin.sinks == ["reports.churn_weekly"]


def test_create_table_as_and_merge():
    assert statement_edges("CREATE TABLE a.b AS SELECT * FROM c.d") == [("c.d", "a.b")]
    merge = "MERGE INTO t.dim USING s.src ON t.dim.id = s.src.id WHEN MATCHED THEN UPDATE SET x = 1"
    assert statement_edges(merge) == [("s.src", "t.dim")]


def test_plain_select_has_no_target():
    assert statement_edges("SELECT * FROM raw.orders") == []


def test_unparseable_sql_is_kept_not_fatal():
    lin = build_lineage(["INSERT INTO a SELECT * FROM b", "INSERT INTO ((("])
    assert lin.edges == [("b", "a")]
    assert len(lin.unparsed) == 1


def test_dialect_specific_sql():
    sql = "INSERT INTO `proj.ds.out` SELECT * FROM `proj.ds.in`"
    assert statement_edges(sql, dialect="bigquery") == [("proj.ds.in", "proj.ds.out")]


def test_empty_lineage():
    lin = build_lineage([])
    assert lin.chain() == [] and lin.describe() == "(no lineage found)"
