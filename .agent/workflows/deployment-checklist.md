---
description: Pre-commit checklist for Vercel/Render deployments
---

# Deployment Pre-Commit Checklist

**ALWAYS run these checks before pushing code that will trigger a deployment build.**

## Lesson: Common Deployment Failures

These issues work locally on Windows but fail on Linux CI/CD:

1. **`.gitignore` patterns are too broad** - `lib/` ignores ALL lib folders including `frontend/lib/`
2. **Missing imports** - `useCallback`, `useEffect` etc. used but not imported
3. **Case sensitivity** - `TwinContext.tsx` vs `twincontext.tsx` (Linux is case-sensitive)
4. **Files not tracked by Git** - Check `git status` and `git ls-files`

---

## Pre-Commit Checklist

### 1. Verify All Files Are Tracked
```powershell
# Check if critical directories are in git
git ls-files frontend/lib
git ls-files frontend/contexts
git ls-files frontend/components
```

If empty, check `.gitignore` for overly broad patterns like `lib/` or `build/`.

### 2. Run Local Build (REQUIRED)
```powershell
cd frontend
Remove-Item -Recurse -Force .next -ErrorAction SilentlyContinue
npm run build
```

**Exit code must be 0.** If build fails, fix ALL errors before committing.

### 3. Check for Missing Imports
```powershell
# Find files using useCallback without importing it
Select-String -Path "frontend/**/*.tsx" -Pattern "useCallback" | 
  ForEach-Object { 
    $file = $_.Path
    if (-not (Select-String -Path $file -Pattern "import.*useCallback" -Quiet)) {
      Write-Host "Missing useCallback import: $file"
    }
  }
```

### 4. Verify tsconfig.json is Valid JSON
```powershell
cd frontend
npx tsc --showConfig > $null 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host "tsconfig.json is invalid!" }
```

### 5. Check Path Alias Configuration
Ensure `frontend/tsconfig.json` has:
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./*"]
    }
  }
}
```

---

## Common Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `Module not found: @/lib/...` | Files not in Git | Fix `.gitignore`, then `git add -f frontend/lib/` |
| `Cannot find name 'useCallback'` | Missing import | Add to React import line |
| `tsconfig.json` parse error | Invalid JSON | Check for unclosed brackets, trailing commas |
| Works locally, fails on Vercel | Case mismatch | Use `git mv` to fix folder/file casing |

---

## After Pushing

1. Monitor Vercel build logs for the first 2 minutes
2. If build fails, read the ENTIRE error message before fixing
3. Fix ALL reported errors in one commit, not one at a time
