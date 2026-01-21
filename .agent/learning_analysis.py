#!/usr/bin/env python3
"""
Week 2+ Learning Analysis Script
Reads workflow outcomes and extracts learning insights
Generates weekly reports for team velocity tracking
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

class LearningAnalyzer:
    """Analyzes workflow outcomes and extracts patterns"""
    
    def __init__(self):
        self.outcomes_file = Path(".agent/learnings/workflow_outcomes.json")
        self.reports_dir = Path(".agent/learnings/weekly_reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.outcomes = []
        
    def load_outcomes(self) -> bool:
        """Load workflow outcomes"""
        try:
            if isinstance(self.outcomes_file, Path) and self.outcomes_file.exists():
                with open(self.outcomes_file, 'r') as f:
                    data = json.load(f)
                    self.outcomes = data if isinstance(data, list) else data.get('workflow_outcomes', [])
                    return True
            return False
        except Exception as e:
            print(f"❌ Error loading outcomes: {e}")
            return False
    
    def calculate_speedup_metrics(self) -> Dict[str, Any]:
        """Calculate speedup metrics from outcomes"""
        if not self.outcomes:
            return {}
        
        speedups = []
        time_saved = 0
        
        for outcome in self.outcomes:
            if isinstance(outcome, dict):
                baseline = outcome.get('baseline_time_minutes')
                actual = outcome.get('time_spent_minutes')
                if baseline and actual and actual > 0:
                    speedup = baseline / actual
                    speedups.append(speedup)
                    time_saved += (baseline - actual)
        
        if not speedups:
            return {}
        
        return {
            'avg_speedup': round(sum(speedups) / len(speedups), 2),
            'max_speedup': round(max(speedups), 2),
            'min_speedup': round(min(speedups), 2),
            'total_time_saved_minutes': int(time_saved),
            'avg_time_saved_per_task': round(time_saved / len(speedups), 1),
            'tasks_measured': len(speedups)
        }
    
    def extract_patterns(self) -> Dict[str, List[str]]:
        """Extract patterns used and discovered"""
        patterns_used = {}
        patterns_discovered = []
        
        for outcome in self.outcomes:
            if not isinstance(outcome, dict):
                continue
                
            # Count patterns applied
            for pattern in outcome.get('patterns_applied', []):
                patterns_used[pattern] = patterns_used.get(pattern, 0) + 1
            
            # Collect patterns discovered
            for pattern in outcome.get('patterns_discovered', []):
                if pattern not in patterns_discovered:
                    patterns_discovered.append(pattern)
        
        # Sort by frequency
        top_patterns = sorted(
            patterns_used.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return {
            'top_patterns_used': [p[0] for p in top_patterns[:5]],
            'patterns_discovered': patterns_discovered,
            'pattern_usage_counts': dict(top_patterns[:10])
        }
    
    def analyze_mcps(self) -> Dict[str, int]:
        """Analyze MCP usage"""
        mcp_usage = {}
        
        for outcome in self.outcomes:
            if not isinstance(outcome, dict):
                continue
            for mcp in outcome.get('mcps_used', []):
                mcp_usage[mcp] = mcp_usage.get(mcp, 0) + 1
        
        return dict(sorted(
            mcp_usage.items(),
            key=lambda x: x[1],
            reverse=True
        ))
    
    def detect_anti_patterns(self) -> Dict[str, Any]:
        """Analyze anti-patterns caught"""
        anti_patterns_found = {}
        anti_pattern_count = 0
        
        for outcome in self.outcomes:
            if not isinstance(outcome, dict):
                continue
            anti_patterns = outcome.get('anti_patterns_found', [])
            anti_pattern_count += len(anti_patterns)
            
            for ap in anti_patterns:
                anti_patterns_found[ap] = anti_patterns_found.get(ap, 0) + 1
        
        return {
            'total_anti_patterns_caught': anti_pattern_count,
            'anti_pattern_types': dict(sorted(
                anti_patterns_found.items(),
                key=lambda x: x[1],
                reverse=True
            )),
            'regressions_prevented': anti_pattern_count
        }
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive weekly report"""
        if not self.load_outcomes():
            print("⚠️  No outcomes to analyze yet")
            return {}
        
        speedup_metrics = self.calculate_speedup_metrics()
        patterns = self.extract_patterns()
        mcp_usage = self.analyze_mcps()
        anti_patterns = self.detect_anti_patterns()
        
        report = {
            'generated': datetime.now().isoformat(),
            'period': 'Week 2',
            'outcomes_analyzed': len(self.outcomes),
            'speedup': speedup_metrics,
            'patterns': patterns,
            'mcp_usage': mcp_usage,
            'anti_patterns': anti_patterns,
            'team_velocity': {
                'tasks_completed': len(self.outcomes),
                'time_saved_total_hours': round(speedup_metrics.get('total_time_saved_minutes', 0) / 60, 1),
                'estimated_velocity_increase': f"{round((speedup_metrics.get('avg_speedup', 1) - 1) * 100)}%"
            },
            'insights': self._generate_insights(speedup_metrics, patterns, anti_patterns),
            'recommendations': self._generate_recommendations(patterns, mcp_usage)
        }
        
        return report
    
    def _generate_insights(self, speedup: Dict, patterns: Dict, anti_patterns: Dict) -> List[str]:
        """Generate key insights"""
        insights = []
        
        if speedup.get('avg_speedup', 0) >= 8:
            insights.append(f"✅ Target speedup achieved: {speedup['avg_speedup']}x")
        elif speedup.get('avg_speedup', 0) > 0:
            insights.append(f"📈 Average speedup: {speedup['avg_speedup']}x (target: 8x)")
        
        if patterns.get('patterns_discovered'):
            insights.append(f"🔍 New patterns discovered: {len(patterns['patterns_discovered'])}")
        
        top_patterns = patterns.get('top_patterns_used', [])
        if top_patterns:
            insights.append(f"⭐ Most used pattern: {top_patterns[0]}")
        
        if anti_patterns.get('total_anti_patterns_caught'):
            insights.append(f"🛡️  Anti-patterns prevented: {anti_patterns['total_anti_patterns_caught']} regressions avoided")
        
        if speedup.get('total_time_saved_minutes', 0) > 0:
            hours = round(speedup['total_time_saved_minutes'] / 60, 1)
            insights.append(f"⏰ Total time saved: {hours} hours this week")
        
        return insights
    
    def _generate_recommendations(self, patterns: Dict, mcp_usage: Dict) -> List[str]:
        """Generate recommendations for improvement"""
        recommendations = []
        
        if not mcp_usage.get('grep'):
            recommendations.append("💡 Consider using grep MCP more for pattern discovery")
        
        if patterns.get('patterns_discovered'):
            recommendations.append(f"📝 Validate and add {len(patterns['patterns_discovered'])} new patterns to index")
        
        if len(mcp_usage) < 4:
            recommendations.append("🎯 Increase adoption of all 4 MCPs - focus on underused ones")
        
        recommendations.append("🔄 Schedule weekly team sync to discuss discoveries")
        
        return recommendations
    
    def save_report(self, report: Dict[str, Any]) -> bool:
        """Save report to file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.reports_dir / f"week2_report_{timestamp}.json"
            
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            print(f"✅ Report saved: {report_file}")
            return True
        except Exception as e:
            print(f"❌ Error saving report: {e}")
            return False
    
    def print_summary(self, report: Dict[str, Any]) -> None:
        """Print human-readable summary"""
        print("\n" + "="*80)
        print("📊 WEEK 2 LEARNING ANALYSIS REPORT")
        print("="*80)
        
        print(f"\n📈 SPEEDUP METRICS")
        print("-" * 80)
        speedup = report.get('speedup', {})
        if speedup:
            print(f"  Average Speedup:        {speedup.get('avg_speedup', 'N/A')}x")
            print(f"  Max Speedup:            {speedup.get('max_speedup', 'N/A')}x")
            print(f"  Total Time Saved:       {speedup.get('total_time_saved_minutes', 0)} minutes ({round(speedup.get('total_time_saved_minutes', 0) / 60, 1)} hours)")
            print(f"  Tasks Measured:         {speedup.get('tasks_measured', 0)}")
        
        print(f"\n🎯 PATTERN ANALYSIS")
        print("-" * 80)
        patterns = report.get('patterns', {})
        if patterns.get('top_patterns_used'):
            print(f"  Top Patterns Used:")
            for i, pattern in enumerate(patterns['top_patterns_used'][:5], 1):
                count = patterns.get('pattern_usage_counts', {}).get(pattern, 0)
                print(f"    {i}. {pattern} ({count} times)")
        
        if patterns.get('patterns_discovered'):
            print(f"\n  New Patterns Discovered: {len(patterns['patterns_discovered'])}")
            for pattern in patterns['patterns_discovered'][:3]:
                print(f"    • {pattern}")
        
        print(f"\n🛠️  MCP USAGE")
        print("-" * 80)
        mcp_usage = report.get('mcp_usage', {})
        for mcp, count in list(mcp_usage.items())[:4]:
            print(f"  {mcp.capitalize():15} {count:3} uses")
        
        print(f"\n🛡️  ANTI-PATTERN PREVENTION")
        print("-" * 80)
        anti_patterns = report.get('anti_patterns', {})
        print(f"  Regressions Prevented:  {anti_patterns.get('total_anti_patterns_caught', 0)}")
        
        print(f"\n✨ KEY INSIGHTS")
        print("-" * 80)
        for insight in report.get('insights', []):
            print(f"  {insight}")
        
        print(f"\n💡 RECOMMENDATIONS")
        print("-" * 80)
        for rec in report.get('recommendations', []):
            print(f"  {rec}")
        
        print(f"\n🎯 TEAM VELOCITY")
        print("-" * 80)
        velocity = report.get('team_velocity', {})
        print(f"  Tasks Completed:        {velocity.get('tasks_completed', 0)}")
        print(f"  Time Saved (hours):     {velocity.get('time_saved_total_hours', 0)}")
        print(f"  Velocity Increase:      {velocity.get('estimated_velocity_increase', 'N/A')}")
        
        print("\n" + "="*80 + "\n")


def main():
    """Run learning analysis"""
    print("🔍 Starting Learning Analysis...\n")
    
    analyzer = LearningAnalyzer()
    report = analyzer.generate_report()
    
    if report:
        analyzer.print_summary(report)
        analyzer.save_report(report)
        print("✅ Analysis complete!")
        return 0
    else:
        print("⚠️  No outcomes available yet. Run some tasks and log outcomes first.")
        return 1


if __name__ == "__main__":
    exit(main())
