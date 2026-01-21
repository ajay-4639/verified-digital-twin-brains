# MCP Usage Guide

> **Purpose**: Quick reference for using Model Context Protocol servers in this project  
> **Created**: 2025-01-20

---

## Quick Reference

| MCP | Purpose | Typical Query | Speedup |
|---|---|---|---|
| **filesystem** | Navigate codebase | "Find all auth guard usages" | 5x |
| **git** | History & blame | "Show evolution of this pattern" | 10x |
| **grep** | Semantic search | "Find all multi-tenant filters" | 8x |
| **postgres** | Schema inspection | "Show verified_qna table schema" | 8x |
| **supabase** | Direct DB access | "List all twins" | Real-time |
| **openapi** | API contracts | "Validate endpoint schema" | 15x |

---

## 1. Filesystem MCP

### Purpose
Navigate the 50K+ line codebase without manual file searching.

### Common Queries
```
"Find all router modules"
→ Returns: backend/routers/ directory structure

"Show auth_guard usage across backend"
→ Returns: All files importing auth_guard

"Find all Python files in modules/"
→ Returns: All .py files in backend/modules/

"Search for supabase client initialization"
→ Returns: All files containing 'supabase' instantiation
```

### When to Use
- Finding related files (e.g., all routers that touch twins)
- Understanding file organization
- Locating where a feature is implemented

### When NOT to Use
- Searching for code patterns (use **grep** MCP instead)
- Looking for specific error messages (use **grep** MCP)

---

## 2. Git MCP

### Purpose
Understand codebase evolution and make regression-safe changes.

### Common Queries
```
"Show git history of backend/modules/auth_guard.py"
→ Returns: All commits that touched this file

"Show blame for line 42 of backend/modules/auth_guard.py"
→ Returns: Who wrote this line and why

"Show diff between main and this branch"
→ Returns: What changed

"Show commits mentioning 'verified_qna'"
→ Returns: All commits related to verified QnA feature
```

### When to Use
- Understanding why a pattern was introduced
- Checking if a change might cause regression
- Finding related changes across files
- Reading commit messages for context

### When NOT to Use
- Finding files with specific code (use **filesystem** MCP)

---

## 3. Grep MCP

### Purpose
Semantic search across codebase for code patterns.

### Common Queries
```
"Find all multi-tenant filters"
→ Returns: All .eq('tenant_id', ...) patterns

"Find all uses of get_current_user dependency"
→ Returns: All routes using auth check

"Show all verified_qna table queries"
→ Returns: All Supabase queries for verified_qna

"Find all HTTPException 403 errors"
→ Returns: All access denied errors

"Find all confidence score checks"
→ Returns: All escalation decision logic
```

### Pattern Search Examples
```
# Find database queries
"supabase.table.*\.execute()"

# Find error handling
"raise HTTPException.*status_code=(401|403|404)"

# Find auth checks
"Depends\(get_current_user\)"

# Find RLS policies
"CREATE POLICY.*verified_qna"
```

### When to Use
- Finding all implementations of a pattern
- Identifying inconsistencies (e.g., some 403 errors use different message)
- Locating all places that need updating when pattern changes
- Building pattern index

### Regex Syntax
```
Use standard Python regex with:
- | for alternation (word1|word2)
- .* for wildcard
- \d for digits
- \s for whitespace
```

---

## 4. Postgres MCP

### Purpose
Real-time database schema inspection without manual SQL.

### Common Queries
```
"Show verified_qna table schema"
→ Returns: Column names, types, constraints

"List all tables in public schema"
→ Returns: All table names

"Show primary keys for twins table"
→ Returns: Column-level constraint info

"Show foreign key references from verified_qna"
→ Returns: All FK relationships

"Show RLS policies for verified_qna table"
→ Returns: All active policies
```

### When to Use
- Verifying column exists before referencing
- Checking constraint types (NOT NULL, UNIQUE, FK)
- Validating RLS policies are in place
- Understanding table relationships

### When NOT to Use
- Making schema changes (use **database_migration_template** pattern)
- Viewing data (use **supabase** MCP instead)

---

## 5. Supabase MCP

### Purpose
Direct database access for querying and testing.

### Common Queries
```
"Query: SELECT * FROM twins LIMIT 1"
→ Returns: Twin records

"Query: SELECT COUNT(*) FROM verified_qna WHERE is_active = true"
→ Returns: Count of active verified answers

"Execute: INSERT INTO ... returning *"
→ Returns: Created record

"Query: SELECT * FROM access_groups WHERE tenant_id = ..."
→ Returns: Groups for tenant
```

### When to Use
- Verifying data after migrations
- Debugging multi-tenant filters
- Testing RLS policies
- Spot-checking production data

