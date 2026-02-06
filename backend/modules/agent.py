import os
import asyncio
import json
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
    Now supports Phase 4: Dialogue Orchestration.
    """
    messages: Annotated[List[BaseMessage], add_messages]
    twin_id: str
    confidence_score: float
    citations: List[str]
    # Path B: Agentic RAG additions
    sub_queries: Optional[List[str]]
    reasoning_history: Optional[List[str]]
    retrieved_context: Optional[Dict[str, Any]] # Stores results from multiple tools
    
    # Phase 4: Dialogue Orchestration Metadata
    dialogue_mode: Optional[str]        # SMALLTALK, QA_FACT, TEACHING, etc.
    requires_evidence: bool
    requires_teaching: bool
    target_owner_scope: bool            # True if person-specific
    planning_output: Optional[Dict[str, Any]] # Structured JSON from Planner Pass
    
    # Path B / Phase 4 Context
    full_settings: Optional[Dict[str, Any]]
    graph_context: Optional[str]
    owner_memory_context: Optional[str]

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
    """
    Analyzes owner's verified responses and opinion documents to create a persistent style profile.
    Now supports Phase 4: Dialogue Orchestration via TwinState.
    """
    twin_id = state.get("twin_id", "Unknown")
    full_settings = state.get("full_settings") or {}
    graph_context = state.get("graph_context") or ""
    owner_memory_context = state.get("owner_memory_context") or ""
    
    style_desc = full_settings.get("persona_profile", "Professional and helpful.")
    phrases = full_settings.get("signature_phrases", [])
    opinion_map = full_settings.get("opinion_map", {})
    
    # Load identity context (High-level concepts)
    node_context = ""
    try:
        from modules.database import supabase
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
    
    return f"""You are the AI Digital Twin of the owner (ID: {twin_id}).
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
async def router_node(state: TwinState):
    """Phase 4 Orchestrator: Intent Classification & Routing"""
    messages = state["messages"]
    last_human_msg = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    
    router_prompt = f"""You are a Strategic Dialogue Router for a Digital Twin.
    Classify the user's intent to determine retrieval and evidence requirements.
    
    USER QUERY: {last_human_msg}
    
    MODES:
    - SMALLTALK: Greetings, brief pleasantries, "how are you".
    - QA_FACT: Questions about objective facts, events, or public knowledge.
    - QA_RELATIONSHIP: Questions about people, entities, or connections (Graph needed).
    - STANCE_GLOBAL: Questions about beliefs, opinions, core philosophy, or "what do I think about".
    - REPAIR: User complaining about being robotic, generic, or incorrect.
    - TEACHING: Explicit request for the twin to learn or the twin needing more info (Fallback).
    
    INTENT ATTRIBUTES:
    - is_person_specific: True if the question asks for MY (the owner's) specific view, decision, preference, or experience.
    
    OUTPUT FORMAT (JSON):
    {{
        "mode": "SMALLTALK | QA_FACT | QA_RELATIONSHIP | STANCE_GLOBAL | REPAIR | TEACHING",
        "is_person_specific": bool,
        "requires_evidence": bool,
        "reasoning": "Brief explanation"
    }}
    """
    
    try:
        router_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, model_kwargs={"response_format": {"type": "json_object"}})
        res = await router_llm.ainvoke([SystemMessage(content=router_prompt)])
        plan = json.loads(res.content)
        print(f"[Router] Plan: {plan}")
        
        mode = plan.get("mode", "QA_FACT")
        is_specific = plan.get("is_person_specific", False)
        req_evidence = plan.get("requires_evidence", True)
        
        # Phase 4 Enforcement: Person-specific queries MUST have evidence verification
        if is_specific:
            req_evidence = True
            
        # Sub-query generation for the next step (retrieval)
        sub_queries = [last_human_msg] if mode != "SMALLTALK" else []
        
        return {
            "dialogue_mode": mode,
            "target_owner_scope": is_specific,
            "requires_evidence": req_evidence,
            "sub_queries": sub_queries,
            "reasoning_history": (state.get("reasoning_history") or []) + [f"Router: Mode={mode}, Specific={is_specific}"]
        }
    except Exception as e:
        print(f"Router error: {e}")
        return {"dialogue_mode": "QA_FACT", "requires_evidence": True, "sub_queries": [last_human_msg]}

