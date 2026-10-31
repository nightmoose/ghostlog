"""Read the remains of a job: an old log file or a deprecated SQL file.

Everything in here is deterministic. The facts a ghost may speak about are
extracted here, so the model only adds a voice, never new facts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

_TS = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)")
_LEVEL = re.compile(r"\b(DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL)\b")
_JOB = re.compile(r"\[(?P<job>[A-Za-z0-9_.\-]+)\]")
_START = re.compile(r"\b(run started|starting run|job started|started)\b", re.IGNORECASE)
_SQL_INLINE = re.compile(r"\bSQL:\s*(?P<sql>.+)$")
_QUOTED = re.compile(r"""['"`](?P<name>[A-Za-z_][A-Za-z0-9_.]*)['"`]""")
_MISSING_COL = re.compile(
    r"column\s+['\"`]?(?P<col>[A-Za-z_][A-Za-z0-9_.]*)['\"`]?\s+(does not exist|not found)",
    re.IGNORECASE,
)


@dataclass
class Remains:
    """Facts recovered from a job's log or SQL file."""

    job_name: str
    source_path: str
    first_seen: date | None = None
    last_seen: date | None = None
    run_nights: int = 0
    usual_start: str | None = None
    sql_statements: list[str] = field(default_factory=list)
    last_error: str | None = None
    died_on: date | None = None
    cause_of_death: str | None = None

    @property
    def lifespan(self) -> str:
        if self.first_seen and self.last_seen:
            return f"{self.first_seen.year} - {self.last_seen.year}"
        return "date unknown"


def _parse_ts(raw: str) -> datetime | None:
    raw = raw.replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def explain_error(message: str) -> str:
    """Turn a raw error line into a short, human cause of death."""
    missing = _MISSING_COL.search(message)
    if missing:
        col = missing.group("col").split(".")[-1]
        return f"upstream column '{col}' vanished"
    lowered = message.lower()
    if "permission denied" in lowered or "access denied" in lowered:
        return "its permissions were revoked"
    if "does not exist" in lowered or "not found" in lowered:
        quoted = _QUOTED.search(message)
        thing = f"'{quoted.group('name')}'" if quoted else "something it needed"
        return f"{thing} disappeared"
    if "timeout" in lowered or "timed out" in lowered:
        return "it waited too long and timed out"
    if "out of memory" in lowered or "oom" in lowered.split():
        return "it ran out of memory"
    return message.strip()[:120]


def _split_sql(text: str) -> list[str]:
    statements = []
    for chunk in text.split(";"):
        lines = [ln for ln in chunk.splitlines() if not ln.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if stmt:
            statements.append(stmt)
    return statements


def read_sql(path: Path) -> Remains:
    text = path.read_text(encoding="utf-8", errors="replace")
    return Remains(
        job_name=path.stem,
        source_path=str(path),
        sql_statements=_split_sql(text),
    )


def read_log(path: Path) -> Remains:
    """Parse a cron/Airflow-style text log line by line."""
    job_names: dict[str, int] = {}
    run_days: set[date] = set()
    start_times: dict[str, int] = {}
    statements: list[str] = []
    seen_sql: set[str] = set()
    first: datetime | None = None
    last: datetime | None = None
    last_error: tuple[datetime | None, str] | None = None

    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            ts_match = _TS.match(line)
            ts = _parse_ts(ts_match.group("ts")) if ts_match else None
            if ts:
                first = ts if first is None or ts < first else first
                last = ts if last is None or ts > last else last
            job = _JOB.search(line)
            if job:
                job_names[job.group("job")] = job_names.get(job.group("job"), 0) + 1
            if ts and _START.search(line):
                run_days.add(ts.date())
                key = ts.strftime("%H:%M")
                start_times[key] = start_times.get(key, 0) + 1
            sql = _SQL_INLINE.search(line)
            if sql:
                stmt = sql.group("sql").strip().rstrip(";")
                if stmt not in seen_sql:
                    seen_sql.add(stmt)
                    statements.append(stmt)
            level = _LEVEL.search(line)
            if level and level.group(1) in {"ERROR", "CRITICAL", "FATAL"}:
                msg = line[level.end() :].strip(" :-")
                if job:
                    msg = _JOB.sub("", msg, count=1).strip(" :-")
                last_error = (ts, msg)

    name = max(job_names, key=job_names.get) if job_names else path.stem
    remains = Remains(
        job_name=name,
        source_path=str(path),
        first_seen=first.date() if first else None,
        last_seen=last.date() if last else None,
        run_nights=len(run_days),
        usual_start=max(start_times, key=start_times.get) if start_times else None,
        sql_statements=statements,
    )
    if last_error:
        err_ts, msg = last_error
        remains.last_error = msg
        remains.died_on = err_ts.date() if err_ts else remains.last_seen
        remains.cause_of_death = explain_error(msg)
    return remains


def read_remains(path: str | Path) -> Remains:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"no remains found at {p}")
    if p.suffix.lower() == ".sql":
        return read_sql(p)
    return read_log(p)
