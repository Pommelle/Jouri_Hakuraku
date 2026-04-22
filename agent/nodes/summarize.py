from agent.state import AgentState
from agent.llm_factory import get_llm, get_daily_rollup_llm
from database.crud import (
    insert_daily_summary,
    get_center_intel_by_date,
    get_memory_chunks,
    delete_center_intel_by_date,
    delete_center_intel_by_ids,
    insert_chunk_summary,
    mark_memory_summarized,
    get_source_confidence_by_key,
    get_chunk_summaries_by_date,
    get_memory_unsummarized_count,
    get_memory_unsummarized_batch,
    delete_memory_chunks,
    _get_next_memory_chunk_index,
)
from langchain_core.messages import SystemMessage, HumanMessage
import json

CHUNK_SIZE = 50


def chunk_summary_node(state: AgentState, team: str = "center") -> dict:
    """
    Drain ALL remaining intel for the target date and team into chunk summaries.
    Internally loops: each call consumes up to CHUNK_SIZE items until none remain.
    On success, deletes consumed intel entries and returns a summary.

    Pass state = {"target_date": "YYYY-MM-DD"} (chunk_index is ignored internally).
    """
    llm = get_llm()
    target_date = state.get("target_date")
    if not target_date:
        return {"error": "No target_date provided to chunk_summary_node"}

    total_items = len(get_center_intel_by_date(target_date, team=team))
    if total_items == 0:
        return {"date": target_date, "chunks": 0, "chunk_ids": [], "team": team}

    chunks_processed = 0
    chunk_ids = []

    while True:
        chunk_index = chunks_processed
        all_intel = get_center_intel_by_date(target_date, team=team)
        if not all_intel:
            break

        start = chunk_index * CHUNK_SIZE
        end = start + CHUNK_SIZE
        chunk_items = all_intel[start:end]
        if not chunk_items:
            break

        combined = "\n".join(
            f"- [{item.get('intel_type', 'mixed')}] {item.get('title', 'No title')}: "
            f"{item.get('synthesis', item.get('summary', ''))}"
            for item in chunk_items
        )

        seen_sources = {}
        for item in chunk_items:
            src = item.get("source", "")
            if src and src not in seen_sources:
                seen_sources[src] = get_source_confidence_by_key(src)

        confidence_hints = [
            f'  - "{src}": anchor {conf["anchor"]:.0%} (tier: {conf["tier"]})'
            if conf else f'  - "{src}": unknown'
            for src, conf in seen_sources.items()
        ]
        confidence_hint_block = "\n".join(confidence_hints) if confidence_hints else "  (no source records found)"

        system_prompt = f"""You are the 'Nexus Chunk Analyst'.
Your task is to analyze a batch of up to 50 intelligence items and produce a concise chunk briefing.

Reference confidence anchors for known sources:
{confidence_hint_block}

Analyze the raw intel items and produce a structured briefing. Return a JSON:
{{
    "topics": "comma-separated topic tags",
    "topic_details": [
        {{
            "topic": "short topic name",
            "brief_analysis": "2-3 sentence summary of what happened in this topic",
            "source_views": [
                {{
                    "source": "source name",
                    "claim": "key claim or finding",
                    "time": "timestamp or time reference if available"
                }}
            ]
        }}
    ]
}}

Guidelines:
- Identify distinct topics within this batch
- For each topic, extract the most relevant source claims (up to 5 per topic)
- Include timestamps if present in the source material
- Keep brief_analysis concise (2-3 sentences)
- The overall topics field should be a comma-separated list of topic names"""

        human_prompt = f"""Intelligence chunk {chunk_index} for {target_date} ({len(chunk_items)} items):

{combined}

Generate the chunk briefing."""

        print(f"[Chunk] Processing {len(chunk_items)} items for chunk {chunk_index} on {target_date}...")

        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ])
            raw = _extract_json(response)
            result = json.loads(raw)
            topics = result.get("topics", "")
            topic_details = result.get("topic_details", [])

            brief_parts = [f"[{td.get('topic', 'Unknown')}] {td.get('brief_analysis', '')}"
                           for td in topic_details]
            brief_analysis = " | ".join(brief_parts)
            source_views = json.dumps(topic_details, ensure_ascii=False)

            chunk_id = insert_chunk_summary(
                date=target_date, chunk_index=chunk_index, raw_count=len(chunk_items),
                topics=topics, brief_analysis=brief_analysis,
                source_views=source_views, source_confidence=confidence_hint_block, team=team,
            )
            delete_center_intel_by_ids([item['id'] for item in chunk_items], team=team)
            print(f"[Chunk] Chunk {chunk_index} done, chunk_id={chunk_id}.")
            chunk_ids.append(chunk_id)
            chunks_processed += 1

        except Exception as e:
            print(f"[Chunk] Error processing chunk {chunk_index}: {e}")
            return {"date": target_date, "chunks": chunks_processed, "chunk_ids": chunk_ids,
                    "error": str(e), "team": team}

    return {"date": target_date, "chunks": chunks_processed, "chunk_ids": chunk_ids, "team": team}


