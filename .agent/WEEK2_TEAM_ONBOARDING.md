# 👥 Week 2 Team Onboarding Guide

**Objective**: Get your team trained and using MCPs productively  
**Duration**: 1-2 hours  
**Outcome**: 100% team adoption of MCPs

---

## 🎯 What This Week Is About

**Goal**: Execute real development tasks using MCPs and measure productivity gains.

**Expected Results**:
- ✅ Each developer completes 3 real tasks
- ✅ Average speedup of **8x** (vs. 6x baseline)
- ✅ 15+ task outcomes logged
- ✅ 3+ new patterns discovered
- ✅ Team ready for Month 2 exponential improvements

---

## 📋 Team Onboarding Checklist

### Pre-Training Setup (Lead)
- [ ] Ensure all 5 MCPs configured in `.agent/mcp.json`
- [ ] Verify workflow_outcomes.json template is ready
- [ ] Have 5 real development tasks identified
- [ ] Print `.agent/DEVELOPER_QUICK_CARD.md` (1 per person)
- [ ] Create team Slack channel: `#mcp-discoveries`

### Team Training (All)
- [ ] Read: `.agent/MCP_QUICK_REFERENCE.md` (15 min)
- [ ] Test: Run 1 example from each MCP (15 min)
- [ ] Verify: All 4 MCPs work on your machine (5 min)
- [ ] Q&A: Ask questions about MCPs (10 min)

### Task Execution (Individual)
- [ ] Get assigned a development task
- [ ] Use MCPs to find relevant patterns
- [ ] Time the task (Windows timer: Win+;)
- [ ] Log outcome to workflow_outcomes.json
- [ ] Share 1 discovery with team

### Weekly Analysis (Lead)
- [ ] Run `.agent/learning_analysis.py` Friday evening
- [ ] Review metrics with team Monday morning
- [ ] Celebrate wins and discoveries

---

## 📅 1-Hour Training Session

### Minute 0-5: Welcome & Motivation
**What**: Set expectations for the week

```
"This week, we're going from learning about MCPs to using them on real work.
Here's what to expect:
  • 15 min: Learn MCPs
  • 30 min: Practice on real task
  • Daily: Use MCPs, track time, log outcome
  • Friday: See team speedup metrics

Expected result: 8x average speedup by end of week."
```

### Minute 5-20: MCP Overview
**What**: Quick tour of each MCP

**Use slides or screen share**:

1. **Filesystem MCP** (4 min)
   - What: Semantic file navigation
   - Example: `filesystem search "auth_check_standard"`
   - Speedup: 15 min → 2 min (7.5x)
   - Use when: Finding where code patterns exist

2. **Git MCP** (4 min)
   - What: Code history and blame
   - Example: `git log -S "multi_tenant_filter" --oneline`
   - Speedup: 10 min → 1 min (10x)
   - Use when: Understanding code evolution

3. **Grep MCP** (4 min)
   - What: Fast pattern matching
   - Example: `grep -r "verify_owner" backend/`
   - Speedup: 5 min → 0.5 min (10x)
   - Use when: Finding all instances of a pattern

4. **Supabase MCP** (4 min)
   - What: Schema inspection without dashboard
   - Example: `supabase schema inspect twins`
   - Speedup: 8 min → 1 min (8x)
   - Use when: Understanding database structure

### Minute 20-35: Hands-On Practice
**What**: Everyone tests an MCP

**Setup** (5 min):
- Open terminal
- Open `.agent/MCP_QUICK_REFERENCE.md`
- Be ready to copy-paste

**Exercises** (10 min):
1. Try `filesystem search "auth_check_standard"` (check if it works)
2. Try `git log -S "multi_tenant_filter" --oneline | head -5`
3. Try `grep -r "verify_owner" backend/ | head -3`
4. Try `supabase schema inspect twins`

**Check-in** (5 min):
- ✅ Did all MCPs work? Yes!
- ❌ Did one fail? Let's troubleshoot together
- Share screen if having issues

### Minute 35-45: Pattern Index Tour
**What**: Show how to use patterns before coding

