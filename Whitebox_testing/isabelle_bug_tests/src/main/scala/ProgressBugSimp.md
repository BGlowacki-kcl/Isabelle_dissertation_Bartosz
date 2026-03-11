# `ProgressBugSimple` Test Notes

This test file documents two interrupt-related failure modes in Isabelle's progress handling.

## Run

From `Isabelle2025/src/Tools/jEdit/src/isabelle_bug_tests`, run:

```bash
sbt "runMain ProgressBugSimple"
```

## Test A — `progress.bash()` watchdog corrupts `stopped`

`progress.bash()` starts a watchdog thread that may call `thread.interrupt()` on the worker once `watchdog_time` expires. If `Progress.stopped()` consumes that interrupt flag, it can permanently set `is_stopped = true` even though `stop()` was never called.

### What this test checks

- the bash command itself finishes quickly,
- the watchdog timeout is intentionally very short,
- the worker thread is interrupted mid-execution,
- `Progress.stopped()` must not convert that interrupt into a persistent stopped state unless `stop()` was explicitly requested.

## Test B — `Future.cancel()` leaks interrupts into `Progress`

`Future.fork` runs repeated `Progress().stopped` checks on worker threads. `Future.cancel()` interrupts those threads via `thread.interrupt()`. If `Progress.stopped()` consumes that interrupt and stores it as `is_stopped = true`, every later `Progress` instance created on the same interrupted thread becomes corrupted.

### What this test checks

- worker threads are cancelled through thread interruption,
- interruption alone must not mark a new `Progress` instance as permanently stopped,
- `Progress.stopped()` should reflect explicit stop state, not leaked thread-interrupt state.

## Summary

Together, these tests verify that thread interrupts from watchdogs or cancelled futures do not silently mutate `Progress` state in ways that survive beyond the original event.