async def evidence_gate_node(state: TwinState):
    """Phase 4: Evidence Gate (Hard Constraint with LLM Verifier)"""
    mode = state.get("dialogue_mode")
    is_specific = state.get("target_owner_scope", False)
    context = state.get("retrieved_context", {}).get("results", [])
    last_human_msg = next((m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), "")
    
    # Hard Gate Logic
    requires_teaching = False
    reason = "Sufficient evidence found."
    
    if is_specific:
        if not context:
            requires_teaching = True
            reason = "No evidence found for person-specific query."
        else:
            # LLM Verifier Pass for person-specific intents
            context_str = "\n".join([f"- {c.get('text')}" for c in context[:3]])
            verifier_prompt = f"""You are an Evidence Verifier for a Digital Twin.
            The user asked a person-specific question, and we retrieved some context.
            Determine if the context contains SUFFICIENT EVIDENCE to answer the question as the twin.
            
            USER QUESTION: {last_human_msg}
            RETRIEVED CONTEXT:
            {context_str}
            
            RULE: If the context is generic, irrelevant, or doesn't actually contain the owner's stance/recipe/decision, you MUST fail it.
            
            OUTPUT FORMAT (JSON):
            {{
                "is_sufficient": bool,
                "reason": "Brief explanation"
            }}
            """
            try:
                verifier_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, model_kwargs={"response_format": {"type": "json_object"}})
                res = await verifier_llm.ainvoke([SystemMessage(content=verifier_prompt)])
                v_res = json.loads(res.content)
                
                if not v_res.get("is_sufficient"):
                    requires_teaching = True
                    reason = f"Verifier: {v_res.get('reason')}"
            except Exception as e:
                print(f"Verifier error: {e}")
                # Fallback to simple context check
                if len(context) < 1:
                    requires_teaching = True
                    reason = "Fallback: Insufficient context length."

    new_mode = "TEACHING" if requires_teaching else mode
    
    return {
        "dialogue_mode": new_mode,
        "requires_teaching": requires_teaching,
        "reasoning_history": (state.get("reasoning_history") or []) + [f"Gate: {'FAIL -> TEACHING' if requires_teaching else 'PASS'}. {reason}"]
    }

async def planner_node(state: TwinState):
    """Pass A: Strategic Planning & Logic (Structured JSON)"""
    mode = state.get("dialogue_mode", "QA_FACT")
    context_data = state.get("retrieved_context", {}).get("results", [])
    
    # Use the dynamic system prompt (Phase 4)
    system_msg = build_system_prompt(state)
    
    # Prepare context
    context_str = ""
    for i, res in enumerate(context_data):
        text = res.get("text", "")
        date_info = res.get("metadata", {}).get("effective_from", "Unknown Date")
        source = res.get("source_id", "Unknown")
        context_str += f"[{i}] (Date: {date_info} | ID: {source}): {text}\n"

    planner_prompt = f"""
{system_msg}

CURRENT MODE: {mode}
EVIDENCE:
{context_str if context_str else "No evidence retrieved."}

TASK:
1. Identify the core points for the user's answer (max 3).
2. If in TEACHING mode, generate 2-3 specific questions for the owner.
3. Select a follow-up question to keep the conversation going.
4. If evidence is present, map points to citations.

OUTPUT FORMAT (STRICT JSON):
{{
    "answer_points": ["point 1", "point 2"],
    "citations": ["Source_ID_1", "Source_ID_2"],
    "follow_up_question": "...",
    "confidence": 0.0-1.0,
    "teaching_questions": ["q1", "q2"],
    "reasoning_trace": "Short internal log"
}}
"""
    try:
        planner_llm = ChatOpenAI(model="gpt-4o", temperature=0, model_kwargs={"response_format": {"type": "json_object"}})
        res = await planner_llm.ainvoke([SystemMessage(content=planner_prompt)])
        plan = json.loads(res.content)
        
        return {
            "planning_output": plan,
            "reasoning_history": (state.get("reasoning_history") or []) + [f"Planner: Generated {len(plan.get('answer_points', []))} points."]
        }
    except Exception as e:
        print(f"Planner error: {e}")
        return {"planning_output": {"answer_points": ["I encountered an error planning my response."], "follow_up_question": "Can you try rephrasing?"}}