def summarize_node(state: AgentState, team: str = "center") -> dict:
    """
    Daily rollup: aggregate ALL chunk summaries for the target date
    (no team filter — red and blue share the same chunk pool), then
    roll up into red + blue reports.
    Uses the dedicated DAILY_ROLLUP LLM for both reports.
    """
    llm = get_daily_rollup_llm()
    target_date = state.get("target_date")
    if not target_date:
        return {"error": "No target_date provided to summarize_node"}

    # Read ALL chunks for the date — shared view for both teams
    all_chunks = get_chunk_summaries_by_date(target_date, team=None)
    if not all_chunks:
        intel_list = get_center_intel_by_date(target_date, team="center")
        if not intel_list:
            print(f"[Summarize] No chunks and no intel for {target_date}, skipping.")
            return {"date": target_date, "red_summary_id": None, "blue_summary_id": None, "team": "joint"}
        return _do_raw_joint_rollup(target_date, intel_list, llm)
    else:
        return _do_joint_rollup(target_date, all_chunks, llm)


def _build_chunk_topic_parts(c: dict) -> str:
    """Parse a chunk's source_views JSON and return a formatted topic text block."""
    topic_parts = [f"## Chunk {c['chunk_index']} ({c['raw_count']} items)", f"Topics: {c['topics'] or 'N/A'}", ""]

    source_views_raw = c.get('source_views', '')
    if source_views_raw:
        try:
            topic_details = json.loads(source_views_raw)
        except (json.JSONDecodeError, TypeError):
            topic_details = []
    else:
        topic_details = []

    if topic_details:
        for td in topic_details:
            topic_name = td.get("topic", "Unknown")
            analysis = td.get("brief_analysis", "")
            topic_parts.append(f"### {topic_name}")
            topic_parts.append(f"Analysis: {analysis}")
            sources = td.get("source_views", [])
            if sources:
                topic_parts.append("Source views:")
                for sv in sources:
                    src_name = sv.get("source", "Unknown")
                    claim = sv.get("claim", "")
                    time_str = sv.get("time", "")
                    time_suffix = f" @ {time_str}" if time_str else ""
                    topic_parts.append(f"  - [{src_name}]{time_suffix}: {claim}")
            topic_parts.append("")
    else:
        topic_parts.append(f"Analysis: {c.get('brief_analysis', 'N/A')}")
        topic_parts.append("")

    return "\n".join(topic_parts).strip()


def _team_label(team: str) -> str:
    if team == "red":
        return "Red Team"
    elif team == "blue":
        return "Blue Team"
    elif team == "memory":
        return "Memory Rollup"
    return team.title()


def _call_rollup_llm(system_prompt: str, human_prompt: str, llm,
                     target_date: str, team: str) -> dict:
    """
    Shared LLM call for structured rollup reports.
    Parses the JSON response and writes a single summary to the DB.
    Returns dict with summary_id, content, and team.
    """
    print(f"[Summarize] Rolling up ({team}) for {target_date}...")

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])
        raw = _extract_json(response)
        result = json.loads(raw)

        # Flatten structured sections into a readable content string
        content = _format_structured_content(result, team)

        # Extract source hints from any embedded source_views
        source_hint = ",".join(sorted(set(
            sv.get("source", "").strip()
            for key, val in result.items()
            for td in (val if isinstance(val, list) else [])
            for sv in (td.get("source_views", []) if isinstance(td, dict) else [])
            if sv.get("source", "").strip()
        )))

        summary_id = insert_daily_summary(
            date=target_date,
            content=content,
            source_hint=source_hint,
            raw_count=0,
            team=team,
        )

        print(f"[Summarize] {team.upper()} summary id={summary_id} written.")
        return {"date": target_date, "summary_id": summary_id, "content": content, "team": team}

    except Exception as e:
        print(f"[Summarize] Error generating {team} summary for {target_date}: {e}")
        return {"date": target_date, "summary_id": None, "error": str(e), "team": team}


