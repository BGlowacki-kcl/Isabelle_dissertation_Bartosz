# Isabelle Contradiction Finder

Automated tool that uses AI to search for genuine soundness violations in Isabelle/HOL — a real proof of `False` without `sorry` or `oops`.

## How It Works

Three Mistral AI agents collaborate in a loop:

| Agent | Role |
|---|---|
| **Strategist** | Proposes attack strategies based on feedback. Maintains full conversation history. |
| **Coder** | Translates each strategy into valid Isabelle theory code. Maintains full conversation history. |
| **Vision** | One-shot screen reader — takes a screenshot and reports errors, proof status, and prover state. No history. |

## Loop

1. Strategist proposes a strategy
2. Coder writes the Isabelle theory
3. Code is typed into Isabelle/jEdit via GUI automation
4. Vision polls the screen until Isabelle finishes processing
5. Vision describes the result → Strategist evaluates it
6. If contradiction found (and no cheats) → done. Otherwise, repeat with a new strategy.

## Rules

- `sorry` and `oops` are forbidden — they bypass the kernel and don't count as proofs
- Each iteration must try a **different** strategy
- A result only counts if Isabelle accepts it with **no errors**

## Files

```
config.py   — constants, Mistral client, system prompts
ai_chats.py — Strategist, Coder, and Vision chat functions
gui.py      — Isabelle/jEdit GUI automation
main.py     — main loop
```
