# backend/modules/graph_context.py
"""
Graph Context Module

Provides bounded, query-relevant graph snapshot retrieval for chat context.
Uses Supabase for storage with 1-hop and optional 2-hop expansion.
"""

from typing import Dict, Any, List, Optional
import logging

from modules.observability import supabase

logger = logging.getLogger(__name__)

# Caps for Graph Snapshot
MAX_SEED_NODES = 8
MAX_NODES = 12
MAX_EDGES = 24


def get_graph_stats(twin_id: str) -> Dict[str, Any]:
    """
    Get summary statistics about a twin's cognitive graph.
    Returns node count and top nodes for UI display.
    """
    try:
        nodes_res = supabase.rpc("get_nodes_system", {
            "t_id": twin_id,
            "limit_val": 50
        }).execute()
        
        nodes = nodes_res.data if nodes_res.data else []
        
        intent_nodes = []
        profile_nodes = []
        
        for node in nodes:
            node_type = node.get("type", "").lower()
            name = node.get("name", "")
            description = node.get("description", "")
            
            if not name:
                continue
            
            node_summary = {
                "name": name,
                "type": node.get("type", ""),
                "description": description[:100] + "..." if len(description) > 100 else description
            }
            
            if "intent" in node_type:
                intent_nodes.append(node_summary)
            else:
                profile_nodes.append(node_summary)
        
        top_nodes = intent_nodes[:3] + profile_nodes[:5]
        
        return {
            "node_count": len(nodes),
            "has_graph": len(nodes) > 0,
            "intent_count": len(intent_nodes),
            "profile_count": len(profile_nodes),
            "top_nodes": top_nodes
        }
    except Exception as e:
        logger.error(f"Error fetching graph stats: {e}")
        return {
            "node_count": 0,
            "has_graph": False,
            "intent_count": 0,
            "profile_count": 0,
            "top_nodes": []
        }

# Import observe decorator for tracing
try:
    from langfuse import observe
    _observe_available = True
except ImportError:
    _observe_available = False
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


@observe(name="graph_snapshot")
async def get_graph_snapshot(
    twin_id: str,
    query: str = None,
    max_nodes: int = MAX_NODES,
    max_edges: int = MAX_EDGES
) -> Dict[str, Any]:
    """
    Build bounded, query-relevant Graph Snapshot for chat context.
    
    Algorithm:
    1. Seed selection via ILIKE match on name/description
    2. 1-hop expansion via edges table
    3. Optional 2-hop if seeds < 3 and under budget
    4. Rank by seed relevance, connectedness, recency
    5. Cap to max_nodes, max_edges
    6. Compress to prompt-ready text
    
    Args:
        twin_id: Twin UUID
        query: User query for seed selection
        max_nodes: Maximum nodes in snapshot (default 12)
        max_edges: Maximum edges in snapshot (default 24)
    
    Returns:
        Dict with context_text, nodes, edges, metadata
    """
    try:
        # 1. Seed Selection
        seed_nodes = await _select_seeds(twin_id, query)
        seed_ids = [n['id'] for n in seed_nodes]
        
        if not seed_nodes:
            # Fallback: get recent nodes if no query match
            all_nodes = await _get_all_nodes(twin_id, limit=max_nodes)
            return _format_snapshot(all_nodes, [], query)
        
        # 2. 1-hop expansion
        neighbor_nodes, edges = await _expand_one_hop(twin_id, seed_ids)
        
        # Combine seeds + neighbors
        all_node_ids = set(seed_ids)
        all_nodes = {n['id']: n for n in seed_nodes}
        
        for node in neighbor_nodes:
            if len(all_nodes) < max_nodes:
                all_node_ids.add(node['id'])
                all_nodes[node['id']] = node
        
        # 3. Optional 2-hop if under budget
        if len(seed_nodes) < 3 and len(all_nodes) < max_nodes:
            new_neighbor_ids = [n['id'] for n in neighbor_nodes if n['id'] not in seed_ids]
            if new_neighbor_ids:
                hop2_nodes, hop2_edges = await _expand_one_hop(twin_id, new_neighbor_ids[:3])
                for node in hop2_nodes:
                    if len(all_nodes) < max_nodes and node['id'] not in all_nodes:
                        all_nodes[node['id']] = node
                edges.extend(hop2_edges)
        
        # 4. Filter edges to only those within our node set
        final_nodes = list(all_nodes.values())
        final_node_ids = set(all_nodes.keys())
        final_edges = [
            e for e in edges 
            if e.get('from_node_id') in final_node_ids 
            and e.get('to_node_id') in final_node_ids
        ][:max_edges]
        
        # 5. Rank nodes (seeds first, then by recency)
        ranked_nodes = _rank_nodes(final_nodes, seed_ids)
        
        return _format_snapshot(ranked_nodes[:max_nodes], final_edges, query)
        
    except Exception as e:
        logger.error(f"Error building graph snapshot: {e}")
        return {
            "context_text": "",
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
            "query": query,
            "error": str(e)
        }


