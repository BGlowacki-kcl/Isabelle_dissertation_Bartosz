# PIDE Bug Report: Error Misattribution on `by sorry`

---

## Summary

When `by simp` is replaced with `by sorry` inside a `proof - ... qed` block, the PIDE
server (`use_theories`) and `isabelle build` (the "oracle") report **different errors at
different lines**:

| Tool | Error line | Error message |
|------|-----------|---------------|
| `isabelle build` (oracle) | **line 25** | `Bad context for command "qed"` |
| PIDE server (`use_theories`) | **line 24** | `Outer syntax error: keyword "(" expected, but end-of-input was found` |

Both tools detect *something* wrong, but they disagree on what and where. The oracle
gives the semantically correct diagnosis; PIDE gives a misleading syntax error pointing
to the wrong line.

---

## How It Was Found

A differential fuzzing framework was built that:

1. Takes a real Isabelle theory file (`Rankings.thy` from the AFP)
2. Applies random mutations (swap tactic, flip operator, duplicate line, etc.)
3. Checks the mutated theory using both `isabelle build` and the PIDE server via `use_theories`
4. Flags cases where the two tools **disagree on which lines have errors**

On the very first run, the mutation `by simp → by sorry` at line 24 was flagged as a
mismatch in 10 out of 10 occurrences. No other mutation type produced a consistent
divergence.

---

## Minimal Reproducer

The following theory reproduces the bug. The key is `by sorry` inside a `proof - ... qed`
block where the proof goal has already been discharged by a `calc` chain:

```isabelle
theory Test
  imports Main
begin

lemma map_index_self:
  assumes "distinct xs"
  shows   "map (index xs) xs = [0..<length xs]"
proof -
  have "xs = map (\<lambda>i. xs ! i) [0..<length xs]"
    by (simp add: map_nth)
  also have "map (index xs) \<dots> = map id [0..<length xs]"
    by (intro map_cong) simp_all
  finally show ?thesis
    by sorry    (* line 16 — triggers the bug *)
qed            (* line 17 *)

end
```

This approach is in the show_sorry_bug.py file, which main task is to uncover
this one issue. Below there are logs gathered after one run of this code.

```wsl
Writing theory to: /home/bartek1301/workplace/isabelle/git/differential/BugDemo.thy
Cleaning up leftover processes...
  [cleanup] Killed 7 leftover polyml process(es).
Starting Isabelle server (this takes ~30 s)...
Found Server: 127.0.0.1:33253
Server ready at 127.0.0.1:33253

Starting HOL session (this takes ~90-120 s on first run)...

Run #1 — running oracle and PIDE server (parallel)...
  [PIDE] Connecting to 127.0.0.1:33253...
  [PIDE] Sending session_start (HOL)...
  [PIDE] session_start response: FINISHED {"session_id":"61225dbd-ae58-4faa-bd2c-66bb2d7bbb18","tmp_dir":"/tmp/isabelle-bartek1301/server_session17903485
  [PIDE] Session ID: 61225dbd-ae58-4faa-bd2c-66bb2d7bbb18
  [PIDE] Sending: use_theories {"session_id": "61225dbd-ae58-4faa-bd2c-66bb2d7bbb18", "theories": ["BugDemo"], "master_dir": "/home/bartek1301/workplace/isabelle/git/differential"}
  [PIDE] use_theories response: FINISHED (410860 chars)

  [Saved] Oracle output → /home/bartek1301/workplace/isabelle/git/differential/show_bug_oracle_1.txt
  [Saved] PIDE output   → /home/bartek1301/workplace/isabelle/git/differential/show_bug_pide_1.txt

============================================================
  ORACLE  (isabelle build)
============================================================
  ShowBugOracle FAILED (see also "isabelle build_log -H Error ShowBugOracle")
  *** Bad context for command "qed" (line 19 of "~/workplace/isabelle/git/differential/.show_bug_oracle/BugDemo.thy")
  *** At command "qed" (line 19 of "~/workplace/isabelle/git/differential/.show_bug_oracle/BugDemo.thy")
  Finished at Thu Mar 26 11:56:34 GMT 2026

============================================================
  PIDE SERVER  (use_theories)
============================================================
  line 16: Failed to apply initial proof method\<^here>:
  line 18: Outer syntax error\<^here>: keyword "(" expected,

============================================================
  VERDICT
============================================================
  Oracle error lines : [19]
  PIDE error lines   : [16, 18]

  *** BUG REPRODUCED ***
  Both tools detect an error, but report DIFFERENT lines.
  Oracle sees 'Bad context for qed'; PIDE sees a syntax error one line earlier.
```

---

## Actual Logs

### Oracle (`isabelle build`) output

```
OracleSession_0: theory OracleSession_0.Test_0
OracleSession_0 FAILED (see also "isabelle build_log -H Error OracleSession_0")
*** Bad context for command "qed" (line 25 of ".../Test_0.thy")
*** At command "qed" (line 25 of ".../Test_0.thy")
Unfinished session(s): OracleSession_0
```

### PIDE server (`use_theories`) response

```json
{
  "ok": false,
  "errors": [
    {
      "kind": "error",
      "message": "Outer syntax error: keyword \"(\" expected, but end-of-input was found",
      "pos": {
        "line": 24,
        "offset": 658,
        "end_offset": 660,
        "file": ".../Test_0.thy"
      }
    }
  ]
}
```

### Framework comparison output

```
[FAIL] Server missed oracle errors.
Oracle-only errors: [25]
Server-only extras: [24]

Oracle error lines extracted: [25]
Server error lines extracted: [24]

Server errors (line -> message snippet):
  line 24: Outer syntax error: keyword "(" expected, but end-of-input was found
```

---

## Why This Is a Bug

A user relying on the IDE error marker would look at `by sorry` and see a confusing
syntax error, rather than understanding that `qed` has no goal to close.

---

## Mutation Applied

The fuzzer applied a single substitution to the original `Rankings.thy` (AFP):

```
- Replaced 'by simp' → 'by sorry'
```