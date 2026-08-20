# Sprint: T0 Observation Batch — Domain/SSL, npm audit, Brain Maintenance
# Covers: T0-01, T0-04, T0-06, T0-10, T0-12
# Repo: duke-of-beans/home
# Deploy: Railway auto-deploys on push to main

## Context
Greg's observations system (src/observations.ts) already runs periodic checks:
- observeGithubStaleness() — every 4h
- observeBacklogAging() — every 12h
- observeSprintQueueState() — every 2h
- observeClaudeInstructionsValidation() — every 24h
- observeMorningBriefTagging() — every 24h

This sprint adds 5 more T0 observation functions. T0 = no approval needed,
pure monitoring that writes to greg_thoughts as alerts or observations.

## Task

### 1. T0-01: Vercel Deployment Health
Every 30 min, check all Vercel projects for deploy status.
Use Vercel API: GET https://api.vercel.com/v6/deployments?limit=1&projectId={id}
Auth: Bearer token from env VERCEL_TOKEN (already on Railway? check, if not, 
the token is in Oktyv vault: apis/vercel)

Portfolio Vercel projects (check these project IDs via Vercel API list_projects):
Key ones: ASURIQ, Capitol Gains, Clear Sky, Consonance, silentampersand.com,
davidkirsch.me, Greg Home dashboard, COVOS, GAD fleet sites.

For each: check latest deployment status. If any are 'ERROR' or 'BUILDING' for
>15 min, write alert to greg_thoughts with tags ['alert', 'deploy-health', 'needs-eye'].

### 2. T0-04: Domain + SSL Expiry
Every 24h, check domain expiry for all portfolio domains.
Domains: asuriq.dev, capitolgains.app, consonance.chat, silentampersand.com,
davidkirsch.me, covos.app, clearskytravel.co, throwbak.com, tessryx.dev,
easter.agency, forme.pub

For each domain, use the Vercel API domain check or a DNS lookup.
SSL expiry: use Node's tls.connect() to get certificate expiry date.
Alert if any domain expires within 30 days or SSL within 14 days.

### 3. T0-06: npm Audit Vulnerability Scans
Every 24h, for repos that have package.json, run a lightweight check.
Since we can't run npm audit from Railway, use the GitHub API to check
for Dependabot alerts:
GET https://api.github.com/repos/duke-of-beans/{repo}/dependabot/alerts?state=open
Auth: Bearer {GITHUB_PAT}

Check top 10 repos. If any have critical/high severity alerts, write to
greg_thoughts with tags ['alert', 'security', 'needs-eye', $repo].

### 4. T0-10: Brain.db Maintenance
Every 24h, check brain.db health via CORTEX:
- POST /mcp with method: "tools/call", name: "federation_health"
  Check all 8 adapters are reachable
- Count observations via recall query "recent observations count"
- If any adapter is down, alert with tags ['alert', 'brain-health']

Also: identify observations older than 90 days with quality < 0.5 —
these are candidates for pruning. Don't prune automatically (T0 = observe only),
but note them in a greg_thought with tags ['brain-maintenance'].

### 5. T0-12: C:/ Drive Storage Monitoring
Every 6h, check if G7's C: drive is getting full.
This can't be done directly from Railway. Instead, check if the existing
D:\Tools\c-drive-management\ health check has run recently by looking for
a brain.db observation about disk space.

Alternative: create a simple health endpoint on G7 (via Desktop Commander
or a local script) that Railway can poll. For now, just check brain.db
for the most recent disk observation and alert if it's stale (>24h old).

## Pattern
Each observation function follows this pattern:
```typescript
async function observeXxx(): Promise<void> {
  try {
    // ... check logic ...
    const result = { /* findings */ };
    
    if (needsAlert) {
      await supabase.from('greg_thoughts').insert({
        content: `Alert: ${summary}`,
        kind: 'alert',
        ring: 3,
        tags: ['alert', category, 'needs-eye'],
        metadata: { source: 'observation', type: 'xxx', ...details }
      });
    }
  } catch (err) {
    console.error('[observe-xxx]', err);
  }
}
```

Register each in the observation scheduler (likely a setInterval map in observations.ts).

## Constraints
- TypeScript on Railway
- All observations write to greg_thoughts (Consonance Supabase)
- T0 tier = no side effects beyond writing observations
- Don't break existing observation functions
- Commit to duke-of-beans/home main branch
