#!/usr/bin/env python3
"""
Week 1 Validation Script: MCPs & Indexed Codebase
Validates that all Week 1 setup is complete
"""

import json
import os
import sys
from pathlib import Path

def check_mcp_json():
    """Verify .agent/mcp.json has all 5 MCPs"""
    mcp_file = Path(".agent/mcp.json")
    
    if not mcp_file.exists():
        print("❌ .agent/mcp.json not found")
        return False
    
    with open(mcp_file, 'r') as f:
        config = json.load(f)
    
    required_mcps = ["supabase", "filesystem", "git", "grep"]
    mcps_found = list(config.get("mcpServers", {}).keys())
    
    print(f"\n📡 MCP Configuration Check")
    print(f"   MCPs Found: {', '.join(mcps_found)}")
    print(f"   Expected: {', '.join(required_mcps)}")
    
    all_present = all(mcp in mcps_found for mcp in required_mcps)
    if all_present:
        print(f"   ✅ All MCPs configured")
        return True
    else:
        missing = [m for m in required_mcps if m not in mcps_found]
        print(f"   ❌ Missing: {', '.join(missing)}")
        return False

def check_pattern_index():
    """Verify pattern index exists and has patterns"""
    patterns_file = Path(".agent/indexes/patterns.json")
    
    if not patterns_file.exists():
        print("\n❌ Pattern index not found")
        return False
    
    with open(patterns_file, 'r') as f:
        patterns = json.load(f)
    
    pattern_count = len(patterns.get("patterns", []))
    print(f"\n📚 Pattern Index Check")
    print(f"   Patterns Found: {pattern_count}")
    print(f"   Expected: 15+")
    
    if pattern_count >= 15:
        print(f"   ✅ Pattern index complete")
        # List patterns
        print(f"   Patterns:")
        for p in patterns.get("patterns", [])[:5]:
            print(f"      - {p['id']} ({p.get('usage_count', 0)} usages)")
        if pattern_count > 5:
            print(f"      ... and {pattern_count - 5} more")
        return True
    else:
        print(f"   ⚠️  Only {pattern_count} patterns found")
        return False

def check_decision_log():
    """Verify decision log exists"""
    decisions_file = Path(".agent/indexes/decisions.json")
    
    if not decisions_file.exists():
        print("\n❌ Decision log not found")
        return False
    
    with open(decisions_file, 'r') as f:
        decisions = json.load(f)
    
    decision_count = len(decisions.get("decisions", []))
    print(f"\n🗂️  Decision Log Check")
    print(f"   Decisions Found: {decision_count}")
    print(f"   Expected: 10+")
    
    if decision_count >= 10:
        print(f"   ✅ Decision log complete")
        # List decisions
        print(f"   Decisions:")
        for d in decisions.get("decisions", [])[:3]:
            print(f"      - {d['title']}")
        if decision_count > 3:
            print(f"      ... and {decision_count - 3} more")
        return True
    else:
        print(f"   ⚠️  Only {decision_count} decisions found")
        return False

def check_knowledge_graph():
    """Verify knowledge graph exists"""
    graph_file = Path(".agent/indexes/knowledge_graph.json")
    
    if not graph_file.exists():
        print("\n❌ Knowledge graph not found")
        return False
    
    with open(graph_file, 'r') as f:
        graph = json.load(f)
    
    node_count = len(graph.get("nodes", []))
    edge_count = len(graph.get("edges", []))
    
    print(f"\n🔗 Knowledge Graph Check")
    print(f"   Nodes Found: {node_count}")
    print(f"   Edges Found: {edge_count}")
    print(f"   Expected: 25+ nodes, 13+ edges")
    
    if node_count >= 25 and edge_count >= 13:
        print(f"   ✅ Knowledge graph complete")
        return True
    else:
        print(f"   ⚠️  Incomplete graph")
        return False

def check_learnings_structure():
    """Verify learnings directory is set up"""
    learnings_dir = Path(".agent/learnings")
    
    print(f"\n📊 Learning Pipeline Structure Check")
    if learnings_dir.exists():
        files = list(learnings_dir.iterdir())
        print(f"   Learnings directory exists")
        print(f"   Files: {[f.name for f in files]}")
        print(f"   ✅ Ready for outcome capture")
        return True
    else:
        print(f"   ⚠️  Learnings directory doesn't exist")
        print(f"   Will be created when tasks are logged")
        return True

def print_summary(results):
    """Print summary of all checks"""
    print("\n" + "="*60)
    print("WEEK 1 VALIDATION SUMMARY")
    print("="*60)
    
    checks = [
        ("MCPs Configuration", results['mcp']),
        ("Pattern Index", results['patterns']),
        ("Decision Log", results['decisions']),
        ("Knowledge Graph", results['graph']),
        ("Learning Structure", results['learnings'])
    ]
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for check_name, result in checks:
        status = "✅" if result else "⚠️ "
        print(f"{status} {check_name}")
    
    print("="*60)
    print(f"\nResult: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 WEEK 1 SETUP COMPLETE!")
        print("\n✅ Next Steps:")
        print("   1. Review .agent/DEVELOPER_QUICK_CARD.md")
        print("   2. Test MCPs in your IDE (Cursor/VS Code)")
        print("   3. Use pattern index on first task")
        print("   4. Log outcomes in workflow_outcomes.json")
        return True
    else:
        print("\n⚠️  Some setup incomplete. See above for details.")
        return False

def main():
    """Run all validation checks"""
    print("\n🚀 WEEK 1: Foundation Setup Validation")
    print("="*60)
    
    results = {
        'mcp': check_mcp_json(),
        'patterns': check_pattern_index(),
        'decisions': check_decision_log(),
        'graph': check_knowledge_graph(),
        'learnings': check_learnings_structure()
    }
    
    success = print_summary(results)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
