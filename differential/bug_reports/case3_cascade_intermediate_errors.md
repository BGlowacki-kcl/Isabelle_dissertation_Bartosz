# Case 3: Server Reports Cascade of Intermediate Errors

**Source:** `Median_Of_Medians_Selection.thy`

## What Happens

A single mutation (duplicated `by (auto ...)` at lines 547–548) causes one root failure.
The oracle reports only the terminal failure site. The server reports errors at every
intermediate proof step affected by the breakage.

```
File 1:  Oracle: [23, 45, 551]           Server: [23, 45, 426, 445, 454, 461, 547]
File 2:  Oracle: [23, 45, 888]           Server: [23, 45, 426, 445, 454, 461, 887]
```

## Why It Matters

In jEdit/VSCode a user sees errors highlighted at lines 426, 445, 454, 461 with no
clear indication that the root cause is the duplicated `by` tactic further down.
One mutation produces a flood of markers that look like many independent failures.
