# backend/modules/auto_updater.py
"""Auto Updater: Scheduled pipeline execution for content updates.

Provides functions to create, manage, and execute ingestion pipelines
that automatically re-crawl content sources on a schedule.
"""

import os
import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from enum import Enum

from modules.observability import supabase, log_ingestion_event

logger = logging.getLogger(__name__)


class PipelineStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    DELETED = "deleted"


class SourceType(str, Enum):
    WEBSITE = "website"
    RSS = "rss"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    YOUTUBE = "youtube"


class IngestionPipeline:
    """Represents an automated ingestion pipeline."""
    
    def __init__(
        self,
        twin_id: str,
        source_url: str,
        source_type: SourceType,
        schedule_hours: int = 24,
        crawl_depth: int = 2,
        max_pages: int = 10,
        metadata: Dict[str, Any] = None
    ):
        self.id = str(uuid.uuid4())
        self.twin_id = twin_id
        self.source_url = source_url
        self.source_type = source_type
        self.schedule_hours = schedule_hours
        self.crawl_depth = crawl_depth
        self.max_pages = max_pages
        self.metadata = metadata or {}
        self.status = PipelineStatus.ACTIVE
        self.last_run_at = None
        self.next_run_at = datetime.now(timezone.utc)
        self.run_count = 0
        self.error_count = 0
        self.last_error = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert pipeline to dictionary for storage."""
        return {
            "id": self.id,
            "twin_id": self.twin_id,
            "source_url": self.source_url,
            "source_type": self.source_type.value if isinstance(self.source_type, SourceType) else self.source_type,
            "schedule_hours": self.schedule_hours,
            "crawl_depth": self.crawl_depth,
            "max_pages": self.max_pages,
            "metadata": self.metadata,
            "status": self.status.value if isinstance(self.status, PipelineStatus) else self.status,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "last_error": self.last_error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IngestionPipeline":
        """Create pipeline from stored dictionary."""
        pipeline = cls(
            twin_id=data["twin_id"],
            source_url=data["source_url"],
            source_type=SourceType(data["source_type"]) if data.get("source_type") else SourceType.WEBSITE,
            schedule_hours=data.get("schedule_hours", 24),
            crawl_depth=data.get("crawl_depth", 2),
            max_pages=data.get("max_pages", 10),
            metadata=data.get("metadata", {})
        )
        pipeline.id = data["id"]
        pipeline.status = PipelineStatus(data["status"]) if data.get("status") else PipelineStatus.ACTIVE
        pipeline.last_run_at = datetime.fromisoformat(data["last_run_at"]) if data.get("last_run_at") else None
        pipeline.next_run_at = datetime.fromisoformat(data["next_run_at"]) if data.get("next_run_at") else None
        pipeline.run_count = data.get("run_count", 0)
        pipeline.error_count = data.get("error_count", 0)
        pipeline.last_error = data.get("last_error")
        return pipeline


class PipelineManager:
    """Manager for ingestion pipelines."""
    
    @staticmethod
    def create_pipeline(
        twin_id: str,
        source_url: str,
        source_type: str,
        schedule_hours: int = 24,
        crawl_depth: int = 2,
        max_pages: int = 10,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create a new ingestion pipeline.
        
        Args:
            twin_id: Twin ID
            source_url: URL to monitor
            source_type: Type of source (website, rss, twitter, etc.)
            schedule_hours: Hours between updates
            crawl_depth: Crawl depth for websites
            max_pages: Maximum pages to crawl
            metadata: Additional metadata
        
        Returns:
            Dict with pipeline info
        """
        try:
            # Validate source type
            try:
                source_type_enum = SourceType(source_type)
            except ValueError:
                return {"success": False, "error": f"Invalid source type: {source_type}"}
            
            pipeline = IngestionPipeline(
                twin_id=twin_id,
                source_url=source_url,
                source_type=source_type_enum,
                schedule_hours=schedule_hours,
                crawl_depth=crawl_depth,
                max_pages=max_pages,
                metadata=metadata
            )
            
            # Store in database
            supabase.table("ingestion_pipelines").insert(pipeline.to_dict()).execute()
            
            logger.info(f"Created pipeline {pipeline.id} for {source_url}")
            
            return {
                "success": True,
                "pipeline_id": pipeline.id,
                "source_url": source_url,
                "source_type": source_type,
                "schedule_hours": schedule_hours,
                "next_run_at": pipeline.next_run_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error creating pipeline: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_pipeline(pipeline_id: str) -> Optional[Dict[str, Any]]:
        """Get a single pipeline by ID."""
        try:
            result = supabase.table("ingestion_pipelines").select("*").eq("id", pipeline_id).single().execute()
            return result.data
        except Exception as e:
            logger.error(f"Error fetching pipeline {pipeline_id}: {e}")
            return None
    
    @staticmethod
    def list_pipelines(twin_id: str, include_paused: bool = False) -> List[Dict[str, Any]]:
        """List all pipelines for a twin."""
        try:
            query = supabase.table("ingestion_pipelines").select("*").eq("twin_id", twin_id)
            
            if not include_paused:
                query = query.eq("status", PipelineStatus.ACTIVE.value)
            
            result = query.execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error listing pipelines for {twin_id}: {e}")
            return []
    
    @staticmethod
    def update_pipeline(pipeline_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update pipeline settings."""
        try:
            # Filter allowed fields
            allowed_fields = ["schedule_hours", "crawl_depth", "max_pages", "status", "metadata"]
            filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
            
            if not filtered_updates:
                return {"success": False, "error": "No valid fields to update"}
            
            supabase.table("ingestion_pipelines").update(filtered_updates).eq("id", pipeline_id).execute()
            
            return {"success": True, "pipeline_id": pipeline_id}
        except Exception as e:
            logger.error(f"Error updating pipeline {pipeline_id}: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def delete_pipeline(pipeline_id: str) -> Dict[str, Any]:
        """Soft delete a pipeline."""
        try:
            supabase.table("ingestion_pipelines").update({
                "status": PipelineStatus.DELETED.value
            }).eq("id", pipeline_id).execute()
            
            return {"success": True, "pipeline_id": pipeline_id}
        except Exception as e:
            logger.error(f"Error deleting pipeline {pipeline_id}: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_due_pipelines() -> List[Dict[str, Any]]:
        """Get all pipelines due for execution."""
        try:
            now = datetime.utcnow().isoformat()
            
            result = supabase.table("ingestion_pipelines").select("*").eq(
                "status", PipelineStatus.ACTIVE.value
            ).lte("next_run_at", now).execute()
            
            return result.data or []
        except Exception as e:
            logger.error(f"Error fetching due pipelines: {e}")
            return []


class PipelineExecutor:
    """Executor for running ingestion pipelines."""
    
    @staticmethod
    async def execute_pipeline(pipeline_id: str) -> Dict[str, Any]:
        """
        Execute a single pipeline.
        
        Args:
            pipeline_id: Pipeline ID to execute
        
        Returns:
            Dict with execution results
        """
        pipeline_data = PipelineManager.get_pipeline(pipeline_id)
        
        if not pipeline_data:
            return {"success": False, "error": "Pipeline not found"}
        
        pipeline = IngestionPipeline.from_dict(pipeline_data)
        
        if pipeline.status != PipelineStatus.ACTIVE:
            return {"success": False, "error": f"Pipeline is {pipeline.status.value}"}
        
        try:
            result = None
            
            # Execute based on source type
            if pipeline.source_type == SourceType.WEBSITE:
                from modules.web_crawler import crawl_website
                result = await crawl_website(
                    url=pipeline.source_url,
                    twin_id=pipeline.twin_id,
                    max_pages=pipeline.max_pages,
                    max_depth=pipeline.crawl_depth
                )
                
            elif pipeline.source_type == SourceType.RSS:
                from modules.social_ingestion import RSSFetcher
                result = await RSSFetcher.ingest_feed(
                    url=pipeline.source_url,
                    twin_id=pipeline.twin_id,
                    max_entries=pipeline.max_pages
                )
                
            elif pipeline.source_type == SourceType.TWITTER:
                from modules.social_ingestion import TwitterScraper
                # Extract username from URL
                import re
                username_match = re.search(r'twitter\.com/(\w+)|x\.com/(\w+)', pipeline.source_url)
                if username_match:
                    username = username_match.group(1) or username_match.group(2)
                    result = await TwitterScraper.ingest_user_tweets(
                        username=username,
                        twin_id=pipeline.twin_id,
                        count=pipeline.max_pages
                    )
                else:
                    result = {"success": False, "error": "Invalid Twitter URL"}
                    
            elif pipeline.source_type == SourceType.YOUTUBE:
                from modules.ingestion import ingest_youtube_transcript_wrapper
                result = await ingest_youtube_transcript_wrapper(
                    pipeline.twin_id,
                    pipeline.source_url
                )
                result = {"success": True, "source_id": result}
                
            else:
                result = {"success": False, "error": f"Unsupported source type: {pipeline.source_type}"}
            
            # Update pipeline status
            now = datetime.utcnow()
            next_run = now + timedelta(hours=pipeline.schedule_hours)
            
            update_data = {
                "last_run_at": now.isoformat(),
                "next_run_at": next_run.isoformat(),
                "run_count": pipeline.run_count + 1
            }
            
            if result and result.get("success"):
                update_data["last_error"] = None
            else:
                update_data["error_count"] = pipeline.error_count + 1
                update_data["last_error"] = result.get("error", "Unknown error") if result else "Execution failed"
            
            supabase.table("ingestion_pipelines").update(update_data).eq("id", pipeline_id).execute()
            
            logger.info(f"Executed pipeline {pipeline_id}: {result}")
            
            return {
                "success": result.get("success", False) if result else False,
                "pipeline_id": pipeline_id,
                "result": result,
                "next_run_at": next_run.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error executing pipeline {pipeline_id}: {e}")
            
            # Update error status
            supabase.table("ingestion_pipelines").update({
                "error_count": pipeline.error_count + 1,
                "last_error": str(e),
                "next_run_at": (datetime.utcnow() + timedelta(hours=pipeline.schedule_hours)).isoformat()
            }).eq("id", pipeline_id).execute()
            
            return {"success": False, "error": str(e), "pipeline_id": pipeline_id}
    
    @staticmethod
    async def run_due_pipelines() -> Dict[str, Any]:
        """
        Run all pipelines that are due for execution.
        
        Returns:
            Dict with execution summary
        """
        due_pipelines = PipelineManager.get_due_pipelines()
        
        if not due_pipelines:
            return {"success": True, "executed": 0, "message": "No pipelines due"}
        
        results = []
        success_count = 0
        error_count = 0
        
        for pipeline_data in due_pipelines:
            result = await PipelineExecutor.execute_pipeline(pipeline_data["id"])
            results.append(result)
            
            if result.get("success"):
                success_count += 1
            else:
                error_count += 1
        
        return {
            "success": True,
            "executed": len(results),
            "successful": success_count,
            "failed": error_count,
            "results": results
        }
