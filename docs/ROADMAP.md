Jarvis-MK37 — Roadmap (priority-first)

Phase 0 — Foundation (now)
1. Define vision & priorities (done)
2. Fix browser attachment (Windows): detect/activate taskbar Chrome, fallback to Playwright persistent context attaching to first profile, and CDP remote-debug fallback.
3. Resolve `error_handler` ↔ `code_helper` mismatch and sanitize generated-step schema.
4. Add unit tests for actions and CI pipeline.

Phase 1 — Robustness
5. Improve ASR: VAD, noise suppression, multi-mic selection, model fallback.
6. Add telemetry (opt-in), logs, and metrics dashboard.
7. Add formatting and linting, enforce pre-commit hooks.

Phase 2 — Extensibility
8. Design plugin API and loader; allow third-party action packages.
9. Implement an action registry, versioning, and capability flags.
10. Build a simple GUI dashboard for action history, logs, and settings.

Phase 3 — Intelligence
11. Integrate an advanced LLM planner with grounding and verifier.
12. Add capability to synthesize and run safe code snippets with sandboxing.
13. Provide multi-modal agents: screen understanding, OCR, face/emotion-aware responses.

Immediate next tasks for "Fix browser attachment"
- Reproduce problem and add detailed logs for browser launches.
- Implement `open_app` native activation helper (WinAPI / pygetwindow / pywinauto).
- Update `browser_control` to prefer native activation for searches and `launch_persistent_context` with `--profile-directory=<first profile>`.
- Add fallback to connect via Chrome remote-debugging port when a native window exists but cannot be controlled.
- Add tests and a small `tools/browser_test.py` helper to validate expected behavior.

