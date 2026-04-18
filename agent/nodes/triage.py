from agent.state import AgentState
from agent.llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage
from typing import Optional
import json
import time
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'nexus.db')

# 内存缓存：避免每次 triage 都查数据库
_cache: Optional[dict] = None
_cache_at: float = 0.0
_CACHE_TTL = 60.0  # 秒


def _load_overrides_from_db() -> dict:
    """从数据库加载 source_confidence 名单，超时后重新读取。"""
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
        pass  # 数据库未就绪时静默降级

    _cache = overrides
    _cache_at = now
    return overrides


def _invalidate_cache():
    global _cache, _cache_at
    _cache = None
    _cache_at = 0.0


def _get_source_anchor(source: str) -> Optional[float]:
    """模糊匹配来源名，返回置信度锚点，找不到返回 None。"""
    overrides = _load_overrides_from_db()
    src_lower = source.lower()
    for key, value in overrides.items():
        if key in src_lower:
            return value
    return None


def triage_node(state: AgentState) -> dict:
    """Triage the raw content to decide if it's worth processing."""
    llm = get_llm()
    
    raw_content = state.get("raw_content", "")
    source = state.get("source", "unknown")
    
    # 构建来源置信度说明片段
    anchor = _get_source_anchor(source)
    anchor_block = ""
    if anchor is not None:
        anchor_block = f"""
    KNOWN SOURCE DETECTED: "{source}"
    This source has a known reliability baseline of {anchor:.0%}.
    Use this as a HARD CEILING - your confidence_score MUST NOT exceed {anchor:.0%} for this source.
    Adjust downward only if the specific content contains red flags (contradicts facts, inflammatory, etc.).
    """
    else:
        anchor_block = """
    SOURCE NOT IN DATABASE: Apply general guidelines only. Default to 0.5 if no red/green flags.
    """

    system_prompt = f"""
    You are an elite cyber threat intelligence analyst (Code Name: Hakuraku).
    Your task is to triage incoming data streams and filter out noise (memes, casual chat, support questions).
    Only actionable intelligence, real vulnerabilities, zero-days, breaches, or significant threat actor movements should pass.
    
    You must score the relevance from 0 to 100.
    - 0-30: Pure noise, memes, casual greetings.
    - 31-59: Low value, opinions, news without indicators.
    - 60-84: High value, specific incidents, tactical updates.
    - 85-100: CRITICAL, 0-day exploits, active data leaks, APT movement.
    
    You must also score the CONFIDENCE (reliability) of the source/content from 0.0 to 1.0.
    Consider: source credibility, corroboration, factual basis, emotional tone, and potential for misinformation.
    - 0.0-0.3: Highly unreliable - unverified claims, anonymous sources, obvious lies, satirical content, or known unreliable actors.
    - 0.4-0.6: Medium reliability - single source, some ambiguity, or from a source with mixed credibility.
    - 0.7-1.0: High reliability - corroborated by multiple sources, official statements, or well-established credible outlets.
    
    Be especially skeptical of:
    - Claims that contradict well-established facts
    - Emotional or inflammatory language
    - Anonymous or unverifiable sources
    - Content from sources known for misinformation{anchor_block}
    You must also extract any Indicators of Compromise (IOCs) such as CVE IDs, IP addresses, domains, or malware names.
    
    Return your analysis in EXACTLY this JSON format (no markdown code blocks):
    {{
        "relevance_score": integer,
        "confidence_score": float,
        "triage_reason": "string: brief justification for the score",
        "confidence_rationale": "string: why you rate this source/content reliability",
        "iocs_found": ["array of strings", "empty if none"]
    }}
    """
    
    human_prompt = f"Source: {source}\nContent: {raw_content}"
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ])
    
    try:
        raw = response.content
        if isinstance(raw, list):
            part = raw[0]
            raw = part['text'] if isinstance(part, dict) and 'text' in part else str(part)
        elif hasattr(raw, 'text'):
            raw = raw.text

        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        result = json.loads(raw)
        score = result.get("relevance_score", 0)
        confidence = result.get("confidence_score", 0.5)
        
        # 强制应用来源上限（AI 偶尔会忽略指令）
        if anchor is not None and confidence > anchor:
            confidence = anchor
        
        # Threat threshold: Auto-discard anything below 60
        triage_result = True if score >= 60 else False
        
        final_state = {
            "triage_result": triage_result,
            "triage_reason": result.get("triage_reason", "Analysis complete"),
            "confidence_rationale": result.get("confidence_rationale", ""),
            "relevance_score": score,
            "confidence_score": confidence,
            "iocs_found": result.get("iocs_found", [])
        }

        anchor_info = f" (anchor: {anchor:.0%})" if anchor is not None else ""
        print(f"[Triage] Score: {score}/100 | Confidence: {confidence:.0%}{anchor_info} | Pass: {triage_result} | IOCs: {len(final_state['iocs_found'])}")
        return final_state
        
    except Exception as e:
        print(f"Error parsing triage output: {e}\nRaw response: {raw}")
        # Default fail-safe for critical errors
        return {"triage_result": False, "triage_reason": "Failed to parse LLM triage output", "confidence_rationale": "", "relevance_score": 0, "confidence_score": 0.0, "iocs_found": []}
