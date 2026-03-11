# Progress Bug Investigation Notes

## Affected Code

- File: `Isabelle2025/src/Pure/System/progress.scala`
- Lines: `86–89`

### Initial implementation

```scala
def stopped: Boolean = {
   if (Thread.currentThread().isInterrupted()) is_stopped = true
   is_stopped
}
```

## Initial Test Result

The `ProgressBugSimple` test reproduced the issue quickly:

```text
[info] ============================================================
[info]   ProgressBugSimple — up to 10000 iterations each
[info] ============================================================
[info] --- TEST A: watchdog sets stopped ---
[info]   [TEST A] iter 100 / 10000 — no bug yet
[info]   ✗  TEST A bug triggered at iteration 117
[info] --- TEST B: Future.cancel leaks interrupt ---
[info]   ✗  TEST B bug triggered at iteration 1
[info] ============================================================
[info]   Result: ✗  BUG(S) CONFIRMED
[info] ============================================================
```

## Incorrect Intermediate Change

An attempted rebuild used `is_interrupt()` instead of `isInterrupted()`, which failed to compile:

```text
### Building Isabelle/Scala (/home/bartek1301/workplace/isabelle/Isabelle2025/lib/classes/isabelle.jar) ...
value is_interrupt is not a member of Thread - did you mean Thread.interrupt?
1 error found
-- [E008] Not Found Error: /home/bartek1301/workplace/isabelle/Isabelle2025/src/Pure/System/progress.scala:87:31
87 |    if (Thread.currentThread().is_interrupt()) is_stopped = true
   |        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   |value is_interrupt is not a member of Thread - did you mean Thread.interrupt?
1 error found
*** Failed to compile Scala sources
```

## Rebuild Status

After correcting the method name, the `Pure` component built successfully:

```text
### Building Isabelle/Scala (/home/bartek1301/workplace/isabelle/Isabelle2025/lib/classes/isabelle.jar) ...
### Building Demo (/home/bartek1301/workplace/isabelle/Isabelle2025/src/Tools/Demo/lib/demo.jar) ...
0:00:46 elapsed time
```

## Intermediate Fix Attempt

```scala
def stopped: Boolean = {
   if (Thread.currentThread().isInterrupted()) is_stopped = true
   is_stopped
}
```

This improved `TEST A`, but did not eliminate the failures. A later run still reproduced both bugs:

```text
[info] running (fork) ProgressBugSimple
[info] ============================================================
[info]   ProgressBugSimple — up to 10000 iterations each
[info] ============================================================
[info] --- TEST A: watchdog sets stopped ---
[info]   [TEST A] iter 100 / 10000 — no bug yet
[info]   [TEST A] iter 200 / 10000 — no bug yet
[info]   [TEST A] iter 300 / 10000 — no bug yet
[info]   [TEST A] iter 400 / 10000 — no bug yet
[info]   ✗  TEST A bug triggered at iteration 447
[info] --- TEST B: Future.cancel leaks interrupt ---
[info]   ✗  TEST B bug triggered at iteration 1
[info] ============================================================
[info]   Result: ✗  BUG(S) CONFIRMED
[info] ============================================================
```

## Latest Test Result

After a fresh rebuild and rerun, `TEST A` no longer reproduced within 10,000 iterations, but `TEST B` still failed immediately:

```text
[info] ============================================================
[info]   ProgressBugSimple — up to 10000 iterations each
[info] ============================================================
[info] --- TEST A: watchdog sets stopped ---
[info]   ...
[info]   [TEST A] iter 10000 / 10000 — no bug yet
[info]   ○  TEST A: no bug in 10000 iterations
[info] --- TEST B: Future.cancel leaks interrupt ---
[info]   ✗  TEST B bug triggered at iteration 1
[info] ============================================================
[info]   Result: ✗  BUG(S) CONFIRMED
[info] ============================================================
```

## Current Proposed Fix

```scala
def stopped: Boolean = is_stopped || Thread.currentThread().isInterrupted()
```

