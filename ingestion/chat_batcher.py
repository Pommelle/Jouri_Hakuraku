import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.crud import (
    get_unprocessed_chat,
    get_unprocessed_chat_count,
    mark_raw_data_batch_processed,
    get_unprocessed_news,
    mark_raw_data_batch_processed as mark_news_processed,
    insert_processed_intel,
    update_raw_data_confidence,
)
from agent.graph import build_graph


CHAT_BATCH_SIZE = 30


def process_single_news(raw_item: dict):
    """
    Take a single raw news item and run it through the AI pipeline.
    Writes result to processed_intel (center, intel_type=news).
    """
    app = build_graph()
    state = {
        "raw_data_id": raw_item['id'],
        "raw_content": raw_item['content'],
        "source": raw_item['source'],
        "intel_type": "news"
    }

    try:
        result = app.invoke(state)
        
        confidence_score = result.get('confidence_score')
        confidence_rationale = result.get('confidence_rationale')
        if confidence_score is not None:
            update_raw_data_confidence(raw_item['id'], confidence_score, confidence_rationale)
        
        intel_id = insert_processed_intel(
            raw_data_id=raw_item['id'],
            title=result.get('title', 'News Intel'),
            summary=result.get('final_synthesis', ''),
            red_team_analysis=result.get('red_team_analysis', ''),
            blue_team_analysis=result.get('blue_team_analysis', ''),
            synthesis=result.get('final_synthesis', ''),
            tags=result.get('tags', ''),
            team_assignment='center',
            intel_type='news',
            batch_count=1
        )
        print(f"[NewsProcessor] Processed news id={raw_item['id']} -> intel id={intel_id}")
        mark_news_processed([raw_item['id']])
        return intel_id
    except Exception as e:
        print(f"[NewsProcessor] Error: {e}")
        return None


def process_all_pending_news():
    """Drain all unprocessed news items. Call on startup."""
    items = get_unprocessed_news(limit=50)
    if not items:
        print("[NewsProcessor] No pending news items.")
        return 0

    processed = 0
    for item in items:
        if process_single_news(item):
            processed += 1
    print(f"[NewsProcessor] Processed {processed}/{len(items)} news items.")
    return processed


def flush_chat_batch():
    """
    Check if we have enough unprocessed chat messages to flush.
    If so, combine them into a single batch and trigger AI analysis.
    Returns the processed intel_id, or None if not enough messages.
    """
    count = get_unprocessed_chat_count()

    if count < CHAT_BATCH_SIZE:
        return None

    batch = get_unprocessed_chat(limit=CHAT_BATCH_SIZE)
    if not batch:
        return None

    combined_content = "\n---\n".join([item['content'] for item in batch])
    combined_author = ", ".join(set([item['author'] for item in batch if item['author']]))
    raw_ids = [item['id'] for item in batch]

    app = build_graph()
    state = {
        "raw_data_id": raw_ids[0],
        "raw_content": combined_content,
        "source": f"discord_chat_batch({len(batch)} messages from: {combined_author})",
        "intel_type": "chat"
    }

    try:
        result = app.invoke(state)
        
        confidence_score = result.get('confidence_score')
        confidence_rationale = result.get('confidence_rationale')
        if confidence_score is not None:
            update_raw_data_confidence(raw_ids[0], confidence_score, confidence_rationale)
        
        intel_id = insert_processed_intel(
            raw_data_id=raw_ids[0],
            title=result.get('title', 'Chat Summary'),
            summary=result.get('final_synthesis', ''),
            red_team_analysis=result.get('red_team_analysis', ''),
            blue_team_analysis=result.get('blue_team_analysis', ''),
            synthesis=result.get('final_synthesis', ''),
            tags=result.get('tags', ''),
            team_assignment='center',
            intel_type='chat',
            batch_count=len(batch)
        )
        print(f"[ChatBatcher] Batch processed: {len(batch)} messages -> intel id={intel_id}")
        mark_raw_data_batch_processed(raw_ids)
        return intel_id
    except Exception as e:
        print(f"[ChatBatcher] Error processing chat batch: {e}")
        return None


def check_and_flush():
    """Lightweight check - just logs current count without building graph."""
    count = get_unprocessed_chat_count()
    print(f"[ChatBatcher] Current unprocessed chat count: {count}/{CHAT_BATCH_SIZE}")
    return count
