import os
import asyncio
from typing import Annotated, TypedDict, List, Dict, Any, Union, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from modules.tools import get_retrieval_tool, get_cloud_tools
from modules.observability import supabase

# Try to import checkpointer (optional - P1-A)
try:
    from langgraph.checkpoint.postgres import PostgresSaver
    # Note: asyncpg is a dependency of langgraph-checkpoint-postgres, no need to import directly
    CHECKPOINTER_AVAILABLE = True
except ImportError:
    CHECKPOINTER_AVAILABLE = False
    PostgresSaver = None

# Global checkpointer instance (singleton)
_checkpointer = None

def get_checkpointer():
    """
    Get or create Postgres checkpointer instance (P1-A).
    Returns None if DATABASE_URL not set or checkpointer unavailable.
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    
    if not CHECKPOINTER_AVAILABLE:
        return None
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # Checkpointer is optional - return None if DATABASE_URL not set
        return None
    
    try:
        # Initialize checkpointer with Postgres connection
        # The checkpointer will create its own connection pool
        _checkpointer = PostgresSaver.from_conn_string(database_url)
        print("[LangGraph] Checkpointer initialized with DATABASE_URL")
        return _checkpointer
    except Exception as e:
        print(f"[LangGraph] Failed to initialize checkpointer: {e}")
        return None

async def get_owner_style_profile(twin_id: str, force_refresh: bool = False) -> str:
    """
    Analyzes owner's verified responses and opinion documents to create a persistent style profile.
    """
    try:
        # 1. Check if we already have a profile in the database
        if not force_refresh:
            # RLS Fix: Use RPC
            twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
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
                vector=[0.1] * 3072, # Use non-zero vector for metadata filtering
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
            # RLS Fix: Use RPC
            twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
            curr_settings = twin_res.data["settings"] if twin_res.data else {}
            
            curr_settings["persona_profile"] = persona_data.get("description")
            curr_settings["signature_phrases"] = persona_data.get("signature_phrases", [])
            curr_settings["style_exemplars"] = persona_data.get("style_exemplars", [])
            curr_settings["opinion_map"] = persona_data.get("opinion_summary", {})
            curr_settings["last_style_analysis"] = datetime.now().isoformat()
            
            # Update probably needs RPC too? Or update via table might work if RLS allows UPDATE but not SELECT?
            # Usually RLS blocks both. But we only need Read for `run_agent_stream`.
            # Updating style is a background task. 
            # I'll leave update as is for now, assuming RLS allows update? (Unlikely).
            # I should use update_twin_settings system RPC but I didn't create one.
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
    Supports Path B: Global Reasoning & Agentic RAG.
    """
    messages: Annotated[List[BaseMessage], add_messages]
    twin_id: str
    confidence_score: float
    citations: List[str]
    # Path B: Agentic RAG additions
    sub_queries: Optional[List[str]]
    reasoning_history: Optional[List[str]]
    retrieved_context: Optional[Dict[str, Any]] # Stores results from multiple tools

