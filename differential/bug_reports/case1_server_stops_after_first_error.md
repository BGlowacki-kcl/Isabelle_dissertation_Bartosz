# Case 1: Server Stops After First Error

**Source:** `Randomised_Social_Choice` / Rankings theory

## What Happens

Both tools find an error at line 354 (`No calculation yet` — `ultimately` tactic fails).
The oracle continues and also detects a second independent failure at line 537.
The server stops after line 354 and never reports 537.

```
Oracle errors: [354, 537]
Server errors: [354]
```

## Why It Matters

A user relying on the server sees only the first error. After fixing it, they discover
a second unrelated failure that was always present. This is especially problematic in
large theories where multiple independent proofs can fail simultaneously.
