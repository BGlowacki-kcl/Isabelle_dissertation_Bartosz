# Case 6: Oracle and Server Report Errors at Very Different Positions (iter10, iter80)

## What Happens

Both tools detect a failure, but report significantly different line numbers.

```
Oracle: [455]    Server: [431]    (off by 24)
```

For GenClock.thy, the theory has nested `qed` blocks:
```
431:  qed    ← server reports here (innermost failing qed)
...
455: qed     ← oracle reports here (outermost enclosing qed)
```

## Why It Matters

The two tools use different error attribution strategies: the server pinpoints the
innermost failure site, while the oracle propagates to the outermost enclosing block.
For iter10 the off-by-2 has no clear structural explanation and may indicate a
position-tracking inconsistency for multi-line commands.