def _format_structured_content(result: dict, team: str) -> str:
    """Render a structured rollup JSON into a readable plain-text briefing."""
    lines = []

    if team == "red":
        labels = {
            "bluf": "🔴 BLUF",
            "fog_of_war": "🕵️ Fog of War & Deception",
            "escalation_vectors": "⚠️ Hidden Escalation Vectors",
            "blind_spots": "👁️ Blind Spots / Missing Intelligence",
        }
    else:
        labels = {
            "bluf": "🔵 BLUF",
            "motive_and_rationality": "🧠 Motive & Rationality",
            "stabilizing_factors": "🛡️ Stabilizing Factors",
            "watchlist": "📡 Watchlist for the Next 24H",
        }

    for key, label in labels.items():
        val = result.get(key, "N/A")
        if isinstance(val, list):
            val = "\n".join(f"  - {v}" for v in val)
        lines.append(f"{label}\n{val}\n")

    return "\n".join(lines).strip()


def _do_rollup(chunks: list, llm, date: str, team: str,
                system_prompt_body: str, human_prompt_intro: str,
                delete_after: bool = True) -> dict:
    """
    Generic rollup: build prompts from chunks, call LLM, write summary to DB.
    If delete_after=True, deletes consumed center intel after writing.
    """
    chunk_summaries = [_build_chunk_topic_parts(c) for c in chunks]
    confidence_hints = {c.get('source_confidence') for c in chunks if c.get('source_confidence')}
    confidence_block = "\n".join(sorted(confidence_hints)) if confidence_hints else "  (no source records found)"
    total_raw = sum(c['raw_count'] for c in chunks)

    system_prompt = f"""You are the 'Nexus {_team_label(team)} AI'.
{system_prompt_body}

Reference confidence anchors for known sources (do not exceed these):
{confidence_block}

Return a JSON with a "content" field containing the full briefing text (300-500 words)."""

    human_prompt = f"""{human_prompt_intro} ({len(chunks)} chunks, {total_raw} total items):

"""
    human_prompt += "\n\n".join(chunk_summaries)
    human_prompt += "\n\nGenerate the briefing."

    print(f"[Summarize] Rolling up {len(chunks)} chunk(s) ({total_raw} items) for {date}...")

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])
        raw = _extract_json(response)
        result = json.loads(raw)
        content = result.get("content", "")

        source_hint = ",".join(sorted(set(
            sv.get("source", "").strip()
            for c in chunks
            for td in (json.loads(c.get('source_views') or '[]') if c.get('source_views') else [])
            for sv in (td.get('source_views') or [])
            if sv.get("source", "").strip()
        )))

        summary_id = insert_daily_summary(
            date=date,
            content=content,
            source_hint=source_hint,
            raw_count=total_raw,
            team=team,
        )

        deleted = 0
        if delete_after and team != "memory":
            deleted = delete_center_intel_by_date(date, team=team)

        print(f"[Summarize] Summary id={summary_id} for {date} (team={team}, {total_raw} items) | deleted {deleted} raw entries.")
        return {"date": date, "summary_id": summary_id, "deleted": deleted, "content": content, "team": team}

    except Exception as e:
        print(f"[Summarize] Error generating summary ({date}, team={team}): {e}")
        return {"date": date, "summary_id": None, "error": str(e), "team": team}


