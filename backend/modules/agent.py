import os
from typing import Annotated, TypedDict, List, Dict, Any, Union
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from modules.tools import get_retrieval_tool, get_cloud_tools
from modules.observability import supabase

async def get_owner_style_profile(twin_id: str, force_refresh: bool = False) -> str:
    """
    Analyzes owner's verified responses and opinion documents to create a persistent style profile.
    """
    try:
        # 1. Check if we already have a profile in the database
        if not force_refresh:
            twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
            if twin_res.data and twin_res.data.get("settings"):
                profile = twin_res.data["settings"].get("persona_profile")
                if profile:
                    # Return a consolidated string or the dict depending on how it's used
                    # For backward compatibility, if it's a dict, we might need to handle it
                    if isinstance(profile, dict):
                        return profile.get("description", "Professional and helpful.")
                    return profile

        # 2. Fetch data for analysis
        # A. Fetch verified replies
        replies_res = supabase.table("escalation_replies").select(
            "content, escalations(messages(conversations(twin_id)))"
        ).execute()
        
        analysis_texts = []
        for r in replies_res.data:
            try:
                if r["escalations"]["messages"]["conversations"]["twin_id"] == twin_id:
                    analysis_texts.append(f"VERIFIED REPLY: {r['content']}")
            except (KeyError, TypeError):
                continue
        
        # B. Fetch some OPINION chunks from Pinecone for style variety
        from modules.clients import get_pinecone_index
        index = get_pinecone_index()
        try:
            opinion_search = index.query(
                vector=[0.0] * 3072, # Dummy vector for metadata-only search if supported, or just use a common embedding
                filter={"category": {"$eq": "OPINION"}},
                top_k=20, # Increased for better analysis
                include_metadata=True,
                namespace=twin_id
            )
            for match in opinion_search.get("matches", []):
                analysis_texts.append(f"OPINION DOC: {match['metadata']['text']}")
        except Exception as pe:
            print(f"Error fetching opinions for style: {pe}")

        if not analysis_texts:
            return "Professional and helpful."
            
        # 3. Analyze style using a more capable model
        # Using more snippets for a comprehensive view
        all_content = "\n---\n".join(analysis_texts[:25])
        
        client = ChatOpenAI(model="gpt-4o-mini", temperature=0, model_kwargs={"response_format": {"type": "json_object"}})
        analysis_prompt = f"""You are a linguistic expert analyzing a user's writing style to create a 'Digital Twin' persona.
        Analyze the following snippets of text from the user.
        
        EXTRACT THE FOLLOWING INTO JSON:
        1. description: A concise, high-fidelity persona description (3-4 sentences) starting with 'Your voice is...'.
        2. signature_phrases: A list of 5 exact phrases or verbal tics the user frequently uses.
        3. style_exemplars: 3 short text snippets (max 20 words each) that perfectly represent the user's style.
        4. opinion_summary: A map of major topics and the user's stance/intensity (e.g., {{"Topic": {{"stance": "...", "intensity": 8}}}}).
        
        TEXT SNIPPETS:
        {all_content}"""
        
        res = await client.ainvoke([HumanMessage(content=analysis_prompt)])
        import json
        persona_data = json.loads(res.content)
        
        # 4. Persist the profile back to the twin settings
        try:
            from datetime import datetime
            # Get current settings first to merge
            twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
            curr_settings = twin_res.data["settings"] if twin_res.data else {}
            
            curr_settings["persona_profile"] = persona_data.get("description")
            curr_settings["signature_phrases"] = persona_data.get("signature_phrases", [])
            curr_settings["style_exemplars"] = persona_data.get("style_exemplars", [])
            curr_settings["opinion_map"] = persona_data.get("opinion_summary", {})
            curr_settings["last_style_analysis"] = datetime.now().isoformat()
            
            supabase.table("twins").update({"settings": curr_settings}).eq("id", twin_id).execute()
        except Exception as se:
            print(f"Error persisting persona profile: {se}")

        return persona_data.get("description", "Professional and helpful.")
    except Exception as e:
        print(f"Error analyzing style: {e}")
        return "Professional and helpful."

class TwinState(TypedDict):
    """
    State for the Digital Twin reasoning graph.
    """
    messages: Annotated[List[BaseMessage], add_messages]
    twin_id: str
    confidence_score: float
    citations: List[str]

