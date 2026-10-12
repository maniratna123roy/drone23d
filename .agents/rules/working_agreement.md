# Spatial Twin — Working Agreement & Project Rules

Source: `PLAN.md` Section 16

## Standing Rules
1. **Read PLAN.md** fully before every phase. Do not invent requirements; if something is unclear, ask.
2. **One phase at a time**: Finish, verify, report, then STOP and wait for user's explicit confirmation to proceed.
3. **Beginner mode**: Before new concepts, provide a one-line real-world analogy, then the code. Explain what / why / where / how it connects.
4. **Complete working files, not fragments**: State `FILE: path` for every file created or changed; do not silently modify unrelated files.
5. **No hard-coded secrets**: `.env` + `.env.example`. Validate all input. Handle errors with friendly messages.
6. **Command discipline**: Give only commands needed for current step, each followed by "What this does".
7. **Testing after every step**: Document how to test + expected result. Never declare "done" until tests pass.
8. **Simplest reliable approach**: No new library without justification and explicit user approval.
9. **Document decisions**: Record every working command/version in `docs/commands.md` and every decision in `docs/decisions.md`.
10. **Honesty rule**: Never claim a feature exists that has not been built and tested.
