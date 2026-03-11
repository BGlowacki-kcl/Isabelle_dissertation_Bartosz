# Differential Testing Overview

This directory contains a lightweight differential testing harness for Isabelle. Its purpose is to compare the result returned by the Isabelle server with the result returned by a direct oracle run and flag any disagreement as a potential bug.

## How it works

For each worker, the harness repeatedly performs the following loop:

1. Load a fresh `.thy` input file from `input/`.
2. Rename its theory header to a worker-specific theory such as `Test_0`.
3. Apply a sequence of random mutations while preserving the outer `theory ... begin` / `end` structure.
4. Run the mutated theory through the Isabelle server.
5. Run the same theory through the oracle using `isabelle process`.
6. Compare both outcomes and save either a mismatch report or a match log.

The main entry point is `start.py`, which starts the Isabelle server and launches multiple parallel workers.

## Main components

- `start.py` — orchestrates the campaign, starts the server, creates sessions, and runs workers in parallel.
- `mutator.py` — loads input theories, rewrites theory names per worker, applies random mutations, and records mutation logs.
- `server.py` — starts a fresh Isabelle server and reads protocol responses until `OK` or `FINISHED`.
- `oracle.py` — runs `isabelle process -e 'use_thy "..."'` as the ground-truth oracle.
- `comparator.py` — extracts error lines from both sides and decides whether the results match.
- `reporter.py` — writes bug reports for mismatches and summary logs for matches.
- `const.py` — stores the main configuration, including worker count, timeout, session name, and output directories.

## What counts as a bug

A run is treated as suspicious when the server and oracle disagree. This includes cases where:

- the server reports an error but the oracle succeeds,
- the oracle reports an error but the server succeeds,
- both fail, but the detected error lines differ,
- the server returns invalid or unparseable JSON.

If both sides succeed, or both fail on the same theory lines, the result is treated as a match.

## Inputs and outputs

### Inputs

- Seed theories are stored in `input/`.
- Per-worker temporary theories are written as files such as `Test_0.thy`, `Test_1.thy`, and so on.
- Mutation histories are saved in `mutations_*.txt`.

### Outputs

- `bug_reports/` contains mismatch reports, including:
	- the failing theory,
	- comparison details,
	- oracle and server logs,
	- the mutation history that produced the case.
- `no_bug/` contains logs for runs where both sides agreed.
- `oracle_output_*.txt` and `server_output_*.txt` store raw outputs for debugging.

## Default configuration

The current defaults in `const.py` are:

- session: `HOL`
- workers: `4`
- mutations per loaded theory: `10`
- oracle timeout: `500` seconds

## Practical goal

The harness is designed to find semantic or reporting inconsistencies between Isabelle server execution and direct theory processing. In short, it checks whether both execution paths agree on whether a mutated theory should pass or fail, and where the failure occurs.