def _do_joint_rollup(target_date: str, chunks: list, llm) -> dict:
    """
    Red and blue read the SAME set of chunks (no team filter applied).
    Each team gets its own structured briefing; chunks are deleted only once
    after both reports are written.
    """
    # Build the shared intel text block once
    chunk_summaries = [_build_chunk_topic_parts(c) for c in chunks]
    confidence_hints = {c.get('source_confidence') for c in chunks if c.get('source_confidence')}
    confidence_block = "\n".join(sorted(confidence_hints)) if confidence_hints else "  (no source records found)"
    total_raw = sum(c['raw_count'] for c in chunks)

    system_prompt_base = f"""Reference confidence anchors for known sources (do not exceed these):
{confidence_block}"""

    human_intel = (
        f"Intelligence chunks for {target_date} ({len(chunks)} chunks, {total_raw} total items):\n\n"
        + "\n\n".join(chunk_summaries)
    )

    # ── Red Team rollup ───────────────────────────────────────────────────────
    red_result = _do_red_rollup(system_prompt_base, human_intel, llm, target_date, chunks)
    red_id = red_result.get("summary_id")

    # ── Blue Team rollup ──────────────────────────────────────────────────────
    blue_result = _do_blue_rollup(system_prompt_base, human_intel, llm, target_date, chunks)
    blue_id = blue_result.get("summary_id")

    # ── Delete consumed chunks once ───────────────────────────────────────────
    from database.crud import delete_center_intel_by_date
    deleted = delete_center_intel_by_date(target_date, team=None)
    print(f"[Summarize] Deleted {deleted} raw entries after joint rollup.")

    return {
        "date": target_date,
        "red_summary_id": red_id,
        "blue_summary_id": blue_id,
        "red_content": red_result.get("content"),
        "blue_content": blue_result.get("content"),
        "deleted": deleted,
        "team": "joint",
    }


def _do_raw_joint_rollup(target_date: str, intel_list: list, llm) -> dict:
    """Fallback: no chunks exist, roll up directly from raw center intel (joint red+blue)."""
    combined = "\n".join(
        f"- [{item.get('intel_type','mixed')}] {item.get('title','No title')}: "
        f"{item.get('synthesis', item.get('summary',''))}"
        for item in intel_list
    )
    total = len(intel_list)
    print(f"[Summarize] Raw fallback: processing {total} items for {target_date}...")

    system_prompt_base = ""

    human_intel = (
        f"Raw intelligence items for {target_date} ({total} items):\n\n{combined}"
    )

    red_result = _do_red_rollup(system_prompt_base, human_intel, llm, target_date, [])
    blue_result = _do_blue_rollup(system_prompt_base, human_intel, llm, target_date, [])

    red_id = red_result.get("summary_id")
    blue_id = blue_result.get("summary_id")

    from database.crud import delete_center_intel_by_date
    deleted = delete_center_intel_by_date(target_date, team=None)

    return {
        "date": target_date,
        "red_summary_id": red_id,
        "blue_summary_id": blue_id,
        "red_content": red_result.get("content"),
        "blue_content": blue_result.get("content"),
        "deleted": deleted,
        "team": "joint",
    }


def _do_red_rollup(system_prompt_base: str, human_intel: str, llm,
                   target_date: str, chunks: list) -> dict:
    """Generate the Red Team dossier (4-section structured briefing)."""
    system_prompt = f"""You are the 'Nexus Red Team AI'.
Core mindset: suspect everything. Look for systemic risks, logical holes, and worst-case scenarios.

Your task is to distill today's intelligence into ONE Red Team Dossier with the following four sections:

1. BLUF (Bottom Line Up Front)
   State in ONE sentence the single greatest geo-physical risk exposed by today's intel stream.
   Example: "Islamabad diplomatic channels are very likely a strategic cover for military operations; the Persian Gulf conflict countdown is not lifted."

2. Fog of War & Deception
   Apply adversarial inference to every contradiction in the intel.
   Example: if the intel says "Trump said Vance had departed" but Vance had not, Red Team interprets this as: "This is almost certainly not a miscommunication — the US is most likely running an information warfare test, or buying time for the third carrier strike group's deployment window."

3. Hidden Escalation Vectors
   Extract seemingly innocuous intel fragments that could trigger chain reactions.
   Example: "CENTCOM's emphasis on '27 vessels intercepted' could trigger Iran's asymmetric maritime retaliation within 48 hours."

4. Blind Spots / Missing Intelligence
   List intelligence that SHOULD have appeared but did NOT. What should be there but isn't?
   Example: "If major troop movements occurred, why is there no airspace restriction coverage?"

Return a JSON:
{{
    "bluf": "One sentence — the single most critical threat judgement.",
    "fog_of_war": "2-3 paragraphs. Identify contradictions, apply adversarial/malicious interpretation. Do not give the benefit of the doubt.",
    "escalation_vectors": "2-3 specific escalation paths that could spiral out of control, each 1-2 sentences.",
    "blind_spots": "List of 2-4 'should have been here but is missing' intelligence gaps. Flag what could be hidden in those blind spots."
}}

{system_prompt_base}"""

    human_prompt = f"""{human_intel}

Generate the Red Team Dossier."""

    return _call_rollup_llm(system_prompt, human_prompt, llm, target_date, team="red")


