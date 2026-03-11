# Whitebox Testing Guide

## Setup

1. Download the official `Isabelle2025` distribution.
2. Add `Isabelle2025/bin` to your system `PATH`.
3. Place the testing folder inside `Isabelle2025/src/Tools/jEdit/src/`.
4. From the `Isabelle2025` directory, run `isabelle build .`.

## Running the Test Suite

1. Change into `Isabelle2025/src/Tools/jEdit/src/isabelle_bug_tests`.
2. Run `sbt "runMain ProgressBugSimple"`.

## Testing Local Isabelle Changes

1. Modify the relevant Isabelle source file, for example `Isabelle2025/src/Pure/System/progress.scala`.
2. Rebuild the affected artifacts with `isabelle build -b Pure`.
3. Re-run the test suite using `sbt "runMain ProgressBugSimple"`.