**Demo**:
1. Open `.agent/indexes/patterns.json`
2. Search for "multi_tenant_filter"
3. Show example usage
4. Show anti-pattern (what NOT to do)
5. Commit to memory: **Use this in EVERY query**

### Minute 45-55: Task Assignment & Outcome Logging
**What**: Explain how to log results

**Task Assignment**:
- Here are 5 real tasks for this week
- Pick your favorite or I'll assign one
- You'll complete it using MCPs
- Time how long it takes

**Outcome Logging**:
- After each task, log to `.agent/learnings/workflow_outcomes.json`
- Use template from file
- Fill in: time, baseline, speedup, patterns found
- Example shown on screen

### Minute 55-60: Q&A + Wrap-Up
**Questions?**
- How do I use grep to find X?
- What if MCP doesn't work?
- How do I log the outcome?

**Action Items**:
- Start your first task today
- Time it
- Log the outcome
- Share discovery in #mcp-discoveries

---

## 🎓 Key Concepts to Teach

### 1. Pattern = Copy-Paste Solution
**Concept**: Patterns are proven code templates

**Teach**:
```
Before: "I need to add auth to this endpoint"
        Search Google, Stack Overflow, other code → 15 min

After:  "I need to add auth to this endpoint"
        Look up auth_check_standard pattern → 2 min
        Copy-paste template → Done!
```

### 2. MCP = Pattern Discovery Tool
**Concept**: MCPs find patterns instantly

**Teach**:
```
Manual: grep -r "auth_check_standard" backend/
        → 5 minutes, error-prone, might miss things

MCP:    filesystem search "auth_check_standard"
        → 30 seconds, semantic, finds similar names
```

### 3. Speedup = Baseline vs. Actual
**Concept**: Measure time saved

**Teach**:
```
Baseline (old way): How long would this take manually?
Actual (new way):   How long did it take with MCPs?
Speedup:            Baseline / Actual = X times faster

Example:
  Baseline: 45 minutes (manual searching)
  Actual:   15 minutes (using MCPs)
  Speedup:  3x faster
```

### 4. Learning Pipeline = System Improves Over Time
**Concept**: Every task makes the system smarter

**Teach**:
```
Week 1: Setup (6x speedup)
        ↓ Everyone logs outcomes
Week 2: Analysis (8x speedup)
        ↓ Patterns extracted, new insights
Week 3: Evolution (10x speedup)
        ↓ System updated, improvements compounded
Week 4+: Exponential (10x+ speedup)
        System self-improves automatically
```

---

## 💻 Demo: Your First Task

**Live Demo** (if time allows):

1. **Pick a Real Task**
   - "Add validation to new endpoint"

2. **Use MCPs to Find Similar Code**
   ```powershell
   filesystem search "endpoint"
   # Finds all endpoints, opens similar one
   ```

3. **Check Pattern Index**
   ```
   Open: .agent/indexes/patterns.json
   Search: "validation"
   Copy: Template for validation_pattern
   ```

4. **Time It**
   - Manual way: 30 min searching Google
   - MCP way: 5 min using MCPs
   - Speedup: 6x

5. **Log It**
   ```json
   {
     "task": "Add validation to endpoint",
     "time_spent_minutes": 5,
     "baseline_time_minutes": 30,
     "mcps_used": ["filesystem"],
     "speedup": 6,
     "patterns_applied": ["validation_pattern"]
   }
   ```

6. **Share It**
   - Slack: "Just added validation using MCPs, 6x faster! Check out validation_pattern in index."

---

## 📊 Success Metrics to Track

### Daily (You)
- [ ] Did I use MCPs today?
- [ ] Did I time my tasks?
- [ ] Did I log the outcome?

### Weekly (Team Lead)
- [ ] Tasks logged: ___/15 (target)
- [ ] Average speedup: ___x (target: 8x)
- [ ] Adoption rate: ___%  (target: 100%)
- [ ] Patterns discovered: ___ (target: 3+)

### By Friday (Report)
- Average speedup vs. baseline
- Top MCPs used
- Most popular patterns
- New patterns discovered
- Anti-patterns prevented
- Time saved (in hours)