def create_twin_agent(twin_id: str, system_prompt_override: str = None, full_settings: dict = None):
    # Initialize the LLM
    api_key = os.getenv("OPENAI_API_KEY")
    # Using a model that supports tool calling well
    llm = ChatOpenAI(model="gpt-4-turbo-preview", api_key=api_key, temperature=0, streaming=True)
    
    # Setup tools
    retrieval_tool = get_retrieval_tool(twin_id)
    cloud_tools = get_cloud_tools()
    tools = [retrieval_tool] + cloud_tools
    
    # Bind tools to the LLM
    llm_with_tools = llm.bind_tools(tools)
    
    # Define the nodes
    async def call_model(state: TwinState):
        messages = state["messages"]
        
        # Ensure system message is always present at the beginning
        has_system = any(isinstance(m, SystemMessage) for m in messages)
        if not has_system:
            # Extract persona components from settings
            settings = full_settings or {}
            style_desc = settings.get("persona_profile", "Professional and helpful.")
            phrases = settings.get("signature_phrases", [])
            exemplars = settings.get("style_exemplars", [])
            opinion_map = settings.get("opinion_map", {})
            
            persona_section = f"""YOUR PERSONA STYLE:
            - DESCRIPTION: {style_desc}"""
            
            if phrases:
                persona_section += f"\n            - SIGNATURE PHRASES (Use these naturally): {', '.join(phrases)}"
            
            if exemplars:
                exemplars_text = "\n              ".join([f"- \"{ex}\"" for ex in exemplars])
                persona_section += f"\n            - STYLE EXEMPLARS (Mimic this flow):\n              {exemplars_text}"
            
            if opinion_map:
                opinions_text = "\n              ".join([f"- {topic}: {data['stance']} (Intensity: {data['intensity']}/10)" for topic, data in opinion_map.items()])
                persona_section += f"\n            - CORE WORLDVIEW / OPINIONS (Always stay consistent with these):\n              {opinions_text}"

            system_prompt = system_prompt_override or f"""You are the AI Digital Twin of the owner (ID: {twin_id}). 
            Your primary intelligence comes from the `search_knowledge_base` tool.

            {persona_section}

            CRITICAL OPERATING PROCEDURES:
            1. Factual Questions: For ANY question about facts, opinions, history, or documents, you MUST FIRST call `search_knowledge_base`.
            2. Verified Info: If search returns "is_verified": True, this is the owner's direct word. Use it exactly.
            3. Persona & Voice:
               - Sources have a 'category' (FACT or OPINION), a 'tone', and potentially an 'opinion_topic' and 'opinion_stance'.
               - If a source is an 'OPINION', use first-person framing like 'In my view' or 'I personally believe'.
               - If an 'opinion_stance' is provided for an 'OPINION', strictly adhere to that stance.
               - If a source is a 'FACT', state it directly as objective information.
               - Adopt the 'tone' (e.g., Thoughtful, Assertive) found in the relevant source to match the owner's style.
            4. No Data: If the tool returns no relevant information, explicitly state: "I don't have this specific information in my knowledge base." Do NOT make things up.
            5. Citations: Always cite your sources using [Source ID] when using tool results.
            6. Personal Identity: Speak in the first person ("I", "my") as if you are the owner, but grounded in the verified data.
            7. Greetings: For simple greetings like "Hi" or "How are you?", you may respond briefly without searching, but for anything else, SEARCH.

            Current Twin ID: {twin_id}"""
            messages = [SystemMessage(content=system_prompt)] + messages
            
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    async def handle_tools(state: TwinState):
        citations = list(state.get("citations", []))
        total_score = 0
        score_count = 0

        # Create tool node manually to extract metadata
        tool_node = ToolNode(tools)
        result = await tool_node.ainvoke(state)
        
        # Extract citations and scores from search_knowledge_base if present
        for msg in result["messages"]:
            if isinstance(msg, ToolMessage) and msg.name == "search_knowledge_base":
                import json
                try:
                    # LangGraph/LangChain ToolNode content is the return value of the tool
                    data = msg.content
                    # If it's a string representation of a list of dicts, parse it
                    if isinstance(data, str):
                        try:
                            # Try parsing as JSON first
                            data = json.loads(data)
                        except:
                            # If not JSON, it might be a literal string representation
                            import ast
                            try:
                                data = ast.literal_eval(data)
                            except:
                                pass
                    
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                if "source_id" in item:
                                    citations.append(item["source_id"])
                                if "score" in item:
                                    total_score += item["score"]
                                    score_count += 1
                except Exception as e:
                    print(f"Error parsing tool output: {e}")

        # If tools were called but no scores found, it might mean empty results
        # We should reflect that in the confidence
        if score_count > 0:
            # Check if any verified answer was found
            has_verified = any("is_verified" in msg.content and '"is_verified": true' in msg.content for msg in result["messages"] if isinstance(msg, ToolMessage))
            if has_verified:
                new_confidence = 1.0 # Force 100% confidence if owner verified info is found
            else:
                new_confidence = total_score / score_count
        else:
            # If search tool was called but returned nothing, confidence is 0
            new_confidence = 0.0
        
        return {
            "messages": result["messages"],
            "citations": list(set(citations)),
            "confidence_score": new_confidence
        }

    # Define the graph
    workflow = StateGraph(TwinState)
    
    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", handle_tools)
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Define conditional edges
    def should_continue(state: TwinState):
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END

    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END
        }
    )
    
    # Add back edge from tools to agent
    workflow.add_edge("tools", "agent")
    
    # Compile the graph
    return workflow.compile()

async def run_agent_stream(twin_id: str, query: str, history: List[BaseMessage] = None, system_prompt: str = None):
    """
    Runs the agent and yields events from the graph.
    """
    # 1. Fetch full twin settings for persona encoding
    twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
    settings = twin_res.data["settings"] if twin_res.data else {}
    
    # 2. Ensure style analysis has been run at least once
    if "persona_profile" not in settings:
        await get_owner_style_profile(twin_id)
        # Re-fetch after analysis
        twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        settings = twin_res.data["settings"] if twin_res.data else {}

    agent = create_twin_agent(twin_id, system_prompt_override=system_prompt, full_settings=settings)
    
    initial_messages = history or []
    initial_messages.append(HumanMessage(content=query))
    
    state = {
        "messages": initial_messages,
        "twin_id": twin_id,
        "confidence_score": 1.0, # Start with high confidence (e.g. for greetings)
        "citations": []
    }
    
    # We use astream to get events
    async for event in agent.astream(state, stream_mode="updates"):
        yield event