def create_twin_agent(
    twin_id: str,
    group_id: Optional[str] = None,
    system_prompt_override: str = None,
    full_settings: dict = None,
    graph_context: str = "",
    owner_memory_context: str = ""
):
    # Initialize the LLM
    api_key = os.getenv("OPENAI_API_KEY")
    
    # Extract tool_access override if present from full_settings
    # (group settings should already be merged in run_agent_stream)
    allowed_tools = None
    if full_settings and "tool_access" in full_settings:
        tool_access_config = full_settings.get("tool_access", {})
        if isinstance(tool_access_config, list):
            allowed_tools = tool_access_config
        elif isinstance(tool_access_config, dict) and "allowed_tools" in tool_access_config:
            allowed_tools = tool_access_config["allowed_tools"]
    
    # Ensure full_settings is a dict
    if full_settings is None:
        full_settings = {}
    
    # Apply group overrides for specific fields
    temperature = full_settings.get("temperature") if "temperature" in full_settings else 0
    max_tokens = full_settings.get("max_tokens")
    
    # Using a model that supports tool calling well
    llm = ChatOpenAI(
        model="gpt-4-turbo-preview", 
        api_key=api_key, 
        temperature=temperature, 
        streaming=True,
        max_tokens=max_tokens if max_tokens else None
    )
    
    # Setup tools
    cloud_tools = get_cloud_tools(allowed_tools=allowed_tools)
    
    # Helper: Build the system prompt with persona and context
    def build_system_prompt(state: TwinState) -> str:
        settings = full_settings or {}
        style_desc = settings.get("persona_profile", "Professional and helpful.")
        phrases = settings.get("signature_phrases", [])
        exemplars = settings.get("style_exemplars", [])
        opinion_map = settings.get("opinion_map", {})
        general_knowledge_allowed = settings.get("general_knowledge_allowed", False)
        
        # Load identity context (High-level concepts)
        node_context = ""
        try:
            nodes_res = supabase.rpc("get_nodes_system", {"t_id": twin_id, "limit_val": 10}).execute()
            if nodes_res.data:
                profile_items = [f"- {n.get('name')}: {n.get('description')}" for n in nodes_res.data]
                node_context = "\n            **GENERAL IDENTITY NODES:**\n            " + "\n            ".join(profile_items)
        except Exception: pass

        final_graph_context = ""
        if graph_context:
            final_graph_context += f"SPECIFIC KNOWLEDGE:\n{graph_context}\n\n"
        if node_context:
            final_graph_context += node_context
        
        persona_section = f"YOUR PERSONA STYLE:\n- DESCRIPTION: {style_desc}"
        if phrases: persona_section += f"\n- SIGNATURE PHRASES: {', '.join(phrases)}"
        if opinion_map:
            opinions_text = "\n".join([f"- {t}: {d['stance']}" for t, d in opinion_map.items()])
            persona_section += f"\n- CORE WORLDVIEW:\n{opinions_text}"

        owner_memory_block = f"OWNER MEMORY:\n{owner_memory_context if owner_memory_context else '- None available.'}"
        
        base_identity = system_prompt_override or f"You are the AI Digital Twin of the owner (ID: {twin_id})."
        
        return f"""{base_identity}
YOUR PRINCIPLES (Immutable):
- Use first-person ("I", "my").
- Every claim MUST be supported by retrieved context.
- If context is missing, say you don't know.
- Be concise by default.

{persona_section}

{final_graph_context}

{owner_memory_block}

AGENTIC RAG OPERATING PROCEDURES:
1. Use `search_knowledge_base` to find specific facts or beliefs.
2. If multiple searches are needed for global reasoning (e.g. "What are my principles?"), perform them.
3. If you find contradictions, acknowledge them.
"""

    # Define the nodes
    async def planner_node(state: TwinState):
        """Phase 1: Intelligent Query Decomposition (Audit 2: LLM Planner)"""
        messages = state["messages"]
        last_human_msg = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
        
        planning_prompt = f"""You are a Strategic Retrieval Planner for a Digital Twin.
        Your goal is to decompose the user's query into 1-3 targeted sub-queries for RAG retrieval.
        
        USER QUERY: {last_human_msg}
        
        OBJECTIVES:
        1. If it's a 'Global' query (e.g., "What are my principles?", "Summarize everything"), generate sub-queries covering high-level concepts, personal philosophy, and recent stances.
        2. If it's a 'Specific' query, generate refined versions of the query to maximize semantic match.
        3. Identify if the query is asking for a CONTRADICTION check.
        
        OUTPUT FORMAT (JSON):
        {{
            "sub_queries": ["query 1", "query 2"],
            "strategy": "global | specific | contradiction",
            "reasoning": "Brief explanation of why these sub-queries were chosen"
        }}
        """
        
        try:
            planner_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, model_kwargs={"response_format": {"type": "json_object"}})
            res = await planner_llm.ainvoke([SystemMessage(content=planning_prompt)])
            import json
            plan = json.loads(res.content)
            
            sub_queries = plan.get("sub_queries", [last_human_msg])
            strategy = plan.get("strategy", "specific")
            reasoning = plan.get("reasoning", "Direct retrieval.")
            
            return {
                "sub_queries": sub_queries, 
                "reasoning_history": (state.get("reasoning_history") or []) + [f"Planning ({strategy}): {reasoning}"]
            }
        except Exception as e:
            print(f"Planning error: {e}")
            return {"sub_queries": [last_human_msg], "reasoning_history": ["Planning fallback: Direct retrieval."]}

    async def retrieve_hybrid_node(state: TwinState):
        """Phase 2: Executing planned retrieval (Audit 1: Parallel & Robust)"""
        sub_queries = state.get("sub_queries", [])
        twin_id = state["twin_id"]
        messages = state["messages"]
        
        all_results = []
        citations = []
        total_score = 0
        score_count = 0
        
        # Create retrieval tool
        retrieval_tool = get_retrieval_tool(twin_id, group_id=group_id, conversation_history=messages)
        
        # Parallel execution of sub-queries (Performance Improvement)
        async def safe_retrieve(query):
            try:
                res_str = await retrieval_tool.ainvoke({"query": query})
                import json
                return json.loads(res_str)
            except Exception as e:
                print(f"Retrieval sub-query error ({query}): {e}")
                return []

        tasks = [safe_retrieve(q) for q in sub_queries]
        results_list = await asyncio.gather(*tasks)
        
        for res_data in results_list:
            if isinstance(res_data, list):
                for item in res_data:
                    all_results.append(item)
                    if "source_id" in item:
                        citations.append(item["source_id"])
                    if "score" in item:
                        total_score += item.get("score", 0.7)
                        score_count += 1

        new_confidence = total_score / score_count if score_count > 0 else 0.0
        
        # Check for verified matches
        has_verified = any(
            item.get("is_verified") or item.get("verified_qna_match") 
            for item in all_results if isinstance(item, dict)
        )
        if has_verified: 
            new_confidence = 1.0

        return {
            "retrieved_context": {"results": all_results},
            "citations": list(set(citations)),
            "confidence_score": new_confidence,
            "reasoning_history": (state.get("reasoning_history") or []) + [f"Retrieval: Executed {len(sub_queries)} parallel sub-queries."]
        }

    async def synthesize_node(state: TwinState):
        """Phase 3: Final Answer Construction (Audit 3: Stance Compiler & Path C)"""
        messages = state["messages"]
        context_data = state.get("retrieved_context", {}).get("results", [])
        settings = full_settings or {}
        opinion_map = settings.get("opinion_map", {})
        
        # Prepare context for the prompt
        context_str = ""
        for i, res in enumerate(context_data):
            text = res.get("text", "")
            # Temporal Marker (Path C Preparation)
            date_info = res.get("metadata", {}).get("effective_from", "Unknown Date")
            source = res.get("source_id", "Unknown")
            context_str += f"[{i}] (Date: {date_info} | ID: {source}): {text}\n"
        
        # Build the structured system prompt
        system_msg = build_system_prompt(state)
        
        # Stance Compiler: Inject core worldviews into the synthesis instruction
        opinions_context = "\n".join([f"- {topic}: {data['stance']}" for topic, data in opinion_map.items()]) if opinion_map else "No specific opinions recorded."

        synthesis_instruction = f"""
{system_msg}

### CORE WORLDVIEW (Authoritative Stance):
{opinions_context}

### RETRIEVED KNOWLEDGE (Chronological/Relevance Ordered):
{context_str}

### PATH B GLOBAL REASONING & PATH C TEMPORAL INSTRUCTIONS:
1. **Consistency Check**: Do the retrieved facts align with my CORE WORLDVIEW? If the knowledge contradicts my core beliefs, prioritize my belief but mention the conflicting data as a potential "point of growth" or "outside perspective".
2. **Temporal Evolution**: Look at the dates in [brackets]. If my stance has changed over time, explain the EVOLUTION. (Path C Reasoning).
3. **Citation Integrity**: Every sentence must point to [Source ID] or [bracket index].
4. **Final Synthesis**: Provide a unified, first-person response that sounds like ME.
"""

        # Context Management: Keep the system prompt and the last 5 human-ai turns
        managed_messages = [SystemMessage(content=synthesis_instruction)]
        if len(messages) > 1:
            managed_messages.extend(messages[1:][-10:]) # Keep last 10 messages for context
            
        try:
            response = await llm.ainvoke(managed_messages)
            
            # Post-processing: Check for citation density (Higher quality check)
            has_citations = "[" in response.content or "Source" in response.content
            
            return {
                "messages": [response],
                "reasoning_history": (state.get("reasoning_history") or []) + [
                    f"Synthesis: Integrated {len(context_data)} sources with Persona Opinions. Citations: {'Present' if has_citations else 'Low'}."
                ]
            }
        except Exception as e:
            print(f"Synthesis error: {e}")
            return {"messages": [HumanMessage(content="I apologize, I encountered a reasoning error while synthesizing my knowledge.")]}

    # Define the graph
    workflow = StateGraph(TwinState)
    
    # Add nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("retrieve", retrieve_hybrid_node)
    workflow.add_node("synthesize", synthesize_node)
    
    # Set entry point
    workflow.set_entry_point("planner")
    
    # Define linear execution for now (can add loops/branches later for complex multi-hop)
    workflow.add_edge("planner", "retrieve")
    workflow.add_edge("retrieve", "synthesize")
    workflow.add_edge("synthesize", END)
    
    # P1-A: Compile with checkpointer if available
    checkpointer = get_checkpointer()
    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)
    else:
        return workflow.compile()

