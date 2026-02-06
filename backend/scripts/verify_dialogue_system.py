import asyncio
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.agent import run_agent_stream
from langchain_core.messages import HumanMessage

async def test_dialogue_orchestrator():
    load_dotenv()
    
    twin_id = "c3cd4ad0-d4cc-4e82-a020-82b48de72d42"
    
    test_cases = [
        {
            "name": "SMALLTALK",
            "query": "Hello there! How are you doing today?"
        },
        {
            "name": "SPECIFIC_WITH_EVIDENCE",
            "query": "What are your core principles regarding startup investing?"
        },
        {
            "name": "SPECIFIC_WITHOUT_EVIDENCE",
            "query": "What is your secret recipe for the best lasagna?"
        }
    ]
    
    for case in test_cases:
        print(f"\n" + "="*50)
        print(f"TESTING {case['name']}: {case['query']}")
        print("="*50)
        
        try:
            async for event in run_agent_stream(twin_id, case['query']):
                # event is a dict {node_name: {updates}}
                for node_name, data in event.items():
                    print(f"\n[NODE: {node_name}]")
                    if "reasoning_history" in data:
                        print(f"  Reasoning: {data['reasoning_history'][-1]}")
                    if "dialogue_mode" in data:
                        print(f"  Mode: {data['dialogue_mode']}")
                    if "requires_evidence" in data:
                        print(f"  Requires Evidence: {data['requires_evidence']}")
                    if "requires_teaching" in data:
                        print(f"  Requires Teaching: {data['requires_teaching']}")
                    if "messages" in data:
                        last_msg = data["messages"][-1]
                        content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                        print(f"  Response Preview: {content[:200]}...")
                    if "planning_output" in data:
                        import json
                        print(f"  Plan: {json.dumps(data['planning_output'], indent=2)}")
                    # Print anything else for deep debug
                    other_keys = [k for k in data.keys() if k not in ["reasoning_history", "dialogue_mode", "messages", "planning_output", "requires_evidence", "requires_teaching"]]
                    if other_keys:
                        print(f"  Other Data: {other_keys}")
        except Exception as e:
            print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_dialogue_orchestrator())
