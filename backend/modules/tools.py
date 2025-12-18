from langchain.tools import tool
from modules.retrieval import retrieve_context
from typing import List, Dict, Any
import os

def get_retrieval_tool(twin_id: str):
    """
    Creates a tool for retrieving context from the digital twin's knowledge base.
    """
    @tool
    async def search_knowledge_base(query: str) -> str:
        """
        Searches the digital twin's knowledge base for information relevant to the query.
        Use this tool when you need information from documents uploaded by the owner.
        Returns a JSON string containing the relevant context snippets.
        """
        import json
        print(f"DEBUG: search_knowledge_base called with query: {query}")
        contexts = await retrieve_context(query, twin_id)
        return json.dumps(contexts)
    
    return search_knowledge_base

def get_cloud_tools():
    """
    Returns a list of cloud-based tools (e.g., Gmail, Slack) via Composio or fallback tools.
    """
    tools = []
    
    # 1. Try to load Composio tools if API key is present
    if os.getenv("COMPOSIO_API_KEY"):
        try:
            from composio_langchain import ComposioToolSet, App
            toolset = ComposioToolSet()
            # Default to some useful apps if configured
            # tools.extend(toolset.get_tools(apps=[App.GMAIL, App.SLACK]))
            pass
        except ImportError:
            print("Composio not installed, skipping cloud tools.")

    # 2. Add fallback/utility tools if allowed
    # Note: In a production "Verified" brain, we might want to restrict external search
    # unless explicitly allowed in twin settings.
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        # Only add if specifically enabled in env or for certain twins
        if os.getenv("ENABLE_WEB_SEARCH") == "true":
            tools.append(DuckDuckGoSearchRun())
    except ImportError:
        pass

    return tools

