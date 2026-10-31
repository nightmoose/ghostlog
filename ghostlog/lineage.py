"""Table-level lineage from SQL, using sqlglot."""

from __future__ import annotations

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp


@dataclass
class Lineage:
    edges: list[tuple[str, str]] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)

    @property
    def sources(self) -> list[str]:
        targets = {t for _, t in self.edges}
        return sorted({s for s, _ in self.edges if s not in targets})

    @property
    def sinks(self) -> list[str]:
        sources = {s for s, _ in self.edges}
        return sorted({t for _, t in self.edges if t not in sources})

    @property
    def tables(self) -> list[str]:
        return sorted({n for e in self.edges for n in e})

    def chain(self) -> list[str]:
        """Longest source-to-sink path, the spine shown on the tombstone."""
        graph: dict[str, list[str]] = {}
        for s, t in self.edges:
            graph.setdefault(s, []).append(t)
        best: list[str] = []

        def walk(node: str, path: list[str]) -> None:
            nonlocal best
            nexts = [n for n in sorted(graph.get(node, [])) if n not in path]
            if not nexts:
                if len(path) > len(best):
                    best = path
                return
            for n in nexts:
                walk(n, path + [n])

        for src in self.sources or sorted(graph):
            walk(src, [src])
        return best

    def describe(self) -> str:
        chain = self.chain()
        return " -> ".join(chain) if chain else "(no lineage found)"


def _name(table: exp.Table) -> str:
    parts = [p for p in (table.catalog, table.db, table.name) if p]
    return ".".join(parts).lower()


def _target(stmt: exp.Expression) -> exp.Table | None:
    if isinstance(stmt, (exp.Insert, exp.Create, exp.Merge, exp.Update)):
        node = stmt.this
        if isinstance(node, exp.Schema):
            node = node.this
        if isinstance(node, exp.Table):
            return node
    return None


def statement_edges(sql: str, dialect: str | None = None) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for stmt in sqlglot.parse(sql, read=dialect):
        if stmt is None:
            continue
        target = _target(stmt)
        if target is None:
            continue
        tgt = _name(target)
        cte_names = {c.alias_or_name.lower() for c in stmt.find_all(exp.CTE)}
        for table in stmt.find_all(exp.Table):
            if table is target:
                continue
            src = _name(table)
            if src and src != tgt and src not in cte_names:
                edge = (src, tgt)
                if edge not in edges:
                    edges.append(edge)
    return edges


def build_lineage(statements: list[str], dialect: str | None = None) -> Lineage:
    lineage = Lineage()
    for sql in statements:
        try:
            for edge in statement_edges(sql, dialect):
                if edge not in lineage.edges:
                    lineage.edges.append(edge)
        except sqlglot.errors.ParseError:
            lineage.unparsed.append(sql)
    return lineage