async def _select_seeds(twin_id: str, query: str) -> List[Dict[str, Any]]:
    """Select seed nodes via ILIKE match on query."""
    if not query:
        return []
    
    try:
        # Extract keywords from query (simple split, could use NLP)
        keywords = [w.strip() for w in query.split() if len(w.strip()) > 2]
        
        if not keywords:
            return []
        
        # Build ILIKE pattern
        # Use first 3 meaningful keywords
        search_terms = keywords[:3]
        
        # Fetch all nodes and filter (Supabase doesn't support complex OR ILIKE easily)
        nodes_res = supabase.rpc("get_nodes_system", {
            "t_id": twin_id,
            "limit_val": 100
        }).execute()
        
        nodes = nodes_res.data if nodes_res.data else []
        
        # Score nodes by keyword matches
        scored_nodes = []
        for node in nodes:
            name = (node.get("name") or "").lower()
            desc = (node.get("description") or "").lower()
            
            score = 0
            for term in search_terms:
                term_lower = term.lower()
                if term_lower in name:
                    score += 3  # Name match is high value
                if term_lower in desc:
                    score += 1  # Description match
            
            if score > 0:
                scored_nodes.append((score, node))
        
        # Sort by score descending, take top seeds
        scored_nodes.sort(key=lambda x: x[0], reverse=True)
        return [n for _, n in scored_nodes[:MAX_SEED_NODES]]
        
    except Exception as e:
        logger.error(f"Error selecting seeds: {e}")
        return []