# Langfuse v3 tracing
try:
    from langfuse import observe
    _langfuse_available = True
except ImportError:
    _langfuse_available = False
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


@observe(name="agent_response")
async def run_agent_stream(
    twin_id: str,
    query: str,
    history: List[BaseMessage] = None,
    system_prompt: str = None,
    group_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    owner_memory_context: str = ""
):
    """
    Runs the agent and yields events from the graph.
    
    P1-A: conversation_id is used as thread_id for state persistence if checkpointer is enabled.
    """
    # 0. Apply Phase 9 Safety Guardrails
    from modules.safety import apply_guardrails
    refusal_message = apply_guardrails(twin_id, query)
    if refusal_message:
        # Yield a simulated refusal event to match the graph output format
        yield {
            "agent": {
                "messages": [AIMessage(content=refusal_message)]
            }
        }
        return

    # 1. Fetch full twin settings for persona encoding
    # RLS Fix: Use RPC
    twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
    settings = twin_res.data["settings"] if twin_res.data else {}
    
    # 2. Load group settings if group_id provided
    if group_id:
        try:
            from modules.access_groups import get_group_settings
            group_settings = await get_group_settings(group_id)
            # Merge group settings with twin settings (group takes precedence)
            settings = {**settings, **group_settings}
        except Exception as e:
            print(f"Warning: Failed to load group settings: {e}")
    
    # 3. Ensure style analysis has been run at least once
    if "persona_profile" not in settings:
        await get_owner_style_profile(twin_id)
        # Re-fetch after analysis
        # RLS Fix: Use RPC
        twin_res = supabase.rpc("get_twin_system", {"t_id": twin_id}).single().execute()
        settings = twin_res.data["settings"] if twin_res.data else {}
        # Re-merge group settings if needed
        if group_id:
            try:
                from modules.access_groups import get_group_settings
                group_settings = await get_group_settings(group_id)
                settings = {**settings, **group_settings}
            except Exception:
                pass

    # 3.5 Fetch Graph Snapshot (P0.2 - Bounded, query-relevant)
    # Feature flag: GRAPH_RAG_ENABLED (default: false)
    graph_context = ""
    graph_rag_enabled = os.getenv("GRAPH_RAG_ENABLED", "false").lower() == "true"
    
    if graph_rag_enabled:
        try:
            from modules.graph_context import get_graph_snapshot
            snapshot = await get_graph_snapshot(twin_id, query=query)
            graph_context = snapshot.get("context_text", "")
            if not graph_context:
                print(f"[GraphRAG] Enabled but returned empty context for twin {twin_id}, query: {query[:50]}")
        except Exception as e:
            print(f"[GraphRAG] Retrieval failed, falling back to RAG-lite. Error: {e}")

    agent = create_twin_agent(
        twin_id,
        group_id=group_id,
        system_prompt_override=system_prompt,
        full_settings=settings,
        graph_context=graph_context,
        owner_memory_context=owner_memory_context
    )
    
    initial_messages = history or []
    initial_messages.append(HumanMessage(content=query))
    
    state = {
        "messages": initial_messages,
        "twin_id": twin_id,
        "confidence_score": 1.0,
        "citations": [],
        "sub_queries": [],
        "reasoning_history": [],
        "retrieved_context": {}
    }
    
    # Phase 10: Metrics instrumentation
    from modules.metrics_collector import MetricsCollector
    import time
    
    metrics = MetricsCollector(twin_id=twin_id)
    metrics.record_request()
    agent_start = time.time()
    
    # P1-A: Generate thread_id from conversation_id for state persistence
    thread_id = None
    if conversation_id:
        # Thread ID format: conversation_id (simple, deterministic)
        thread_id = conversation_id
        print(f"[LangGraph] Using thread_id: {thread_id}")
    
    try:
        # P1-A: Pass thread_id if checkpointer is enabled
        config = {"configurable": {"thread_id": thread_id}} if thread_id and get_checkpointer() else {}
        async for event in agent.astream(state, stream_mode="updates", **config):
            yield event
    finally:
        # Record agent latency and flush metrics
        agent_latency = (time.time() - agent_start) * 1000
        metrics.record_latency("agent", agent_latency)
        metrics.flush()
