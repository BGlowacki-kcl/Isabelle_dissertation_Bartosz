# Case 2: Server Session State Contamination (iter66–iter71)

**Source:** `Risk_Free_Lending.thy` — six consecutive mutations of the same theory

## What Happens

The server reports **line 118** for all six iterations regardless of where the actual error is.
The oracle correctly tracks the error to different positions across mutations.

| Iteration | Oracle errors | Server errors |
|-----------|---------------|---------------|
| File 1    | [42]          | [118]         |
| File 2    | [177]         | [118]         |
| File 3    | [2265]        | [118]         |

## Why It Matters

The server carries stale proof state from the iter66 session. The `use_theories` call
reuses a live session without fully invalidating the cached failure region. Users are
misled into investigating line 118 while the real error is elsewhere in the file.