async def _get_all_nodes(twin_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Get all nodes for a twin (fallback when no query)."""
    try:
        nodes_res = supabase.rpc("get_nodes_system", {
            "t_id": twin_id,
            "limit_val": limit
        }).execute()
        return nodes_res.data if nodes_res.data else []
    except Exception as e:
        logger.error(f"Error getting all nodes: {e}")
        return []


async def _expand_one_hop(twin_id: str, node_ids: List[str]) -> tuple:
    """Get 1-hop neighbors via edges."""
    if not node_ids:
        return [], []
    
    try:
        # Get edges where any seed is from or to
        # Note: This is a simplification - ideally we'd use a custom RPC
        edges_res = supabase.table("edges").select("*").eq(
            "twin_id", twin_id
        ).execute()
        
        edges = edges_res.data if edges_res.data else []
        
        # Filter to edges connected to our seeds
        connected_edges = []
        neighbor_ids = set()
        
        for edge in edges:
            from_id = edge.get("from_node_id")
            to_id = edge.get("to_node_id")
            
            if from_id in node_ids:
                connected_edges.append(edge)
                if to_id not in node_ids:
                    neighbor_ids.add(to_id)
            elif to_id in node_ids:
                connected_edges.append(edge)
                if from_id not in node_ids:
                    neighbor_ids.add(from_id)
        
        # Fetch neighbor nodes
        neighbor_nodes = []
        if neighbor_ids:
            nodes_res = supabase.table("nodes").select("*").eq(
                "twin_id", twin_id
            ).in_("id", list(neighbor_ids)).execute()
            neighbor_nodes = nodes_res.data if nodes_res.data else []
        
        return neighbor_nodes, connected_edges
        
    except Exception as e:
        logger.error(f"Error expanding 1-hop: {e}")
        return [], []


def _rank_nodes(nodes: List[Dict], seed_ids: List[str]) -> List[Dict]:
    """Rank nodes: seeds first, then by updated_at."""
    seed_set = set(seed_ids)
    
    def sort_key(node):
        is_seed = node['id'] in seed_set
        updated = node.get('updated_at') or node.get('created_at') or ''
        return (not is_seed, updated)  # False sorts before True
    
    return sorted(nodes, key=sort_key, reverse=True)


def _format_snapshot(nodes: List[Dict], edges: List[Dict], query: str = None) -> Dict[str, Any]:
    """Format snapshot into prompt-ready context."""
    if not nodes:
        return {
            "context_text": "",
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
            "query": query
        }
    
    # Build context text
    node_lines = []
    for n in nodes:
        name = n.get("name", "")
        node_type = n.get("type", "")
        description = n.get("description", "")
        props = n.get("properties", {}) or {}
        
        if not name or not description:
            continue
        
        props_str = ""
        if props:
            props_items = [f"{k}: {v}" for k, v in props.items() 
                          if isinstance(v, (str, int, float))][:3]
            if props_items:
                props_str = f" [{', '.join(props_items)}]"
        
        node_lines.append(f"- {name} ({node_type}): {description}{props_str}")
    
    # Build edge lines
    edge_lines = []
    node_name_map = {n['id']: n.get('name', 'Unknown') for n in nodes}
    for e in edges[:10]:  # Limit edge descriptions
        from_name = node_name_map.get(e.get('from_node_id'), 'Unknown')
        to_name = node_name_map.get(e.get('to_node_id'), 'Unknown')
        edge_type = e.get('type', 'RELATED_TO')
        edge_lines.append(f"  {from_name} → {edge_type} → {to_name}")
    
    context_text = ""
    if node_lines:
        context_text = "MEMORIZED KNOWLEDGE (High Priority - Answer from here if relevant):\n"
        context_text += "\n".join(node_lines)
        if edge_lines:
            context_text += "\n\nKNOWN RELATIONSHIPS:\n" + "\n".join(edge_lines)
    
    return {
        "context_text": context_text,
        "nodes": [{"id": n['id'], "name": n.get('name'), "type": n.get('type')} for n in nodes],
        "edges": [{"id": e['id'], "type": e.get('type')} for e in edges],
        "node_count": len(nodes),
        "edge_count": len(edges),
        "query": query
    }


# Legacy function for backward compatibility
def get_graph_context_for_chat(twin_id: str, limit: int = 20) -> Dict[str, Any]:
    """
    Legacy sync wrapper. Use get_graph_snapshot for new code.
    """
    try:
        nodes_res = supabase.rpc("get_nodes_system", {
            "t_id": twin_id,
            "limit_val": limit
        }).execute()
        
        nodes = nodes_res.data if nodes_res.data else []
        
        if not nodes:
            return {
                "context_text": "",
                "node_count": 0,
                "nodes_used": []
            }
        
        node_summaries = []
        nodes_used = []
        
        for n in nodes:
            name = n.get("name", "")
            node_type = n.get("type", "")
            description = n.get("description", "")
            props = n.get("properties", {}) or {}
            
            if not name or not description:
                continue
            
            props_str = ""
            if props:
                props_items = [f"{k}: {v}" for k, v in props.items() 
                              if isinstance(v, (str, int, float))]
                if props_items:
                    props_str = f" [{', '.join(props_items[:3])}]"
            
            node_summaries.append(f"- {name} ({node_type}): {description}{props_str}")
            nodes_used.append({
                "name": name,
                "type": node_type
            })
        
        context_text = ""
        if node_summaries:
            context_text = "MEMORIZED KNOWLEDGE (High Priority - Answer from here if relevant):\n" + "\n".join(node_summaries)
        
        return {
            "context_text": context_text,
            "node_count": len(nodes_used),
            "nodes_used": nodes_used
        }
    except Exception as e:
        logger.error(f"Error fetching graph context: {e}")
        return {
            "context_text": "",
            "node_count": 0,
            "nodes_used": []
        }

def get_style_guidelines(twin_id: str) -> str:
    """
    Get explicit style/tone guidelines from the graph.
    Returns a system prompt segment.
    """
    try:
        # Fetch style nodes
        nodes_res = supabase.rpc("get_nodes_system", {
            "t_id": twin_id,
            "limit_val": 10
        }).execute()
        
        nodes = nodes_res.data if nodes_res.data else []
        style_instructions = []
        
        for n in nodes:
            node_type = n.get("type", "").lower()
            name = n.get("name", "")
            desc = n.get("description", "")
            
            if "style" in node_type or "communication" in node_type or "tone" in node_type:
                style_instructions.append(f"- {name}: {desc}")
                
        if not style_instructions:
            return ""
            
        return "COMMUNICATION STYLE (Must Follow):\n" + "\n".join(style_instructions)
        
    except Exception as e:
        logger.error(f"Error fetching style guidelines: {e}")
        return ""
