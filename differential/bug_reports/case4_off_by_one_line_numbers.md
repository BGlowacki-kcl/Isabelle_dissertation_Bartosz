# Case 4: Consistent Off-by-One Line Number Discrepancy

## What Happens

Both tools identify the same failing command, but report different line numbers — always
off by exactly 1.

```
file 2:  Oracle: [79]   Server: [78]
File 1 and 3:          Oracle: [87]   Server: [86]
```

Around the discrepancy in File 2:
```
78:  unfolding is_bound_def by sorry
79:  obtain x y where "p = (x, y)" by (cases p)   ← oracle says here
```
The server attributes the `obtain` failure to line 78 instead of 79.

## Why It Matters

Server and batch mode have a systematic 1-line offset in how they attribute commands to
source positions — likely a difference in whether the line counter advances before or
after processing the newline. Jump-to-error and inline markers would highlight the wrong line.
