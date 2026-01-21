#!/usr/bin/env python3
"""
Improvement Tracking Script
Measures improvements to working features over time
Purpose: Track optimization impact
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List

class ImprovementTracker:
    def __init__(self):
        self.metrics_file = os.path.join(
            os.path.dirname(__file__), 
            "..", 
            "eval",
            "improvement_metrics.json"
        )
        self.load_baseline()
    
    def load_baseline(self):
        """Load or create baseline metrics"""
        if os.path.exists(self.metrics_file):
            with open(self.metrics_file, 'r') as f:
                self.data = json.load(f)
        else:
            self.data = {
                "baseline": {},
                "current": {},
                "improvements": [],
                "last_updated": None
            }
    
    def save_metrics(self):
        """Save metrics to file"""
        self.data["last_updated"] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
        with open(self.metrics_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def measure_auth_latency(self) -> float:
        """Measure authentication endpoint latency"""
        try:
            import requests
            times = []
            for _ in range(5):  # 5 samples
                start = time.time()
                requests.post(
                    "http://localhost:8000/auth/sync-user",
                    headers={"Authorization": "Bearer test"},
                    timeout=10
                )
                times.append((time.time() - start) * 1000)
                time.sleep(0.1)
            
            # Return median (avoid outliers)
            return sorted(times)[len(times)//2]
        except:
            return None
    
    def measure_chat_latency(self, twin_id: str = "test") -> float:
        """Measure chat endpoint latency"""
        try:
            import requests
            start = time.time()
            requests.post(
                f"http://localhost:8000/chat/{twin_id}",
                headers={"Authorization": "Bearer test"},
                json={"message": "test"},
                timeout=10
            )
            return (time.time() - start) * 1000
        except:
            return None
    
    def measure_vector_search_latency(self) -> float:
        """Measure vector search latency"""
        try:
            from modules.clients import get_pinecone_client
            import time
            
            client = get_pinecone_client()
            index = client.Index(os.getenv("PINECONE_INDEX_NAME"))
            
            times = []
            for _ in range(3):
                start = time.time()
                index.query(
                    vector=[0.1] * 3072,
                    top_k=5,
                    include_metadata=True
                )
                times.append((time.time() - start) * 1000)
            
            return sorted(times)[len(times)//2]
        except:
            return None
    
    def measure_all_metrics(self):
        """Measure all performance metrics"""
        print("Measuring performance metrics...")
        
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "auth_latency_ms": self.measure_auth_latency(),
            "chat_latency_ms": self.measure_chat_latency(),
            "vector_search_latency_ms": self.measure_vector_search_latency(),
        }
        
        # Store as current
        self.data["current"] = metrics
        
        # Set baseline if not exists
        if not self.data["baseline"]:
            self.data["baseline"] = metrics
            print("✅ Baseline metrics set")
        else:
            # Calculate improvements
            self.calculate_improvements()
        
        self.save_metrics()
        return metrics
    
    def calculate_improvements(self):
        """Calculate improvements from baseline"""
        baseline = self.data["baseline"]
        current = self.data["current"]
        
        improvements = []
        
        for metric_name in ["auth_latency_ms", "chat_latency_ms", "vector_search_latency_ms"]:
            if metric_name in baseline and metric_name in current:
                baseline_val = baseline[metric_name]
                current_val = current[metric_name]
                
                if baseline_val and current_val:
                    pct_change = ((baseline_val - current_val) / baseline_val) * 100
                    
                    improvement = {
                        "metric": metric_name,
                        "baseline": baseline_val,
                        "current": current_val,
                        "improvement_percent": pct_change,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    improvements.append(improvement)
                    
                    status = "✅" if pct_change > 0 else "❌"
                    print(f"{status} {metric_name}: {pct_change:+.1f}%")
        
        self.data["improvements"] = improvements

def main():
    tracker = ImprovementTracker()
    metrics = tracker.measure_all_metrics()
    
    print("\n=== Current Metrics ===")
    for key, value in metrics.items():
        if value is not None:
            print(f"{key}: {value:.1f}")

if __name__ == "__main__":
    main()
