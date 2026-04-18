from typing import TypedDict, Optional, List

class AgentState(TypedDict):
    raw_data_id: int
    raw_content: str
    source: str

    intel_type: Optional[str]  # 'news' | 'chat' | 'mixed'
    triage_result: Optional[bool]
    triage_reason: Optional[str]
    confidence_score: Optional[float]
    confidence_rationale: Optional[str]

    red_team_analysis: Optional[str]
    blue_team_analysis: Optional[str]

    team_assignment: Optional[str]
    title: Optional[str]
    tags: Optional[str]

    processed_intel_id: Optional[int]
    memory_context: Optional[str]
