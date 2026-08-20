# Sprint: T1 Auto-Execute Batch — Tests, Branch Cleanup, TypeGen, HIBP
# Covers: T1-01, T1-04, T1-05, T1-10, T1-14
# Repo: duke-of-beans/home
# Deploy: Railway auto-deploys on push to main

## Context
T1 actions auto-execute and notify David. They must be REVERSIBLE.
POSTCOG R-score > 0.8 required (but POSTCOG integration is T-07, not yet wired —
for now, apply conservative safety checks inline).

## Task

### 1. T1-01: Yuma Test Suite Runs
Every 6h, for KERNL-registered projects that have test specs, trigger test runs.
This runs from Railway, so it can't use KERNL directly. Instead:
- Use GitHub API to check if repos have test configs (package.json scripts.test)
- For repos with GitHub Actions test workflows, check latest run status
- For repos without CI tests, note them as untested

Write results to greg_thoughts:
```
kind: 'observation', tags: ['testing', 'yuma', $project]
```

### 2. T1-04: Stale Git Branch Cleanup
Every 24h, scan repos for branches that:
- Are merged into main
- Are older than 30 days
- Are not 'main', 'dev', or 'staging'

Use GitHub API:
GET /repos/duke-of-beans/{repo}/branches
For each branch, check if merged:
GET /repos/duke-of-beans/{repo}/compare/main...{branch}
If status='identical' or behind_by=0, it's merged.

DELETE /repos/duke-of-beans/{repo}/git/refs/heads/{branch}

This is reversible (branches can be restored from the SHA).
Write to greg_thoughts with tags ['maintenance', 'git-cleanup', $repo].
List deleted branches in the content.

### 3. T1-05: TypeScript Type Regeneration from Supabase
Every 24h, regenerate TypeScript types for Supabase projects.
Use Supabase MCP or API:
- Project zdmxqzkqutizehynqojk (Consonance)
- Any other Supabase projects in the portfolio

Call: POST generate_typescript_types with project_id
Compare output with existing types file in the repo.
If different, create a commit on a branch 'chore/update-supabase-types'
and note it in greg_thoughts with tags ['maintenance', 'types', $project].

Don't auto-merge — David reviews type changes.

### 4. T1-10: Supabase Security + Performance Advisors
Every 12h, run Supabase advisors on all projects:
GET advisors with type='security' and type='performance'

Projects to check:
- zdmxqzkqutizehynqojk (Consonance)
- Any others (check via list_projects)

If any advisors return findings, write to greg_thoughts:
```
kind: 'alert', tags: ['security', 'supabase', $project, 'needs-eye']
```
Include the remediation URL so David can click through.

### 5. T1-14: HIBP Breach Checking on Vault Credentials
Every 24h, check Oktyv vault credentials against Have I Been Pwned.
Use k-anonymity API (no full passwords sent):

For each credential in the vault:
1. SHA-1 hash the value
2. Send first 5 chars to: GET https://api.pwnedpasswords.com/range/{prefix}
3. Check if the remaining hash suffix appears in results

This can't run from Railway directly (no Oktyv vault access from Railway).
Instead, create a new observation endpoint in Home that CORTEX can trigger,
or schedule it as a sprint that runs on Desktop.

For now: write a placeholder that notes "HIBP check requires vault access —
schedule as Desktop sprint" in greg_thoughts with tags ['security', 'hibp', 'blocked'].

## Constraints
- TypeScript on Railway
- All actions must be reversible
- GitHub API auth: GITHUB_PAT env var on Railway
- Supabase: SUPABASE_URL + SUPABASE_KEY env vars on Railway
- Don't delete 'main', 'dev', or 'staging' branches ever
- Write results to greg_thoughts (Consonance Supabase)
- Commit to duke-of-beans/home main branch
