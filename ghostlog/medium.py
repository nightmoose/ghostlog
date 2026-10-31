"""The medium: gives a dead job its voice.

Talks to a local Ollama server (default model: Gemma). If Ollama is not
running, or the model answers with something unusable, Ghostlog falls back to
a deterministic template so the seance always completes offline.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from .lineage import Lineage
from .logparse import Remains

DEFAULT_MODEL = os.environ.get("GHOSTLOG_MODEL", "gemma3:4b")
DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

SYSTEM_PROMPT = (
    "You are the ghost of a retired data pipeline, speaking at a gentle "
    "Dia de los Muertos ofrenda. Speak in the first person, warm and a little "
    "eerie. Use ONLY the facts given in the JSON. Never invent table names, "
    "dates, numbers, or causes.\n"
    "Reply with JSON only, with two keys:\n"
    '"testimony": exactly 3 short sentences. Sentence 1 says your job_name, '
    "usual_start_time and nights_run. Sentence 2 names the tables in read_from "
    "and wrote_to. Sentence 3 gives died_on and cause_of_death.\n"
    '"epitaph": exactly 3 short lines for a tombstone, at most 6 words each, '
    "mentioning one table you fed."
)


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "testimony": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
        "epitaph": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
    },
    "required": ["testimony", "epitaph"],
}

_NUMBER = re.compile(r"\d+")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")


@dataclass
class Seance:
    testimony: list[str]
    epitaph: list[str]
    voice: str  # e.g. "gemma3:4b via ollama" or "offline template"
    channeled: bool
    note: str = ""  # why the template was used, if it was


def facts(remains: Remains, lineage: Lineage) -> dict:
    return {
        "job_name": remains.job_name,
        "usual_start_time": remains.usual_start,
        "nights_run": remains.run_nights or None,
        "first_seen": remains.first_seen.isoformat() if remains.first_seen else None,
        "died_on": remains.died_on.isoformat() if remains.died_on else None,
        "cause_of_death": remains.cause_of_death,
        "read_from": lineage.sources,
        "wrote_to": lineage.sinks,
        "lineage": lineage.chain(),
    }


def template_seance(remains: Remains, lineage: Lineage) -> Seance:
    """Deterministic voice used when no model is reachable."""
    first = f"I was {remains.job_name}."
    if remains.usual_start and remains.run_nights:
        first = (
            f"I was {remains.job_name}. I ran at {remains.usual_start} "
            f"for {remains.run_nights:,} nights."
        )
    reads = ", ".join(lineage.sources) or "nothing I can recall"
    writes = ", ".join(lineage.sinks) or "nowhere I can recall"
    second = f"I read {reads} and wrote {writes}."
    if remains.died_on and remains.cause_of_death:
        third = f"I died on {remains.died_on.isoformat()}: {remains.cause_of_death}."
    else:
        third = "My last night is lost to time, but my queries remain."
    sink = lineage.sinks[0] if lineage.sinks else "the warehouse"
    cause = (remains.cause_of_death or "the end came").rstrip(".")
    epitaph = ["Faithfully fed", sink, f"until {_short_cause(cause)}."]
    return Seance([first, second, third], epitaph, "offline template", False)


def _short_cause(cause: str) -> str:
    if cause.startswith("upstream column '") and cause.endswith("' vanished"):
        col = cause[len("upstream column '") : -len("' vanished")]
        return f"{col} left us"
    return cause


def grounded(lines: list[str], known: dict) -> bool:
    """Reject answers that skip the job's name or invent numbers.

    Every number the ghost speaks must already appear in the facts.
    """
    text = " ".join(lines)
    if str(known.get("job_name", "")).lower() not in text.lower():
        return False
    allowed = set(_digits(json.dumps(known)))
    return all(n in allowed for n in _digits(text))


def _digits(text: str) -> list[str]:
    """Digit runs, with thousands separators removed ("1,424" -> "1424")."""
    return _NUMBER.findall(_THOUSANDS.sub("", text))


def _valid(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    for key, n in (("testimony", 3), ("epitaph", 3)):
        value = payload.get(key)
        if not isinstance(value, list) or len(value) < n:
            return False
        if not all(isinstance(x, str) and x.strip() for x in value[:n]):
            return False
    return True


def ask_ollama(
    payload: dict,
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    timeout: float = 120.0,
) -> dict | None:
    body = json.dumps(
        {
            "model": model,
            "system": SYSTEM_PROMPT,
            "prompt": "Facts:\n" + json.dumps(payload, indent=2),
            "format": RESPONSE_SCHEMA,
            "stream": False,
            "options": {"temperature": 0.6, "seed": 31},
        }
    ).encode()
    req = urllib.request.Request(
        host.rstrip("/") + "/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            outer = json.loads(resp.read().decode())
        return json.loads(outer.get("response", ""))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def channel(
    remains: Remains,
    lineage: Lineage,
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    offline: bool = False,
    asker=ask_ollama,
) -> Seance:
    fallback = template_seance(remains, lineage)
    if offline:
        fallback.note = "skipped (--offline)"
        return fallback
    known = facts(remains, lineage)
    answer = asker(known, model=model, host=host)
    if answer is None:
        fallback.note = f"{model} unreachable"
        return fallback
    if not _valid(answer):
        fallback.note = f"{model} answer was malformed"
        return fallback
    testimony = [s.strip() for s in answer["testimony"][:3]]
    epitaph = [s.strip() for s in answer["epitaph"][:3]]
    if not grounded(testimony + epitaph, known):
        fallback.note = f"{model} answer was not grounded in the facts"
        return fallback
    return Seance(testimony, epitaph, f"{model} via ollama", True)