def _do_blue_rollup(system_prompt_base: str, human_intel: str, llm,
                    target_date: str, chunks: list) -> dict:
    """Generate the Blue Team brief (4-section structured briefing)."""
    system_prompt = f"""You are the 'Nexus Blue Team AI'.
Core mindset: constructive, logically consistent. Seek each side's bottom lines and paths to de-escalation.

Your task is to distill today's intelligence into ONE Blue Team Brief with the following four sections:

1. BLUF (Baseline Fact Determination)
   Strip away rhetoric and political spin. What PHYSICAL facts actually occurred today?
   Example: "Despite escalatory rhetoric, neither side fired the first shot in the Persian Gulf; Pakistan's mediation channel remains active."

2. Motive & Rationality
   Find coherent, rational博弈 motivations behind seemingly chaotic events.
   Example: "Iran's insistence on 'no blockade lift, no negotiation' is standard diplomatic posturing; the Vance travel delay may reflect internal reassessment of offering a partial blockade lift in exchange for Iranian presidential attendance at talks."

3. Stabilizing Factors
   List any buffer signals, de-escalation signals, or third-party mediation progress present in today's intel.

4. Watchlist for the Next 24H
   Provide objective, falsifiable indicators to watch.
   Example: "Watch whether the Pakistani Foreign Ministry issues an official confirmation statement within 24 hours; track AIS (ship tracking) data for any non-military tanker resuming transit through the contested waters."

Return a JSON:
{{
    "bluf": "2-3 sentences. Physical facts only. Strip political spin.",
    "motive_and_rationality": "2-3 paragraphs. Assign rational博弈 motivations to each major actor. Do not assume irrationality without evidence.",
    "stabilizing_factors": "2-4 specific stabilizing signals present in today's intel. Be precise and evidence-based.",
    "watchlist": "3-5 specific, falsifiable indicators to monitor in the next 24 hours. Each item should be a concrete observable event or data point."
}}

{system_prompt_base}"""

    human_prompt = f"""{human_intel}

Generate the Blue Team Brief."""

    return _call_rollup_llm(system_prompt, human_prompt, llm, target_date, team="blue")


def _extract_json(response) -> str:
    """Pull JSON string out of an LLM response, handling all common wrapper formats."""
    raw = response.content

    if isinstance(raw, dict):
        raw = raw.get("text", "") or str(raw)
    elif isinstance(raw, list):
        part = raw[0]
        raw = part['text'] if isinstance(part, dict) and 'text' in part else str(part)
    elif hasattr(raw, 'text'):
        raw = raw.text

    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    return raw


# ─────────────────────────────────────────────────────────────────
# Memory sidebar chunk processing
# ─────────────────────────────────────────────────────────────────

MEMORY_CHUNK_SIZE = 50


