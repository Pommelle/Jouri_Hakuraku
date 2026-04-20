from agent.state import AgentState
from agent.llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage
from typing import Optional
import json
import time
import os
import ssl

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'nexus.db')
TRACKING_TOPIC = os.getenv("TRACKING_TOPIC", "")

_cache: Optional[dict] = None
_cache_at: float = 0.0
_CACHE_TTL = 60.0


def _load_overrides_from_db() -> dict:
    global _cache, _cache_at
    now = time.time()
    if _cache is not None and (now - _cache_at) < _CACHE_TTL:
        return _cache

    import sqlite3
    overrides = {}
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT source_key, anchor FROM source_confidence")
        for row in cur.fetchall():
            overrides[row['source_key'].lower()] = row['anchor']
        conn.close()
    except Exception:
        pass

    _cache = overrides
    _cache_at = now
    return overrides


def _invalidate_cache():
    global _cache, _cache_at
    _cache = None
    _cache_at = 0.0


def _get_source_anchor(source: str) -> Optional[float]:
    overrides = _load_overrides_from_db()
    src_lower = source.lower()
    for key, value in overrides.items():
        if key in src_lower:
            return value
    return None


def triage_node(state: AgentState) -> dict:
    llm = get_llm()

    raw_content = state.get("raw_content", "")
    source = state.get("source", "unknown")

    anchor = _get_source_anchor(source)
    anchor_clause = ""
    if anchor is not None:
        anchor_clause = f' Source "{source}" has a known baseline confidence of {anchor:.0%}. Do not exceed this.'

    system_prompt = f"""You are a threat intelligence triage filter.

TASK: Decide whether this content is worth further analysis, and if so, produce a structured intel summary.

Criteria:
- Pass (score >= 60): Directly relevant to "{TRACKING_TOPIC}"
- Fail (score < 60): Off-topic, casual chat, memes, support questions, tangential news unrelated to "{TRACKING_TOPIC}".
Even significant cyber events NOT about "{TRACKING_TOPIC}" should fail.{anchor_clause}

Return ONLY this JSON (no markdown, no explanation):
{{"relevance_score": integer, "triage_reason": "one sentence", "title": "concise title if passing, else empty string", "summary": "2-3 sentence executive summary if passing, else empty string", "tags": "comma-separated tags if passing, else empty string"}}
"""

    human_prompt = f"Source: {source}\nContent: {raw_content}"

    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ])

            raw = response.content
            if isinstance(raw, dict):
                raw = raw.get("text", "")
            elif isinstance(raw, list):
                raw = " ".join(
                    b.get("text", "") if isinstance(b, dict) else (b.text if hasattr(b, "text") else str(b))
                    for b in raw
                )
            elif hasattr(raw, "text"):
                raw = raw.text
            else:
                raw = str(raw)
            raw = raw.strip().strip("`")
            for marker in ("```json", "```JSON", "```"):
                if marker in raw:
                    raw = raw.split(marker, 1)[1].split("```")[0].strip()

            result = json.loads(raw)
            score = int(result.get("relevance_score", 0))
            pass_through = score >= 60

            print(f"[Triage] Score: {score}/100 | Pass: {pass_through}")

            if pass_through:
                return {
                    "triage_result": True,
                    "triage_reason": result.get("triage_reason", ""),
                    "confidence_rationale": "",
                    "relevance_score": score,
                    "confidence_score": anchor if anchor is not None else 0.5,
                    "iocs_found": [],
                    "title": result.get("title", "Intel Entry"),
                    "final_synthesis": result.get("summary", ""),
                    "tags": result.get("tags", ""),
                }
            else:
                return {
                    "triage_result": False,
                    "triage_reason": result.get("triage_reason", ""),
                    "confidence_rationale": "",
                    "relevance_score": 0,
                    "confidence_score": 0.0,
                    "iocs_found": [],
                    "title": "",
                    "final_synthesis": "",
                    "tags": "",
                }

        except (ssl.SSLError, OSError) as e:
            if attempt < MAX_RETRIES - 1:
                print(f"[Triage] Network error, retrying ({attempt + 1}/{MAX_RETRIES}): {e}")
                time.sleep(2 ** attempt)
                continue
            print(f"[Triage] Error after {MAX_RETRIES} retries: {e}")
            return {
                "triage_result": False,
                "triage_reason": "Network/Parse error",
                "confidence_rationale": "",
                "relevance_score": 0,
                "confidence_score": 0.0,
                "iocs_found": [],
                "title": "",
                "final_synthesis": "",
                "tags": "",
            }
        except (json.JSONDecodeError, ValueError, AttributeError, TypeError) as e:
            print(f"[Triage] Parse error: {e}, raw: {raw if 'raw' in dir() else 'N/A'}")
            return {
                "triage_result": False,
                "triage_reason": "Parse error",
                "confidence_rationale": "",
                "relevance_score": 0,
                "confidence_score": 0.0,
                "iocs_found": [],
                "title": "",
                "final_synthesis": "",
                "tags": "",
            }
