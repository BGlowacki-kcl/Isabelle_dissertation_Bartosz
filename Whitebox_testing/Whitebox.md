# Whitebox Testing Guide

## Setup

1. Download the official `Isabelle2025` distribution.
2. Add `Isabelle2025/bin` to your system `PATH`.

## Running the Test Suite

1. Go to `Whitebox_testing/isabelle_bug_tests`.
2. Run `sbt "runMain ProgressBugSimple"`.

## Testing Local Isabelle Changes

1. Modify the relevant Isabelle source file, for example `Isabelle2025/src/Pure/System/progress.scala`.
2. Rebuild the affected artifacts with `isabelle build -b Pure`.
3. Re-run the test suite using `sbt "runMain ProgressBugSimple"`.