def memory_chunks_summary_node(state: AgentState) -> dict:
    """
    Drain ALL unsummarized sidebar memories into chunk summaries.
    Internally loops: each iteration consumes up to MEMORY_CHUNK_SIZE items.
    On success, marks those memories as summarized=1 (frontend hides them).

    Pass state = {} (chunk_index is ignored internally).
    Returns total chunks processed and their IDs.
    """
    llm = get_llm()

    total = get_memory_unsummarized_count()
    if total == 0:
        return {"chunks": 0, "chunk_ids": [], "source": "memory"}

    chunks_processed = 0
    chunk_ids = []
    chunk_index = _get_next_memory_chunk_index()

    while True:
        memories = get_memory_unsummarized_batch(limit=MEMORY_CHUNK_SIZE)
        if not memories:
            break

        combined = "\n".join(
            f"[{m.get('created_at', 'unknown')}] [team:{m.get('team', 'general')}] "
            f"[src:{m.get('source', 'unknown')}] {m.get('author', 'No title')}: {m.get('context', '')}"
            for m in memories
        )

        system_prompt = """You are the 'Nexus Sidebar Memory Analyst'.
You are analyzing a batch of manually curated sidebar intelligence memories.

For each entry you receive:
- [timestamp] [team:X] [src:Y] Title: Context

Your job is to distill these memories into a structured briefing. Return a JSON:

{
    "topics": "comma-separated topic tags",
    "topic_details": [
        {
            "topic": "short topic name",
            "brief_analysis": "2-3 sentence summary of the key intel in this topic",
            "source_views": [
                {
                    "source": "memory title or memory id",
                    "claim": "specific key finding or claim from this memory",
                    "time": "timestamp if available, otherwise empty string"
                }
            ]
        }
    ]
}

Guidelines:
- Identify distinct topics within this batch (aim for 3-6 topics).
- For each topic, extract the most impactful claims from the source memories.
- Each topic's source_views should cite the specific memory titles/ids that support it.
- Include timestamps whenever the source material provides them.
- Keep brief_analysis concise (2-3 sentences per topic).
- Output the overall topics field as a plain comma-separated list of topic names."""

        human_prompt = f"""Sidebar memory chunk {chunk_index} ({len(memories)} entries):

{combined}

Generate the chunk briefing."""

        print(f"[MemChunk] Processing {len(memories)} memories for chunk {chunk_index}...")

        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ])
            raw = _extract_json(response)
            result = json.loads(raw)
            topics = result.get("topics", "")
            topic_details = result.get("topic_details", [])

            brief_parts = [f"[{td.get('topic', 'Unknown')}] {td.get('brief_analysis', '')}"
                           for td in topic_details]
            brief_analysis = " | ".join(brief_parts)
            source_views = json.dumps(topic_details, ensure_ascii=False)

            chunk_id = insert_chunk_summary(
                date="memory", chunk_index=chunk_index, raw_count=len(memories),
                topics=topics, brief_analysis=brief_analysis,
                source_views=source_views, source_confidence=None, team="memory",
            )
            mark_memory_summarized([m["id"] for m in memories])
            print(f"[MemChunk] Chunk {chunk_index} done, chunk_id={chunk_id}, "
                  f"{len(memories)} memories marked summarized.")
            chunk_ids.append(chunk_id)
            chunk_index += 1
            chunks_processed += 1

        except Exception as e:
            print(f"[MemChunk] Error processing chunk {chunk_index}: {e}")
            return {"chunks": chunks_processed, "chunk_ids": chunk_ids,
                    "source": "memory", "error": str(e)}

    return {"chunks": chunks_processed, "chunk_ids": chunk_ids, "source": "memory"}


def summarize_memory_node() -> dict:
    """
    Roll up all memory sidebar chunks into a single briefing.
    Uses the dedicated DAILY_ROLLUP LLM. Writes to daily_summary with date='memory'.
    After successful rollup, deletes all memory chunks so next day starts fresh.
    """
    llm = get_daily_rollup_llm()
    chunks = get_memory_chunks()

    if not chunks:
        print(f"[Summarize] No memory chunks found, skipping.")
        return {"date": "memory", "summary_id": None}

    result = _do_memory_rollup(chunks, llm)

    # Clean up chunks after successful rollup
    if result.get("summary_id"):
        deleted = delete_memory_chunks()
        print(f"[Summarize] Memory rollup done, deleted {deleted} chunk(s).")
        result["chunks_deleted"] = deleted

    return result


def _do_memory_rollup(chunks: list, llm) -> dict:
    """Thin wrapper: roll up memory sidebar chunks."""
    return _do_rollup(
        chunks, llm,
        date="memory",
        team="memory",
        system_prompt_body=(
            "Your task is to distill ALL sidebar memory chunks into ONE concise briefing capturing key intelligence threads.\n\n"
            "The briefing should cover:\n"
            "1. Key intelligence threads / recurring themes\n"
            "2. Notable items requiring attention\n"
            "3. Overall memory/sidebar sentiment\n\n"
            "Keep it to 300-500 words. Write in an executive briefing style."
        ),
        human_prompt_intro="Memory chunks",
    )
