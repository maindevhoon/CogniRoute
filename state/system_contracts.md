# System Contracts

## Runtime Constraints

- Sequential orchestration only
- One frontend worker task per `/generate` call
- Workers receive scoped task context only
- Plan state is stored in `state/implementation_plan.md`
- Verification is a single checkpoint, not a replanning loop

## Frontend Artifact Contract

The frontend worker must return exactly one artifact with a filename and content.

```json
{
  "artifact": {
    "content": "string",
    "filename": "string"
  },
  "status": "completed|failed",
  "task_id": "string"
}
```
