# Per-app AI-polish styles — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Steps use `- [ ]`.

**Goal (approved design):** Add selectable AI-polish *styles* to Flow mode — **Tidy** (today's clean-up), **Prompt** (rewrite rambling speech into a clear AI instruction), and **Custom** (a per-app free-text instruction). Selectable as a global default *and* per-app via the existing profiles (e.g. `code.exe` → Prompt). Pure text→text; no code/context needed.

**Architecture:** A "style" just swaps the system prompt handed to the existing `cleanup.clean()` LLM. The effective style flows through the existing `App._eff()` profile-override mechanism, so per-app profiles override the global default. Only runs when AI cleanup (Flow mode) is on.

**Files:** `cleanup.py` (styles), `config.py` (2 fields), `app.py` (`_polish` passes style), `profiles.py` (KEYS + editor card), `settings.py` (global dropdown). Linux-testable: `cleanup._style_system()` + `profiles.resolve()` (both pure, import-light). UI = parse-check + Windows manual-verify.

**Branch:** `feat/polish-styles` (off main, v2.27.0).

---

## Task 1: cleanup styles (`cleanup.py`)

**Files:** Modify `wisprlite/cleanup.py`; Create `tests/test_cleanup_styles.py`

- [ ] **Step 1: failing test** — `tests/test_cleanup_styles.py`:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite import cleanup

def test_tidy_is_default():
    assert cleanup._style_system("tidy") == cleanup._TIDY
    assert cleanup._style_system("") == cleanup._TIDY
    assert cleanup._style_system("nonsense") == cleanup._TIDY  # unknown -> tidy

def test_prompt_style():
    s = cleanup._style_system("prompt")
    assert s == cleanup._PROMPT
    assert "rewrite" in s.lower() and "only" in s.lower()  # restructure + output-only rail

def test_custom_style():
    s = cleanup._style_system("custom", "Rewrite as a git commit message.")
    assert s.startswith("Rewrite as a git commit message.")
    assert "ONLY the rewritten text" in s  # safety rails appended
    # empty custom instruction falls back to tidy (never an empty/unsafe prompt)
    assert cleanup._style_system("custom", "   ") == cleanup._TIDY

if __name__ == "__main__":
    test_tidy_is_default(); test_prompt_style(); test_custom_style()
    print("OK")
```

Run: `python3 tests/test_cleanup_styles.py` → FAIL (`_style_system`/`_TIDY`/`_PROMPT` undefined).

- [ ] **Step 2: implement** — in `wisprlite/cleanup.py`, immediately AFTER the existing `SYSTEM = (...)` block (ends line 30), add:

```python

# The existing SYSTEM prompt IS the "tidy" style.
_TIDY = SYSTEM

_PROMPT = (
    "You rewrite a raw voice-dictation transcript into a clear, well-structured "
    "prompt for an AI assistant. The speaker is talking TO an AI (often a coding "
    "assistant) and may ramble, backtrack, or be disorganized. Reorganize their "
    "words into a clear, concise instruction the assistant can act on: keep EVERY "
    "requirement, constraint, name, file and detail they stated; tighten and order "
    "it for clarity; use light structure (a short paragraph, or a few bullet "
    "points) only when it genuinely helps. Do NOT add requirements, assumptions, "
    "scope, or specifics they did not say. Do NOT answer, execute, or comment on "
    "the request — only rewrite it. Return ONLY the rewritten prompt, nothing else."
)

# Appended to a user's CUSTOM instruction so user-defined styles stay safe.
_CUSTOM_RAILS = (
    " Apply that to the user's raw voice dictation. Preserve their intent and every "
    "specific they stated; do NOT add anything they did not say; do NOT answer, "
    "execute, or comment on the content — only rewrite it. Return ONLY the rewritten "
    "text, nothing else."
)


def _style_system(style: str = "tidy", custom_instruction: str = "") -> str:
    """The base system prompt for a polish style (before accent/notes clauses)."""
    style = (style or "tidy").strip().lower()
    if style == "prompt":
        return _PROMPT
    if style == "custom":
        ci = (custom_instruction or "").strip()
        return (ci + _CUSTOM_RAILS) if ci else _TIDY
    return _TIDY
```

- [ ] **Step 3: thread it through `clean()`** — change the `clean` signature and the system message. Replace:
```python
def clean(text: str, provider: str = "openai", model: str = "",
          language: str = "", notes: str = "") -> Optional[str]:
```
with:
```python
def clean(text: str, provider: str = "openai", model: str = "",
          language: str = "", notes: str = "",
          style: str = "tidy", custom_instruction: str = "") -> Optional[str]:
```
and replace this line:
```python
                {"role": "system", "content": SYSTEM + _accent_clause(language) + _notes_clause(notes)},
```
with:
```python
                {"role": "system", "content": _style_system(style, custom_instruction) + _accent_clause(language) + _notes_clause(notes)},
```

- [ ] **Step 4: pass** — `python3 tests/test_cleanup_styles.py` → `OK`. Also `python3 -c "import ast; ast.parse(open('wisprlite/cleanup.py').read()); print('ok')"`.
- [ ] **Step 5: commit** — `git add wisprlite/cleanup.py tests/test_cleanup_styles.py && git commit -m "feat(polish): tidy/prompt/custom cleanup styles in cleanup.py"`

---

## Task 2: per-app profile support (`profiles.py`)

**Files:** Modify `wisprlite/profiles.py`; Create `tests/test_profiles_style.py`

- [ ] **Step 1: failing test** — `tests/test_profiles_style.py`:

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from wisprlite import profiles

def test_resolve_passes_style_overrides():
    p = [{"name": "code.exe", "match": {"exe": "code.exe"},
          "overrides": {"engine": "deepgram", "cleanup_style": "prompt",
                        "cleanup_instruction": "x", "bogus": "drop"}}]
    ov = profiles.resolve(p, {"exe": "code.exe", "title": "whatever"})
    assert ov.get("cleanup_style") == "prompt", ov
    assert ov.get("cleanup_instruction") == "x", ov
    assert ov.get("engine") == "deepgram", ov
    assert "bogus" not in ov  # still whitelisted

def test_no_match_returns_empty():
    assert profiles.resolve([{"match": {"exe": "x.exe"}, "overrides": {"cleanup_style": "prompt"}}],
                            {"exe": "other.exe"}) == {}

if __name__ == "__main__":
    test_resolve_passes_style_overrides(); test_no_match_returns_empty()
    print("OK")
```

Run: `python3 tests/test_profiles_style.py` → FAIL (cleanup_style filtered out by current `KEYS`).

- [ ] **Step 2: widen the whitelist** — in `wisprlite/profiles.py`, change:
```python
KEYS = ("engine", "ai_cleanup", "auto_enter", "output_mode")
```
to:
```python
KEYS = ("engine", "ai_cleanup", "auto_enter", "output_mode", "cleanup_style", "cleanup_instruction")
```

- [ ] **Step 3: pass** — `python3 tests/test_profiles_style.py` → `OK`.

- [ ] **Step 4: editor UI** — add a Polish-style control to each profile card. In `wisprlite/profiles.py`:
  (a) After `P_OUTPUTS = [...]` (line 51), add:
  ```python
  P_STYLES = [("tidy", "Tidy — clean up"), ("prompt", "Prompt — for AI tools"), ("custom", "Custom…")]
  ```
  (b) In `add_card`, after the OUTPUT column block (the `out_col` … ends ~line 217), add a STYLE column + a custom-instruction row, mirroring the existing `eng_col`/`out_col` pattern:
  ```python
          sty_col = tk.Frame(ctl, bg=CARD)
          sty_col.pack(side="left", padx=(26, 0))
          tk.Label(sty_col, text="POLISH STYLE", bg=CARD, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
          style_var = tk.StringVar(value=dict(P_STYLES).get(overrides.get("cleanup_style", ""), P_STYLES[0][1]))
          ttk.Combobox(sty_col, textvariable=style_var, values=[l for _, l in P_STYLES],
                       state="readonly", width=16).pack(anchor="w", pady=(5, 0))
  ```
  Then after the `chk` checkbox frame (~line 224), add a custom-instruction entry:
  ```python
          instr_frame = tk.Frame(inner, bg=CARD)
          instr_frame.pack(fill="x", pady=(12, 0))
          tk.Label(instr_frame, text="Custom polish instruction (used when style = Custom)",
                   bg=CARD, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w")
          instr_var = tk.StringVar(value=overrides.get("cleanup_instruction", ""))
          ttk.Entry(instr_frame, textvariable=instr_var, width=60).pack(anchor="w", pady=(4, 0))
  ```
  (c) In the `card.update(...)` call (~line 226), add `style=style_var, instruction=instr_var`.
  (d) In `save()`, inside the per-card `ov = {...}` build (after `output_mode`, ~line 245), add:
  ```python
              "cleanup_style": _value_for(card["style"].get(), P_STYLES),
  ```
  and right after the `ov` dict, before the `eng = ...` line:
  ```python
              ci = card["instruction"].get().strip()
              if ci:
                  ov["cleanup_instruction"] = ci
  ```

- [ ] **Step 5: verify + commit** — `python3 -c "import ast; ast.parse(open('wisprlite/profiles.py').read()); print('ok')"`; re-run both tests. `git add wisprlite/profiles.py tests/test_profiles_style.py && git commit -m "feat(polish): per-app polish style in profiles (resolve + editor)"`

---

## Task 3: config + app wiring + global settings UI

**Files:** Modify `wisprlite/config.py`, `wisprlite/app.py`, `wisprlite/settings.py`

- [ ] **Step 1: config fields** — in `wisprlite/config.py`, after `cleanup_model: str = ""` (line 74), add:
```python
    cleanup_style: str = "tidy"       # tidy | prompt | custom — how Flow mode polishes
    cleanup_instruction: str = ""     # the instruction used when cleanup_style == "custom"
```
Verify: `python3 -c "from wisprlite.config import Config; c=Config(); print(c.cleanup_style, repr(c.cleanup_instruction))"` → `tidy ''`

- [ ] **Step 2: app `_polish` passes the effective style** — in `wisprlite/app.py`, in `_polish`, change:
```python
        polished = cleanup.clean(text, self.cfg.cleanup_provider, self.cfg.cleanup_model,
                                 self.cfg.language, self.cfg.speech_notes)
```
to:
```python
        polished = cleanup.clean(text, self.cfg.cleanup_provider, self.cfg.cleanup_model,
                                 self.cfg.language, self.cfg.speech_notes,
                                 style=self._eff("cleanup_style"),
                                 custom_instruction=self._eff("cleanup_instruction"))
```
(`_eff(key)` returns the per-app profile override else the global `cfg` value — so a profile's `cleanup_style` wins, else the global default. Both keys now exist on `Config` (Step 1) and pass through `profiles.resolve` (Task 2).)

- [ ] **Step 3: global Polish-style dropdown in Settings** — READ `wisprlite/settings.py` first. Near `CLEANUP_PROVIDERS` (top of file), add:
```python
STYLES = [("tidy", "Tidy — clean up"), ("prompt", "Prompt — for AI tools"), ("custom", "Custom…")]
```
In the **"Polish & text"** card (`c = card("Polish & text", ...)`, ~line 490), right AFTER the existing "Cleanup with" `combo(row(c, "Cleanup with", ...), cleanup_var, ...)` block (~line 493–500), add a style dropdown + a custom-instruction field, mirroring the EXACT widget helpers used there (`row`, `combo`, and whatever single-line text-entry helper the file uses for fields like `vocabulary`/`cleanup_model` — find it and mirror it):
```python
    cleanup_style_var = tk.StringVar(value=dict(STYLES).get(cfg.cleanup_style, STYLES[0][1]))
    combo(row(c, "Polish style", "Tidy keeps your words; Prompt rewrites rambling into a clear AI instruction; Custom uses your own instruction."),
          cleanup_style_var, [l for _, l in STYLES])
```
…and a text entry bound to a new `cleanup_instruction_var = tk.StringVar(value=cfg.cleanup_instruction)` labelled e.g. "Custom polish instruction" with sublabel "Used when Polish style = Custom." Use the same entry helper the file already uses for free-text settings (mirror `vocabulary` or `cleanup_model`'s entry — do NOT invent a new widget style).
In the save block (~line 588, near `cfg.cleanup_provider = value_for(cleanup_var, CLEANUP_PROVIDERS)`), add:
```python
        cfg.cleanup_style = value_for(cleanup_style_var, STYLES)
        cfg.cleanup_instruction = cleanup_instruction_var.get().strip()
```

- [ ] **Step 4: verify + commit** — `python3 -c "import ast; [ast.parse(open(p).read()) for p in ['wisprlite/config.py','wisprlite/app.py','wisprlite/settings.py']]; print('ok')"`; re-run `tests/test_cleanup_styles.py` + `tests/test_profiles_style.py` (`OK`). `git add wisprlite/config.py wisprlite/app.py wisprlite/settings.py && git commit -m "feat(polish): config fields + app wiring + global Polish-style setting"`

---

## Manual verification (Windows)
- [ ] Settings → Polish & text shows the "Polish style" dropdown + custom-instruction field; saving persists.
- [ ] App profiles editor: each card has a POLISH STYLE dropdown + custom-instruction; saving persists per app.
- [ ] Set `code.exe` profile → Prompt; dictate a rambling request into VS Code/Claude Code → it comes out as a clean, structured prompt (Flow mode must be ON). Dictate into a Tidy app → just tidied.
- [ ] Custom: set an instruction (e.g. "rewrite as a git commit message") → output follows it; empty custom instruction behaves like Tidy.

## Self-review
- Coverage: styles (T1) + per-app override (T2) + global default + app wiring (T3); guardrails baked into each style prompt; `_eff` precedence (profile > global). ✔
- Pure units tested on Linux (`_style_system`, `resolve`); UI parse-checked + Windows-verified. ✔
- Back-compat: `clean()` style defaults to "tidy" = today's behaviour; new config defaults to tidy/"". No behaviour change unless a style is chosen. ✔
- Out of scope: per-utterance style switching (a future hotkey); context-aware prompting (reading the open file).
