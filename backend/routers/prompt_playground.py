"""
Prompt Playground API - Test prompts directly
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from modules.auth_guard import require_admin
from modules.inference_router import invoke_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/playground", tags=["prompt-playground"])


class PromptTestRequest(BaseModel):
    prompt: str
    user_message: str
    model: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 1024
    variables: Optional[Dict[str, str]] = None


class PromptTestResponse(BaseModel):
    response: str
    latency_ms: int
    tokens_used: Optional[int] = None
    model: str


@router.post("/test", response_model=PromptTestResponse)
async def test_prompt(
    request: PromptTestRequest,
    user=Depends(require_admin)
):
    """
    Test a prompt with a user message.
    
    Useful for iterating on prompts before saving to Langfuse.
    """
    try:
        import time
        
        start = time.time()
        
        # Compile prompt with variables
        prompt_text = request.prompt
        if request.variables:
            try:
                prompt_text = prompt_text.format(**request.variables)
            except KeyError as e:
                raise HTTPException(status_code=400, detail=f"Missing variable: {e}")
        
        # Call LLM
        messages = [
            {"role": "system", "content": prompt_text},
            {"role": "user", "content": request.user_message}
        ]
        
        response_text, meta = await invoke_text(
            messages,
            task="playground",
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        latency_ms = int((time.time() - start) * 1000)
        
        return PromptTestResponse(
            response=response_text,
            latency_ms=latency_ms,
            model=meta.get("model", request.model)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prompt test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_prompts(
    prompt_a: str,
    prompt_b: str,
    user_message: str,
    user=Depends(require_admin)
):
    """
    Compare two prompts side-by-side with the same user message.
    """
    try:
        import time
        
        results = []
        
        for name, prompt in [("A", prompt_a), ("B", prompt_b)]:
            start = time.time()
            
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message}
            ]
            
            response_text, meta = await invoke_text(
                messages,
                task="playground",
                temperature=0.0,
                max_tokens=1024
            )
            
            latency_ms = int((time.time() - start) * 1000)
            
            results.append({
                "variant": name,
                "prompt": prompt[:200] + "..." if len(prompt) > 200 else prompt,
                "response": response_text,
                "latency_ms": latency_ms,
                "model": meta.get("model", "unknown")
            })
        
        return {
            "user_message": user_message,
            "comparisons": results,
        }
        
    except Exception as e:
        logger.error(f"Prompt comparison failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prompts")
async def list_available_prompts(
    user=Depends(require_admin)
):
    """List available prompts from Langfuse."""
    try:
        from modules.langfuse_prompt_manager import get_prompt_manager
        
        manager = get_prompt_manager()
        prompts = manager.list_available_prompts()
        
        return {
            "prompts": [
                {"name": name, "versions": manager.get_prompt_versions(name)}
                for name in prompts
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to list prompts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prompts/{name}")
async def get_prompt(
    name: str,
    version: Optional[str] = None,
    user=Depends(require_admin)
):
    """Get a specific prompt."""
    try:
        from modules.langfuse_prompt_manager import get_prompt
        
        prompt = get_prompt(name, version)
        return prompt
        
    except Exception as e:
        logger.error(f"Failed to get prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))
