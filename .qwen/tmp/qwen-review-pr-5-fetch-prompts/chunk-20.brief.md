You are reviewing chunk 20 of 23 of a code diff.

Your territory: lines 6180-6450 of the diff (271 lines, 10017 characters). The surrounding chunks belong to other agents — do not review them.

It covers these source files:
- modal-apps/bl1nk-app/environments/singularity.py (new-side lines 1-265)

**If the read comes back with `isTruncated` set, you do not have your chunk.** Keep calling `read_file` with a larger `offset` until you have the whole range. A receipt for a range you only half read makes the coverage guarantee a lie, which is worse than not having one.

You may also `read_file` the **full source files** above from the worktree whenever a hunk's correctness depends on code outside it. Diff context is three lines deep; state invariants are not. Page a source file that comes back truncated rather than reasoning from its first screenful.

## What to review

For your territory only, you own every dimension: line-by-line correctness, the removed-behavior audit of your own deleted lines, security, code quality, performance, test coverage, and the adversarial reading. Two duties are NOT yours, because a chunk agent is structurally blind to them: cross-file tracing (a caller in another chunk) and the cross-chunk half of removed-behavior. Audit the deletions in your own territory; do not conclude a deletion is unreplaced merely because its replacement is not in your range.

Format each finding using this structure:
- **File:** <file path>:<line number or range>
- **Anchor:** <1-3 consecutive lines copied VERBATIM from the diff — the code this finding is about>
- **Source:** [review]
- **Issue:** <one-line statement of the defect>
- **Failure scenario:** <the concrete trigger and the concrete wrong outcome: what input, state, timing, or config makes this code misbehave, and what incorrect output / crash / leak / exposure results>
- **Suggested fix:** <concrete code suggestion when possible, or "N/A">
- **Severity:** Critical | Suggestion | Nice to have
- **Confidence:** high | low

**The anchor is what places the comment, not the line number.** The line is computed from your snippet downstream; a bad snippet lands a real blocker on unrelated code, or gets it dropped. So:

- Copy it **verbatim** from the diff, indentation included. Strip the leading `+`.
- Prefer **added (`+`) lines** — that is what a review comments on. An unchanged context line inside a hunk resolves too. A **removed (`-`) line does not**: deleted code has no line on the side a comment can attach to. To comment on a deletion, anchor on the line that *replaced* it.
- Give **enough lines to be unique**. A bare `}` or `});` appears everywhere in the file and will resolve to whichever one happens to be nearest. Two or three lines are almost always unique; one distinctive line is fine.
- Fill in **File** and the line number anyway. The path selects the file and the line breaks a tie when the snippet genuinely repeats. Neither is trusted as the answer.

**The failure scenario is the finding's evidence, and it gates reporting.** For a quality finding, state the concrete cost instead of a crash — what is duplicated, wasted, or made harder to change — or quote the rule it violates. A **Suggestion** or **Nice to have** whose failure scenario you cannot fill in concretely **is not a finding: do not report it.** A suspected **Critical** whose trigger you cannot pin down IS still reported, at `Confidence: low`, with the scenario naming the mechanism and what remains uncertain — a later verification stage rules on it. "This looks risky", with no nameable trigger and no nameable cost, is how a hallucinated finding reaches a pull request.

Apply the severity definitions. **Severity describes the code, not your feelings about the finding.**
- **Critical** — the code does something wrong. A bug that produces incorrect behaviour, a security hole, data loss, a resource or state leak, a build or test failure. Not "important", not "large", not "I am confident": *wrong*.
- **Suggestion** — a recommended improvement to code that works.
- **Nice to have** — optional.

**A missing test is a Suggestion.** Absent code that does something wrong, nothing is broken, and "this file has zero references to `X`" is a coverage statistic, not a defect. Two shapes ARE Critical, because in both of them something *is* wrong: a test that asserts the **opposite** of the intended behaviour (it will bless the very regression it was written to catch), and a test **weakened, disabled or deleted in this diff** so that new behaviour passes. If a missing test would let a specific incorrect behaviour ship, report **that behaviour** as the Critical and cite the missing test as your evidence — naming the bug is the work; naming the gap is not.

An inflated severity blocks a merge: the verdict is computed from Criticals alone. Measured on one run of this skill, four "zero test coverage" findings were filed as Critical and two identical ones as Suggestion, in the same review, and the pull request was blocked partly on the strength of the four.

## What is NOT a finding

Do not report anything that matches these. Silence is better than noise — but a silently dropped **Critical** is neither, and it is unrecoverable, because no later stage ever sees it.

- **Pre-existing issues in unchanged code.** Review the diff. A defect entirely in code this change does not touch is out of scope, unless this change is what makes it newly reachable or newly wrong — in which case report it as an effect of this diff.
- **Style or formatting a formatter would auto-normalize**, and naming that matches the surrounding conventions. But a substantive issue a linter or type checker would flag — an unused variable, unreachable code, a type error — IS in scope, even where the surrounding code tolerates it.
- **Pedantic nitpicks** a senior engineer would not raise, and subjective "consider doing X" that names no real problem.
- **A Suggestion or Nice-to-have with no concrete failure scenario** — no nameable trigger, no nameable cost. (A suspected Critical in that state is reported at `Confidence: low` instead of dropped.)
- **A description of what the diff does, filed as a finding.** If your Suggested fix reads `N/A (already implemented)`, or the Issue praises the change instead of naming something wrong with it, that is a changelog entry. Drop it. Every finding must be something the author should **do**. A review of a good pull request is allowed to be empty, and an empty review is more useful than a padded one — dogfooded, one run reported five "Suggestions" that each summarised something the pull request already did, and the reader had to read all five to discover there was nothing to do.
- **If you are unsure whether a Suggestion or Nice to have is a problem, do not report it.** This does **not** apply to a suspected Critical.
- Minor refactors that address no real problem; missing documentation unless the logic is genuinely confusing; "best practice" citations that point to no concrete bug or risk.
- Issues already discussed in the pull request's existing comments.

## When you are done

If you found nothing, say so **and say what you examined** — the specific lines, files and cases you walked, in your own words. Do not recite a stock sentence: a return that names nothing you read is indistinguishable from never having read anything, and will be treated as such.

Then, on its own final line: `Covered: chunk 20 lines 6180-6450`