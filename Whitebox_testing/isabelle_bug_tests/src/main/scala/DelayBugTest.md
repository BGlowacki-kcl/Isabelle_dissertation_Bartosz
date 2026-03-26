# `DelayBugTest` — Delay.run() rethrows exception, killing the global event timer

## Run

From `isabelle_bug_tests`, run:

```bash
export ISABELLE_HOME=<Your_Isabelle_path>/Isabelle2025
sbt "runMain DelayBugTest"
```

## Bug Summary

`Delay.run()` catches non-interrupt exceptions but then rethrows them. The rethrown exception propagates through `Event_Timer`'s `TimerTask.run()` into `java.util.TimerThread.mainLoop()`. The JDK `Timer` does not catch `RuntimeException` from tasks — the timer thread terminates (source: https://github.com/openjdk/jdk/blob/master/src/java.base/share/classes/java/util/Timer.java).

After that, every `Delay.invoke()` call in the entire process either fails with `IllegalStateException: Timer already cancelled` or silently stops working. This breaks all debouncing and throttling throughout the editor (session-ready delays, file-load delays, syntax highlight delays, etc.).

## Why It Happens

`Event_Timer` is backed by a single global `java.util.Timer` instance (a lazy val singleton). The timer runs a dedicated daemon thread (`event_timer`) that executes all scheduled `TimerTask`s sequentially. When a task's `run()` method throws an unchecked exception, `TimerThread.mainLoop()` does not catch it — the exception propagates out, the `finally` block sets `newTasksMayBeScheduled = false`, and the thread dies. No future tasks can be scheduled.
From event_timer.scala:17:
``` scala
private lazy val event_timer = new Timer("event_timer", true)
```

The call chain is:

1. `Delay.invoke()` schedules a `TimerTask` via `Event_Timer.request()`
2. The timer thread fires the task, calling `Delay.run()`
3. `Delay.run()` executes the user event inside `try { event }`
4. The catch block logs the exception, then rethrows it
5. The rethrow escapes `TimerTask.run()` → kills `TimerThread`

## Affected Code

- File: `Isabelle2025/src/Pure/Concurrent/delay.scala`
- Line: `29`

### Buggy version

```scala
catch { case exn: Throwable if !Exn.is_interrupt(exn) => log(Exn.message(exn)); throw exn }
```

### Fixed version

```scala
catch { case exn: Throwable if !Exn.is_interrupt(exn) => log(Exn.message(exn)) }
```

## Why the Fix Works

Removing `throw exn` means the exception is still logged (so developers can see it), but `Delay.run()` exits normally. The `TimerTask.run()` returns cleanly, and `TimerThread.mainLoop()` continues its loop — ready to fire the next scheduled task. The global event timer stays alive.

## What the Test Checks

1. Creates a `Delay` (d1) whose event throws a `RuntimeException`
2. Invokes d1 and waits for it to fire (150ms, well past the 30ms delay)
3. Creates a second `Delay` (d2) whose event sets a flag
4. Tries to invoke d2 — if the timer died, this throws `IllegalStateException`
5. Waits for d2 to fire

The bug is detected if either:
- `d2.invoke()` threw `IllegalStateException` (timer cancelled) -> likely, or
- d1 fired but d2 never did (timer thread dead, no tasks run)

## Pre-Fix Test Result (bug confirmed)

```text
[info] running (fork) DelayBugTest
[error] Exception in thread "event_timer" java.lang.RuntimeException: deliberate exception in delay event
[error] 	at DelayBugTest$.$anonfun$2(DelayBugTest.scala:13)
[error] 	at DelayBugTest$.$anonfun$adapted$2(DelayBugTest.scala:14)
[error] 	at scala.Function0.apply$mcV$sp(Function0.scala:42)
[error] 	at isabelle.Delay$.first$$anonfun$1(delay.scala:13)
[error] 	at isabelle.Delay$.first$$anonfun$adapted$1(delay.scala:13)
[error] 	at scala.Function0.apply$mcV$sp(Function0.scala:42)
[error] 	at isabelle.Delay.run(delay.scala:28)
[error] 	at isabelle.Delay.invoke$$anonfun$2(delay.scala:41)
[error] 	at isabelle.Delay.invoke$$anonfun$adapted$1(delay.scala:41)
[error] 	at scala.Function0.apply$mcV$sp(Function0.scala:42)
[error] 	at isabelle.Event_Timer$$anon$1.run(event_timer.scala:28)
[error] 	at java.base/java.util.TimerThread.mainLoop(Timer.java:566)
[error] 	at java.base/java.util.TimerThread.run(Timer.java:516)
[info] ============================================================
[info]   DelayBugTest — Delay.run() rethrow kills event timer
[info] ============================================================
[info]   [FAIL] delay_rethrows_exception — bug confirmed
[info] ============================================================
```

## Post-Fix Test Result (bug resolved)

```text
[info] running (fork) DelayBugTest
[info] ============================================================
[info]   DelayBugTest — Delay.run() rethrow kills event timer
[info] ============================================================
[info]   [PASS] delay_rethrows_exception — no bug detected
[info] ============================================================
```

## Rebuild Instructions

After editing `delay.scala`, rebuild the jar with:

```bash
cd /home/bartek1301/workplace/isabelle/Isabelle2025
./bin/isabelle build -b Pure
```

Then re-run the test to verify.
