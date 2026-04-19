# Case 5: Internal ML Exception Surfacing in Server Mode (iter4, iter6, iter7)

**Source:** `Birkhoff_Finite_Distributive_Lattices.thy`

## What Happens

The server surfaces a raw ML exception instead of a clean proof-method failure:

```
exception THM 0 raised (line 307 of "drule.ML"):
  OF: no unifiers
```

This exception appears across three independent iterations of the same theory.
(Note: oracle JSON also records `ok:false` for the same error — the mismatch is a
framework false positive, but the exception type itself is a genuine robustness issue.)

## Why It Matters

The `OF` combinator in `drule.ML` does not guard against unification failure with
`Exn.capture`, so an internal exception propagates to the user as an ML stack trace
rather than an intelligible Isabelle error message. The theory fails correctly, but
the diagnostic quality is poor.