---

## 🔄 Daily Workflow (For Team Members)

### Morning (Start of Day)
- Check Slack #mcp-discoveries for team findings
- Get your assigned task
- Have `.agent/MCP_QUICK_REFERENCE.md` ready
- Start timer on task

### During Task
- Use MCPs for pattern discovery
- When stuck: "Let me search for this pattern"
- When learning something new: "This should go in the pattern index"
- Document anything interesting

### End of Task
- Stop timer
- Calculate speedup
- Log outcome to workflow_outcomes.json
- Share finding in #mcp-discoveries

### Friday EOD
- Review all your logged outcomes
- Prepare for Monday team briefing
- Think about new patterns to add

---

## 🆘 Troubleshooting Quick Guide

### MCP Not Working?
**Solution**:
1. Check `.agent/MCP_USAGE.md` troubleshooting section
2. Try restarting IDE (Ctrl+Shift+P → Developer: Reload Window)
3. Verify path is correct
4. Ask in #mcp-discoveries, we'll help

### Don't Know Which Pattern to Use?
**Solution**:
1. Search `.agent/indexes/patterns.json`
2. Ask team lead
3. Share discovery in #mcp-discoveries
4. We'll add it to index

### Having Trouble Logging Outcome?
**Solution**:
1. Follow template exactly (copy-paste structure)
2. Example: Look at first entry in workflow_outcomes.json
3. Make sure JSON is valid (use JSON validator)
4. Ask if stuck

### Can't Achieve 8x Speedup?
**Solution**:
1. That's OK! Baseline is 6x, 8x is target
2. Log honest numbers
3. We'll analyze why and improve
4. System learns from every outcome

---

## 📞 Communication Channels

### Slack Channel: #mcp-discoveries
**Use for**:
- Sharing MCP findings
- Asking quick questions
- Celebrating wins
- Posting pattern discoveries

**Example messages**:
- "Found auth_check_standard, saved 15 min using filesystem MCP!"
- "Should we add validation_pattern to index? It appears 12 times"
- "Git MCP just showed me code evolution, super helpful"
- "Caught multi_tenant_filter missing - prevented a bug!"

### Weekly Team Meeting: Friday 5 PM
**Agenda**:
1. Review team speedup metrics
2. Discuss new patterns discovered
3. Show any interesting findings
4. Plan for next week

### Async: workflow_outcomes.json
**Updates**:
- Every developer updates after each task
- Lead reviews for patterns Friday EOD
- Used to generate team report

---

## 🎁 Rewards & Recognition

### This Week
- ✅ Developer who completes 3 tasks = "MCP Master"
- ✅ Developer who discovers most patterns = "Pattern Scout"
- ✅ Team if achieves 8x+ speedup = "Velocity Heroes"

### Next Week
- ✅ Most time saved = featured in team standup
- ✅ Best pattern discovery = added to pattern index
- ✅ Zero regressions = quality award

---

## 📈 Expected Week 2 Results

### By End of Friday
- [ ] 15 tasks completed (3 per developer, 5 developers)
- [ ] 15 outcomes logged
- [ ] Average speedup: **8x** (vs. 6x baseline)
- [ ] **300 minutes saved** (5 hours of team time)
- [ ] 3+ new patterns discovered
- [ ] 2+ anti-patterns prevented
- [ ] **37% team velocity increase**

### Recognition
```
🎉 Week 2 Success!
   • Team speedup: 8.2x
   • Time saved: 5 hours
   • New patterns: 4
   • Regressions prevented: 3
   • Adoption rate: 100%

Ready for Week 3: 10x+ speedup!
```

---

## Next Week (Week 3)

**Goal**: Maintain 10x+ speedup, start seeing compound learning effects

**What's New**:
- Learning pipeline more mature
- More patterns in index
- Team confident with MCPs
- Exponential improvements begin

---

**Training Complete! 🎓**

Now go execute real tasks with MCPs and make development 8x faster! 🚀

Questions? Check `.agent/DEVELOPER_QUICK_CARD.md` or ask in #mcp-discoveries