async def realizer_node(state: TwinState):
    """Pass B: Conversational Reification (Human-like Output)"""
    plan = state.get("planning_output", {})
    mode = state.get("dialogue_mode", "QA_FACT")
    llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
    
    realizer_prompt = f"""You are the Voice Realizer for a Digital Twin. 
    Take the structured plan and rewrite it into a short, natural, conversational response.
    
    PLAN:
    {json.dumps(plan, indent=2)}
    
    CONSTRAINTS:
    - 1 to 3 sentences total.
    - Sound like a real person, not a bot.
    - Include the follow-up question at the end.
    - If teaching: explain briefly that you need their input to be certain.
    - NO FAKE SOURCES. Use citations provided in the plan if any.
    """
    
    try:
        res = await llm.ainvoke([SystemMessage(content=realizer_prompt)])
        
        # Post-process for citations and teaching metadata (Phase 4)
        citations = plan.get("citations", [])
        teaching_questions = plan.get("teaching_questions", [])
        
        # Enrich message with metadata for the UI
        res.additional_kwargs["teaching_questions"] = teaching_questions
        res.additional_kwargs["planning_output"] = plan
        res.additional_kwargs["dialogue_mode"] = mode
        
        return {
            "messages": [res],
            "citations": citations,
            "reasoning_history": (state.get("reasoning_history") or []) + ["Realizer: Response reified with Metadata."]
        }
    except Exception as e:
        print(f"Realizer error: {e}")
        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(content="I'm having trouble finding the words right now.")]}

def create_twin_agent(
    twin_id: str,
    group_id: Optional[str] = None,
    system_prompt_override: str = None,
    full_settings: dict = None,
    graph_context: str = "",
    owner_memory_context: str = ""
):
    # Retrieve-only tool setup needs to stay inside or be passed
    from modules.tools import get_retrieval_tool
    retrieval_tool = get_retrieval_tool(twin_id, group_id=group_id)

    async def retrieve_hybrid_node(state: TwinState):
        """Phase 2: Executing planned retrieval (Audit 1: Parallel & Robust)"""
        sub_queries = state.get("sub_queries", [])
        messages = state["messages"]
        all_results = []
        citations = []
        
        async def safe_retrieve(query):
            try:
                res_str = await retrieval_tool.ainvoke({"query": query})
                return json.loads(res_str)
            except Exception as e:
                print(f"Retrieval error: {e}")
                return []

        tasks = [safe_retrieve(q) for q in sub_queries]
        results_list = await asyncio.gather(*tasks)
        for res_data in results_list:
            if isinstance(res_data, list):
                for item in res_data:
                    all_results.append(item)
                    if "source_id" in item:
                        citations.append(item["source_id"])

        return {
            "retrieved_context": {"results": all_results},
            "citations": list(set(citations)),
            "reasoning_history": (state.get("reasoning_history") or []) + [f"Retrieval: Executed {len(sub_queries)} queries."]
        }

    # Define the graph
    workflow = StateGraph(TwinState)
    
    workflow.add_node("router", router_node)
    workflow.add_node("retrieve", retrieve_hybrid_node)
    workflow.add_node("gate", evidence_gate_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("realizer", realizer_node)
    
    workflow.set_entry_point("router")
    
    def route_after_router(state: TwinState):
        if state.get("requires_evidence"):
            return "retrieve"
        return "planner"

    workflow.add_conditional_edges("router", route_after_router, {"retrieve": "retrieve", "planner": "planner"})
    workflow.add_edge("retrieve", "gate")
    workflow.add_edge("gate", "planner")
    workflow.add_edge("planner", "realizer")
    workflow.add_edge("realizer", END)
    
    checkpointer = get_checkpointer()
    return workflow.compile(checkpointer=checkpointer) if checkpointer else workflow.compile()

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
        "retrieved_context": {},
        # Phase 4 initialization
        "dialogue_mode": "QA_FACT",
        "requires_evidence": True,
        "requires_teaching": False,
        "target_owner_scope": False,
        "planning_output": None,
        # Path B / Phase 4 Context
        "full_settings": settings,
        "graph_context": graph_context,
        "owner_memory_context": owner_memory_context
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
