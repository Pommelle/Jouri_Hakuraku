import os
import sys

# Add parent directory to path to import database module
sys.path.append(os.path.join(os.path.dirname(__file__)))
from database.crud import insert_processed_intel, insert_memory, insert_raw_data

def seed_database():
    print("Seeding database with mock data for central UI testing...")
    
    # Insert shared memories to the general memory bank
    insert_memory("general", "Project Titan", "A suspected new AI model being trained by a major tech company. We need to find vulnerabilities and monitor for leaps in architecture.", source="Internal Intel")
    insert_memory("general", "Zero-Day vulnerability", "Recent chatter indicates a potential vulnerability in widely used authentication library. High risk of exploitation.", source="Dark Web Monitor")
    
    # Insert raw data (mock)
    raw_id_1 = insert_raw_data("discord_selfbot", "Just heard a huge leak about Project Titan. It might be AGI.", "@analyst", intel_type="news")
    
    # Insert central processed intel
    insert_processed_intel(
        raw_data_id=raw_id_1,
        title="Executive Summary: Project Titan Rumors",
        summary="A leaker posted about Project Titan potentially reaching AGI capabilities.",
        red_team_analysis="Highly skeptical. 'AGI' is an overused buzzword to gain followers.",
        blue_team_analysis="We should monitor this. Even if exaggerated, a major architectural leap from this company could disrupt our defensive AI models.",
        synthesis="The claim is likely exaggerated for clout, but given the entity involved, we must track related repositories for sudden architectural shifts. Both Red and Blue teams acknowledge the low immediate risk but high potential impact.",
        tags="AGI, Rumor",
        team_assignment="center",
        intel_type="news",
        batch_count=1
    )

    print("Seeding complete.")

if __name__ == "__main__":
    seed_database()
