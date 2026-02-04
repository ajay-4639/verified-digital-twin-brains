## 📋 What Changed

Brief description of what this PR does.

- Key change 1
- Key change 2
- Key change 3

**Type of change:**
- [ ] 🐛 Bug fix (fixes #___)
- [ ] ✨ New feature (closes #___)
- [ ] 📚 Documentation update
- [ ] ♻️ Refactor (no functional change)
- [ ] ⚡ Performance improvement
- [ ] 🔒 Security fix
- [ ] 🗄️ Database migration

## 🧪 How to Test

**Local Verification:**
1. Step 1
2. Step 2
3. Step 3

**CI Verification:**
- ✅ GitHub Actions will run automatically on PR
- ✅ Check that all checks pass

**Manual Testing (if needed):**
- User flow 1
- User flow 2
- Edge case 1

## ⚠️ Risk Assessment

**Risk Level:** 🟢 Low / 🟡 Medium / 🔴 High

**Why?** _Explain your risk assessment_

**Potential Issues & Mitigations:**
- Issue 1 and how it's mitigated
- Issue 2 and how it's mitigated

**Testing Coverage:**
- [ ] Unit tests added
- [ ] Integration tests added
- [ ] Manual testing completed

## 🔄 Rollback Plan

**If this needs to be rolled back:**
1. Step 1 to rollback
2. Step 2 to rollback
3. Expected recovery time: ___ minutes

**Alternative:** `git revert <commit>`

## 📸 Screenshots or Logs

_Include screenshots for UI changes or relevant logs._

## 📊 Checklist - REQUIRED BEFORE MERGE

**Code Quality:**
- [ ] Ran `./scripts/preflight.ps1` locally (exit code 0)
- [ ] All tests pass (locally and in CI)
- [ ] No console.log or debug code left
- [ ] Follows `.cursorrules` conventions

**Security & Multi-Tenancy:**
- [ ] All DB queries filter by `tenant_id` or `twin_id`
- [ ] All routes use `Depends(get_current_user)` where needed
- [ ] Resource access verified with `verify_owner()`
- [ ] No hardcoded secrets or API keys
- [ ] No PII logged or exposed

**Testing & Compatibility:**
- [ ] New code has test coverage
- [ ] No breaking changes (or clearly documented)
- [ ] Database migrations are reversible (if applicable)

**Documentation:**
- [ ] README updated (if needed)
- [ ] Code comments added for complex logic
- [ ] PR description complete

## 🔗 Related

- Fixes issue: #___ or N/A
- Related PR: #___ or N/A
- Blocked by: #___ or N/A

## 📚 Reference

| Topic | Link |
|-------|------|
| Review Guidelines | `docs/CODE_REVIEW_GUIDELINES.md` |
| Best Practices | `docs/CODE_REVIEW_BEST_PRACTICES.md` |
| Quick Ref | `docs/CODE_REVIEW_QUICK_REFERENCE.md` |
| Coding Std | `.cursorrules` |
| Operating Manual | `docs/ai/agent-manual.md` |

---

**Questions?** See the reference docs or ask in #code-review

