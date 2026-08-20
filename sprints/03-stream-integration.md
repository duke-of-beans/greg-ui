# Sprint: Home Backend — Stream Integration + Communication Pipeline
# Covers: STREAM-02 through STREAM-05, STREAM-07
# Repo: duke-of-beans/home (Greg's Railway service)
# Deploy: Railway auto-deploys on push to main

## Context
Greg (Home) runs on Railway at cortex-production-d0d7.up.railway.app.
The codebase is TypeScript, runs 24/7, handles DMN thinking, sprint execution,
observations, and communication.

greg_thoughts table in Supabase (Consonance, project zdmxqzkqutizehynqojk) is
the canonical stream. It has 194+ rows with kinds: dmn_thought, note, journal,
morning_brief, workspace_note. Tags are in a text array column.

STREAM-01 (DMN thinking → greg_thoughts) and STREAM-06 (auto-tagging) are done.
STREAM-08 (workspace notes) is done.

## Task

### 1. STREAM-02: Messages to David → greg_thoughts
In src/comms.ts (or wherever messageForDavid() lives):
After composing a message for David, write it to greg_thoughts:
```sql
INSERT INTO greg_thoughts (content, kind, ring, tags, metadata)
VALUES ($content, 'message', 3, ARRAY['for-david'], $metadata)
```
metadata should include: { recipient: 'david', channel: 'stream', priority: 'normal' }
Tag with 'for-david' so the DASH-01 filter picks it up.

### 2. STREAM-03: Journal entries → greg_thoughts
Greg's journal entries (written by journal.ts) should also go to greg_thoughts
with kind='journal', ring=3, tags=['journal']. Morning briefs already do this
(kind='morning_brief'). Verify regular journal entries do too.
If not, add the write in the journal entry creation path.

### 3. STREAM-04: Monitoring alerts → greg_thoughts
In src/observations.ts, when an observation detects something notable
(e.g., deployment down, security advisory, stale repo), write an alert:
```sql
INSERT INTO greg_thoughts (content, kind, ring, tags, metadata)
VALUES ($summary, 'alert', 3, ARRAY['alert', $category, 'needs-eye'], $metadata)
```
Categories: 'deploy-health', 'security', 'staleness', 'budget'
metadata: { source: 'observation', observation_type: $type, severity: 'info'|'warning'|'critical' }

### 4. STREAM-05: Sprint execution results → greg_thoughts
In src/index.ts executeSprint(), after a sprint completes (success or failure),
write the result to greg_thoughts:
```sql
INSERT INTO greg_thoughts (content, kind, ring, tags, metadata)
VALUES ($summary, 'sprint_result', 3, ARRAY['sprint', $project, $status], $metadata)
```
metadata: { sprint_id, project, status: 'completed'|'failed'|'aborted', 
  commit_sha (if any), duration_ms, model_used }

For failures, add tag 'needs-eye' so it surfaces in the dashboard.

### 5. STREAM-07: POSTCOG ring evaluation on stream writes
Before writing any stream entry, evaluate the content's ring level.
If the content contains sensitive information (ring 0-1 keywords: passwords,
API keys, personal data patterns), set ring=4 (internal only) instead of ring=3.

Simple keyword scan is fine for v1:
```typescript
function evaluateRing(content: string): number {
  const sensitivePatterns = [
    /api[_-]?key/i, /password/i, /secret/i, /token/i,
    /bearer\s+\w{20,}/i, /sk-[a-zA-Z0-9]{20,}/
  ];
  return sensitivePatterns.some(p => p.test(content)) ? 4 : 3;
}
```

## Supabase Connection
Project: zdmxqzkqutizehynqojk (Consonance)
The service already has SUPABASE_URL and SUPABASE_KEY env vars on Railway.
greg_thoughts table schema: id (uuid), content (text), kind (text), ring (int),
tags (text[]), metadata (jsonb), created_at (timestamptz), updated_at (timestamptz).

## Constraints
- TypeScript, runs on Railway
- Don't break existing DMN thinking, sprint execution, or observation flows
- All writes go to greg_thoughts (NOT stream_entries — that table is unused)
- Test by checking Supabase table after push
- Commit to duke-of-beans/home main branch
