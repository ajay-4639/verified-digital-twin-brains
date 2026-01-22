
import asyncio
import sys
import os
import json
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

# Mock Supabase
from unittest.mock import MagicMock
sys.modules["modules.observability"] = MagicMock()
sys.modules["modules.observability"].supabase = MagicMock()

# Import after mocking
from modules._core.interview_controller import InterviewController, InterviewStage
from modules._core.registry_loader import get_specialization_manifest
from modules._core.host_engine import get_next_slot, get_next_question

async def simulate_interview():
    print("Starting Interview Simulation...")
    
    # 1. Load Policy
    manifest = get_specialization_manifest("vanilla")
    policy_path = manifest.get("host_policy")
    full_path = os.path.join(os.getcwd(), "backend", policy_path)
    with open(full_path, "r", encoding="utf-8") as f:
        host_policy = json.load(f)
        
    print(f"Policy Loaded: {len(host_policy.get('required_slots', []))} required slots")
    
    # 2. Initialize State
    filled_slots = {}
    session = {
        "id": "sim_session",
        "stage": InterviewStage.DEEP_INTERVIEW.value,
        "turn_count": 0,
        "asked_template_ids": []
    }
    
    # 3. Simulate Turns
    max_turns = 15
    for turn in range(max_turns):
        print(f"\n--- Turn {turn + 1} ---")
        
        # Get Next Slot
        next_slot = get_next_slot(host_policy, filled_slots)
        if not next_slot:
            print("Interview Complete! (No more slots)")
            break
            
        print(f"Target Slot: {next_slot['slot_id']}")
        
        # Get Question
        q = get_next_question(host_policy, filled_slots, "vanilla", session["asked_template_ids"])
        question = q.get("question") if q else "Generic Question?"
        print(f"Host: {question}")
        
        # Simulate User Answer
        user_answer = f"My {next_slot['slot_id']} is very detailed and substantive."
        print(f"User: {user_answer}")
        
        # Simulate Extraction (Success)
        print(f"Scribe: Extracted data for {next_slot['slot_id']}")
        filled_slots[next_slot['slot_id']] = "filled"
        
        # Simulate Context Update
        session["asked_template_ids"].append(q.get("template_id"))
        
    # 4. Verify Result
    if not get_next_slot(host_policy, filled_slots):
        print("\nTEST PASSED: All slots filled.")
    else:
        print("\nTEST FAILED: Slots remaining.")

if __name__ == "__main__":
    asyncio.run(simulate_interview())
