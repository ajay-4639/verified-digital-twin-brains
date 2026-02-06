import asyncio
import os
import sys
import json
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from modules.agent import run_agent_stream
from modules.observability import supabase
from langchain_core.messages import HumanMessage

async def verify_vc_teaching_flow():
    load_dotenv()
    twin_id = "c3cd4ad0-d4cc-4e82-a020-82b48de72d42"
    
    # Fetch tenant_id once
    try:
        t_res = supabase.table("twins").select("tenant_id").eq("id", twin_id).single().execute()
        tenant_id = t_res.data.get("tenant_id")
    except Exception as e:
        print(f"Error fetching tenant_id: {e}")
        return

    test_scenarios = [
        {
            "query": "What is our specific criteria for Series A fintech investments in emerging markets?",
            "answer": "For Series A fintech in emerging markets, we require at least $100k MRR, full regulatory license, and a founding team with 5+ years domain experience.",
            "user_query": "I have a fintech in Nigeria with $120k MRR and a central bank license. Do I meet your criteria?",
            "keyword": "$100k MRR"
        },
        {
            "query": "What is our stance on investing in solopreneurs for B2B SaaS?",
            "answer": "We generally prefer co-founding teams, but we will invest in solopreneurs for B2B SaaS if the founder has at least 2 successful previous exits.",
            "user_query": "I am a solo founder building a CRM, but this is my 3rd startup (2 previous exits). Will you talk to me?",
            "keyword": "2 successful previous exits"
        },
        {
            "query": "What valuation multiples do we target for early-stage AI startups?",
            "answer": "For early-stage AI startups, we typically target valuation multiples between 10x and 15x ARR, depending on proprietary data moats.",
            "user_query": "We are an AI startup with $1M ARR and a unique dataset. What valuation multiple should we expect from you?",
            "keyword": "10x and 15x ARR"
        },
        {
            "query": "What is our standard due diligence timeline?",
            "answer": "Our standard due diligence process is aggressive but thorough, taking exactly 4 weeks from term sheet to close.",
            "user_query": "How long does your due diligence usually take if we sign a term sheet today?",
            "keyword": "4 weeks"
        },
        {
            "query": "Do we always require a board seat for our investments?",
            "answer": "We only require a board seat for investment rounds exceeding $3 million. For smaller checks, we take board observer rights.",
            "user_query": "We are raising a $2M seed round. Will you require a board seat if you invest?",
            "keyword": "rounds exceeding $3 million"
        }
    ]

    for i, scenario in enumerate(test_scenarios):
        print(f"\n--- [LOOP {i+1}] Topic: {scenario['query'][:30]}... ---")
        
        # 1. Trigger Teaching Mode
        found_teaching = False
        async for event in run_agent_stream(twin_id, scenario["query"]):
            for node, data in event.items():
                if node == "gate" and data.get("dialogue_mode") == "TEACHING":
                    found_teaching = True
        
        if found_teaching:
            print(f"PASS: Teaching mode triggered for loop {i+1}.")
        else:
            print(f"INFO: Teaching mode not triggered (context might already exist). Proceeding.")

        # 2. Ingest "Active" Belief (Training)
        try:
            supabase.table("owner_beliefs").insert({
                "tenant_id": tenant_id,
                "twin_id": twin_id,
                "topic_normalized": scenario["query"].lower()[:50],
                "memory_type": "belief",
                "value": scenario["answer"],
                "status": "active",
                "provenance": {"session_type": "automated_test", "loop": i+1}
            }).execute()
            print(f"PASS: Belief ingested as 'active'.")
        except Exception as e:
            print(f"FAIL: Ingestion failed: {e}")
            continue

        # 3. Test as User (Founder)
        print(f"Founder Query: '{scenario['user_query']}'")
        found_correct_answer = False
        async for event in run_agent_stream(twin_id, scenario["user_query"]):
            for node, data in event.items():
                if node == "realizer":
                    msg = data["messages"][-1]
                    content = msg.content
                    print(f"Response: {content}")
                    if scenario["keyword"] in content:
                        found_correct_answer = True
        
        if found_correct_answer:
            print(f"SUCCESS: Loop {i+1} completed with conversational and accurate response.")
        else:
            print(f"FAILURE: Loop {i+1} response did not contain expected terms.")

if __name__ == "__main__":
    asyncio.run(verify_vc_teaching_flow())

if __name__ == "__main__":
    asyncio.run(verify_vc_teaching_flow())
