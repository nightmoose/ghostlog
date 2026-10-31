"""Regenerate examples/legacy/nightly_orders_etl.log (a synthetic, deterministic log)."""

from datetime import date, timedelta
from pathlib import Path

JOB = "nightly_orders_etl"
START = date(2021, 4, 21)
DEATH = date(2025, 3, 14)
SQL = [
    (
        "INSERT INTO stg.orders SELECT order_id, cust_id, amount, order_ts FROM raw.orders "
        "WHERE order_ts >= CURRENT_DATE - 1"
    ),
    (
        "INSERT INTO mart.daily_revenue SELECT CAST(order_ts AS DATE) AS day, SUM(amount) "
        "AS revenue, COUNT(DISTINCT cust_id) AS customers FROM stg.orders GROUP BY 1"
    ),
]


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "examples" / "legacy" / f"{JOB}.log"
    lines = []
    day = START
    while day <= DEATH:
        d = day.isoformat()
        lines.append(f"{d} 02:00:00 INFO [{JOB}] run started")
        lines.append(f"{d} 02:00:01 INFO [{JOB}] SQL: {SQL[0]}")
        if day == DEATH:
            lines.append(
                f'{d} 02:00:04 ERROR [{JOB}] column "cust_id" does not exist in raw.orders'
            )
            lines.append(f"{d} 02:00:04 INFO [{JOB}] run failed; scheduler disabled job")
        else:
            lines.append(f"{d} 02:03:12 INFO [{JOB}] SQL: {SQL[1]}")
            lines.append(f"{d} 02:03:40 INFO [{JOB}] run finished ok")
        day += timedelta(days=1)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} lines to {out}")


if __name__ == "__main__":
    main()