### When NOT to Use
- Bulk operations (use backend instead)
- Modifying schema (use migrations)

---

## 6. OpenAPI MCP

### Purpose
API contract validation and documentation.

### Common Queries
```
"Show API contract for GET /twins/{twin_id}"
→ Returns: Request/response schema

"Validate POST /messages request schema"
→ Returns: Schema validation report

"List all endpoints"
→ Returns: All REST endpoints

"Show breaking changes from last version"
→ Returns: Endpoints with changed schemas
```

### When to Use
- Checking endpoint parameters before implementation
- Validating request body schema
- Detecting breaking changes before merge
- Generating TypeScript client types

---

## Workflow: Using MCPs Together

### Scenario 1: Adding New Feature
```
1. Use GREP to find similar patterns
   "Find all verified_qna queries"
   
2. Use FILESYSTEM to locate related routers
   "Show routers that reference verified_qna"
   
3. Use POSTGRES to verify schema
   "Show verified_qna table schema"
   
4. Use OPENAPI to check endpoint contract
   "Show POST /verified_qna schema"
   
5. Use GIT to understand decision
   "Show commits mentioning verified_qna"
```

### Scenario 2: Fixing Regression
```
1. Use GIT to identify when regression was introduced
   "Show git blame for line X"
   
2. Use GREP to find all related patterns
   "Find all multi-tenant filters"
   
3. Use FILESYSTEM to locate all affected files
   "Find all routers using this pattern"
   
4. Use POSTGRES to verify schema
   "Show affected table schema"
   
5. Use SUPABASE to test fix
   "Query with correct filter"
```

### Scenario 3: Implementing New Pattern
```
1. Use GREP to find existing implementations
   "Find all auth check patterns"
   
2. Use GIT to understand history
   "Show evolution of auth_guard.py"
   
3. Use FILESYSTEM to locate all files that should use pattern
   "Find all routers"
   
4. Document in .agent/indexes/patterns.json
5. Use GREP to verify adoption
   "Find all routers using new pattern"
```

---

## MCP Limitations & Workarounds

| Limitation | Workaround |
|---|---|
| Grep MCP may return too many results | Use more specific regex patterns |
| Filesystem MCP is read-only | Use replace_string_in_file tool for edits |
| Postgres MCP schema info may be stale | Reload PostgREST schema cache in Supabase |
| Supabase MCP needs service role key | Already configured in .agent/mcp.json |
| OpenAPI MCP needs current spec file | Keep docs/api_contracts.openapi.json updated |

---

## Expected Speedup Comparison

### Before MCPs
```
Task: "Find all multi-tenant filters"
- Manual grep search: 5 calls to grep_search tool
- File navigation: 10+ read_file calls
- Total: 15+ tool calls
- Time: ~2 minutes

Result: Incomplete, might miss some patterns
```

### After MCPs
```
Task: "Find all multi-tenant filters"
- Grep MCP query: 1 call
- Time: ~20 seconds

Result: Complete pattern index with file locations
```

**Expected speedup: 5-10x for discovery tasks**

---

## Integration with Compound Engineering

MCPs feed the learning pipeline:

```
1. Developer uses GREP MCP
   "Find all multi-tenant filters"
   
2. Results captured in .agent/learnings/workflow_outcomes.json
   
3. Weekly analysis runs
   "Are all multi-tenant filters consistent?"
   
4. Pattern index updated
   "Add variation: tenant_id vs group_id filters"
   
5. Next developer gets improved guidance
   "New pattern added to index with 30+ examples"
```

---

## Troubleshooting

### "MCP Server Not Responding"
1. Check .agent/mcp.json configuration
2. Verify environment variables (SUPABASE_URL, etc.)
3. Restart VS Code
4. Check firewall/VPN

### "Query Returned Too Many Results"
1. Use more specific regex patterns
2. Add file path filter (e.g., `includePattern: "backend/routers/**"`)
3. Break into smaller queries

### "Filesystem MCP Shows Different Structure"
1. Run `git status` to ensure all files are tracked
2. Check `.gitignore` isn't too broad
3. Verify folder exists: `ls -la /d/verified-digital-twin-brains`

### "Postgres Query Failed"
1. Check DATABASE_URL is correct in .agent/mcp.json
2. Verify column names (case-sensitive on Linux)
3. Try simpler query first (e.g., `SELECT 1`)

---

## Next Steps

- [ ] Test each MCP in Cursor/VS Code
- [ ] Add MCP queries to AGENTS.md for specific failure patterns
- [ ] Build workflow templates for common tasks
- [ ] Document MCP discoveries in .agent/learnings/
