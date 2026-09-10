# Core and optional-feature migration contract

This document defines the boundary between the hax base repository and optional features.
It specifies what belongs in the base binary, what belongs in the source patch catalog, and
the exact process for migrating optional capabilities out of base into patches.

## Purpose and distribution model

hax is a single-binary coding agent designed around a small, portable core. Every feature in
the base repository is maintained, compiled, and tested for all supported platforms.

Stock release binaries distributed via GitHub releases are built directly from the clean,
unmodified base tree. They do not include any patches from the catalog.

Users who want optional capabilities apply unified diffs from `patches/` and compile custom
binaries. Custom builds must be identified separately from stock releases in package names,
version outputs, or bug reports so that issues with third-party or optional patches do not
get confused with base defects.

## First-release core

The first-release core consists of the following ten components:

1. **Shared agent loop (`src/agent_core.{c,h}`, `src/agent_loop.{c,h}`).**
   Coordinates model stream processing, turn assembly, tool dispatch, multi-turn continuation,
   and cancellation across both interactive and non-interactive frontends. Tracks token usage
   and cost estimates.

2. **Canonical item log (`src/item.{c,h}`, `src/agent_session.{c,h}`).**
   The single source of truth for conversation state. A flat, append-only, provider-independent
   sequence of items recording user messages, assistant text, tool calls, tool results, summary
   seeds, and turn boundaries.

3. **Protocol adapters and shared transport**
   (`src/provider.{c,h}`, `src/providers/`, `src/transport/`).
   Translates between provider-independent `struct context` or `struct stream_event` and wire
   protocols such as OpenAI, Anthropic, OpenRouter, and llama.cpp. Shared transport manages
   HTTP and SSE mechanics.

4. **Ordinary coding tools (`src/tool.{c,h}`, `src/tools/`).**
   The core toolset: `bash`, `read`, `write`, and `edit`. Also includes background task control
   tools (`task_start`, `task_wait`, `task_stop`) to allow the model to manage concurrent work.

5. **Interactive REPL frontend**
   (`src/agent.{c,h}`, `src/render/`, `src/select.{c,h}`, `src/slash.{c,h}`, `src/terminal/`).
   The primary terminal interface, featuring line editing, Markdown rendering, visual diffs,
   prompt history, and interactive pickers for providers, models, and reasoning effort.

6. **One-shot execution and JSON output (`src/oneshot.{c,h}`).**
   Non-interactive runner (`hax -p`) that writes clean output to stdout for Unix pipeline
   composition, returns meaningful process exit codes, and provides streaming JSONL (`hax --json`).

7. **Session persistence and resume (`src/session.{c,h}`).**
   Appends conversation events to versioned JSONL files under `$XDG_STATE_HOME/hax/sessions/`,
   enabling session recovery with `--resume` and `-c`.

8. **Context compaction (`src/compaction.{c,h}`).**
   Monitors context usage against model limits, summarizes older history into an append-only
   summary item, and preserves full on-disk logs while keeping active prompts within bounds.

9. **Project instructions and skill discovery (`src/agent_env.{c,h}`).**
   Discovers and loads hierarchical `AGENTS.md` instruction files and `SKILL.md` directories,
   injecting them into the system prompt context.

10. **Runtime configuration registry (`src/config.{c,h}`).**
    Provides a typed, centralized registry of settings resolved through a defined priority order
    (run flags, conversation overrides, environment variables, state.json, config.json, defaults).

## Inclusion rules

Features are categorized into base core or optional patches using three architectural criteria.
Line count does not decide inclusion: a small platform quirk belongs in a patch if it serves
desktop convenience, while a large protocol parser belongs in base if it is needed for correct
model communication.

### Base core inclusion

A capability belongs in the base repository when it satisfies at least one of these criteria:

- **Correctness.** Enforces state invariants, turn boundaries, context limits, signal handling,
  or deterministic error recovery. Without it, the agent could corrupt conversation state, fail
  to terminate loops, or misinterpret model responses.
- **Resource management.** Controls the lifecycle of system resources, including joining worker
  threads, releasing child processes, cleaning temporary files, and restoring terminal modes.
- **Protocol and wire mechanics.** Implements LLM wire formats, streaming event parsing, HTTP
  transport, session file formats, or model catalog metadata.

### Patch catalog inclusion

A capability belongs in the source patch catalog (`patches/`) when it fits any of these roles:

- **Personal preference.** Customizes cosmetic appearance, key tips, banners, or prompts
  without altering core reasoning or execution semantics.
- **Desktop environment convenience.** Integrates with host desktop daemons, notification
  systems, sleep inhibitors, or graphical clipboard managers.
- **Niche workflows.** Specialized integrations or export formats that require non-standard host
  utilities or apply only to specific desktop environments.

## Initial extraction targets and base retentions

Three existing capabilities are designated as the first extraction targets:

1. **Desktop notifications (`src/terminal/notify.{c,h}`).**
   Emits terminal bells or OSC 9 notification sequences when turns finish. This is a desktop
   convenience feature that depends on terminal emulator capabilities.
2. **Idle sleep inhibition (`src/system/keepawake.{c,h}`).**
   Spawns platform-specific commands (`caffeinate`, `systemd-inhibit`) to prevent system sleep
   during long turns. This is a host environment convenience feature.
3. **Clipboard capture (`src/paste_image.{c,h}`).**
   Reads image or text data from desktop clipboards via external tools (`osascript`, `wl-paste`,
   `xclip`, `powershell`) to construct paste markers. This is an interactive desktop utility.

### Features retained in base

The following components remain in the base repository and will not be extracted:

- **Background tasks (`src/system/bg_job.{c,h}`, `src/tools/task_*.c`).**
  Provides the asynchronous worker infrastructure used for catalog refreshes, model metadata
  probing, subagent delegation, and long-running shell execution. Essential for agent concurrency
  and resource safety.
- **Presets (`src/config.c`).**
  Enables named bundles of provider, model, effort, and system prompts. Presets are required for
  model routing, subagent role assignments, and core configuration.
- **Provider authentication (`src/providers/`, `auth.json`).**
  Manages credentials, OAuth tokens, and device authorization flows. Clipboard writing
  (`clipboard_copy` in `src/terminal/clipboard.{c,h}`) remains in base because device code
  login workflows rely on copying codes and URLs to the clipboard.

## What extraction is and is not

Extraction has a strict definition in hax:

- **Extraction means complete source removal.** Code, headers, configuration registry entries,
  slash commands, user documentation, and dedicated tests are removed entirely from base.
  The feature is preserved as a unified diff in `patches/<name>/`.
- **Extraction is not a feature flag.** Leaving dead code or runtime boolean branches in base
  is not extraction.
- **Extraction is not an empty stub.** Leaving dummy functions that return 0 or no-op in base
  is not extraction.
- **Extraction is not a runtime plugin or hook bus.** hax does not add generic hook buses,
  dynamic callback registries, or plugin architectures to core. Such mechanisms introduce
  extra protocol rules, failure modes, and indirection into the core loop.

In an unpatched base checkout, there is no code, header, or configuration definition for an
extracted feature. The patch introduces the implementation and modifies the call sites directly.

## Configuration handling for extracted keys

When a feature is extracted from base, its configuration key is removed from `REGISTRY[]` in
`src/config.c`.

The base configuration parser (`config_init()`) loads `config.json` into a JSON DOM. Keys present
in `config.json` that are not in `REGISTRY[]` are ignored during resolution:

- The base binary does not fail, warn, or reject unknown top-level keys in `config.json`.
- The base binary does not rewrite or scrub `config.json` on disk to delete unrecognized keys.
- The base binary does not retain dummy or placeholder entries in `REGISTRY[]` for old keys.

If a user retains an extracted setting in `config.json` (such as `"notify": "off"`), running the
stock base binary safely ignores it. If the user applies the feature patch, the patch restores the
key in `REGISTRY[]`, and the user's existing setting takes effect immediately without manual
migration.

## Stock binaries and custom builds

- **Stock binaries:** Compiled from the unpatched repository. They represent the baseline
  behavior and are the only binaries covered by stock release tags.
- **Custom builds:** Compiled from a repository with one or more catalog patches applied or with
  local edits. Custom builds should adjust their build identification or report applied patches
  when reporting bugs.

## Extraction checklist

When extracting an optional feature from the base repository into a catalog patch, follow this
step-by-step checklist:

1. **Source and header removal.**
   - Delete the feature's implementation files and private headers from `src/`.
   - In calling code, remove calls, includes, and state variables associated with the feature.
     Do not leave stub functions or unused arguments.

2. **Build registration update.**
   - Remove the deleted source files from the `sources` array in `meson.build`.

3. **Configuration and UI removal.**
   - Remove feature keys from `REGISTRY[]` in `src/config.c`.
   - Remove associated CLI flags, slash command entries in `src/slash.c`, and keybinding hints.
   - Update `docs/configuration.md` and `docs/usage.md` to remove references to the feature.

4. **Test adjustments.**
   - Remove feature-only test sources from `tests/` and deregister them in `tests/meson.build`.
   - Update integration tests that checked the feature's settings to verify that base operates
     cleanly without them.

5. **Patch export and catalog registration.**
   - Create a clean feature commit on a branch based on the target release commit.
   - Export the commit as a unified diff using `git format-patch -1 --stdout`.
   - Save the diff under `patches/<feature-name>/hax-<feature-name>-YYYYMMDD-BASEHASH.diff`.
   - Create `patches/<feature-name>/README.md` documenting description, base revision,
     dependencies, conflicts, and verification commands.
   - Add the patch to `patches/README.md` and to the CI matrix in `.github/workflows/ci.yml`.

6. **Base and patched verification.**
   - On the unpatched base tree, run `make tests` and `make lint`. Verify all tests pass.
   - Apply the patch with `scripts/patch.sh apply <feature-name>`.
   - Run `make tests` and `make lint` on the patched tree. Verify tests pass.
   - Reverse the patch with `scripts/patch.sh reverse <feature-name>`.
   - Run `git status` and `git diff` to ensure the working tree returns to a clean state.

## Module ownership review and behavior-preservation checks

This section reviews the modules involved in the three initial extraction targets and defines
named checks to verify base behavior preservation.

### 1. Notifications

- **Modules involved:** `src/terminal/notify.{c,h}`, `src/agent.c`, `src/config.c`.
- **Extraction diff:** Removes `notify.{c,h}`, removes `notify_attention()` call from
  `src/agent.c`, and removes the `notify` entry from `REGISTRY[]` in `src/config.c`.
- **Named behavior-preservation checks:**
  - `check_repl_idle_clean`: When a multi-turn request completes in the REPL, the prompt is
    redrawn cleanly without emitting BEL (`\a`) or OSC 9 escape sequences to the terminal.
  - `check_cancel_preservation`: Pressing Esc interrupts turn processing immediately; the REPL
    returns to the prompt without triggering notification logic.
  - `check_config_notify_ignored`: Placing `"notify": "off"` in `config.json` does not cause
    startup errors, warnings, or unexpected output in base.

### 2. Keep-awake

- **Modules involved:** `src/system/keepawake.{c,h}`, `src/agent_loop.c`, `src/config.c`,
  `tests/system/test_keepawake.c`.
- **Extraction diff:** Removes `keepawake.{c,h}`, removes `keepawake_acquire()` and
  `keepawake_release()` from `src/agent_loop.c`, removes the `keep_awake` setting from
  `src/config.c`, and removes `tests/system/test_keepawake.c`.
- **Named behavior-preservation checks:**
  - `check_agent_loop_turn_cycle`: The agent loop executes user turns, stream turns, and tool
    dispatches cleanly without calling power assertion APIs.
  - `check_subcommand_reaping`: `waitpid` in child process management only reaps tool processes;
    no external inhibitor child processes (`caffeinate`, `systemd-inhibit`) are spawned.
  - `check_config_keepawake_ignored`: Specifying `"keep_awake": 0` in `config.json` or setting
    `HAX_KEEP_AWAKE=0` is ignored without error by the base binary.

### 3. Clipboard capture

- **Modules involved:** `src/paste_image.{c,h}`, `src/terminal/clipboard.{c,h}`, `src/agent.c`,
  `src/slash.c`, `tests/test_paste_image.c`.
- **Extraction diff:** Removes `paste_image.{c,h}`, removes `clipboard_paste_image()` and
  `clipboard_paste_text()` from `src/terminal/clipboard.{c,h}`, disconnects `editor.on_paste`
  and `editor.filter_paste` in `src/agent.c`, removes `ctrl-v` from `src/slash.c`, and removes
  `tests/test_paste_image.c`.
- **Base retention note:** `clipboard_copy()` and `clipboard_osc52_sequence()` remain in base
  inside `src/terminal/clipboard.{c,h}` to support `/copy` and provider login flows.
- **Named behavior-preservation checks:**
  - `check_repl_bracketed_paste`: Standard terminal bracketed paste continues to insert text
    cleanly into the prompt editor without spawning external clipboard utilities.
  - `check_provider_auth_clipboard`: Device authorization login flows in
    `src/providers/codex_login.c` continue to copy user codes and URLs to the system clipboard
    via `clipboard_copy()`.
  - `check_slash_copy`: The `/copy` command in `src/slash.c` continues to copy assistant responses
    to the system clipboard.
  - `check_no_helper_spawns`: Triggering line-editor shortcuts does not spawn external helper
    binaries (`wl-paste`, `xclip`, `osascript`, `powershell`).

## Migration entry templates

When the initial targets are migrated into the catalog, their patch README files must follow
these templates:

### Template for `patches/notify/README.md`

```markdown
# Desktop notifications

Emit terminal bell or OSC 9 notification sequences when background turns complete.

- Base revision: <BASE_COMMIT_HASH>
- Dependencies: none.
- Conflicts: other patches modifying REPL turn completion in `src/agent.c`.
- Verification: `scripts/check.sh test config agent`

## Usage

```sh
scripts/patch.sh check notify
scripts/patch.sh apply notify
make tests
make
```

Configure with `"notify": "auto"` (or `bel`, `osc9`, `off`) in `config.json` or via `HAX_NOTIFY`.
To remove, run `scripts/patch.sh reverse notify` and rebuild.
```

### Template for `patches/keep-awake/README.md`

```markdown
# Keep-awake sleep inhibition

Inhibit system idle sleep while model turns are running.

- Base revision: <BASE_COMMIT_HASH>
- Dependencies: none.
- Conflicts: other patches modifying the main loop in `src/agent_loop.c`.
- Verification: `scripts/check.sh test system/keepawake agent_loop`

## Usage

```sh
scripts/patch.sh check keep-awake
scripts/patch.sh apply keep-awake
make tests
make
```

Configure with `"keep_awake": 1` (or `0`) in `config.json` or via `HAX_KEEP_AWAKE`.
To remove, run `scripts/patch.sh reverse keep-awake` and rebuild.
```

### Template for `patches/clipboard-capture/README.md`

```markdown
# Clipboard image and text capture

Capture images and text from the system clipboard using Ctrl-V in the REPL.

- Base revision: <BASE_COMMIT_HASH>
- Dependencies: none.
- Conflicts: other patches modifying editor paste hooks in `src/agent.c`.
- Verification: `scripts/check.sh test paste_image agent`

## Usage

```sh
scripts/patch.sh check clipboard-capture
scripts/patch.sh apply clipboard-capture
make tests
make
```

Press Ctrl-V in the REPL to paste clipboard image content as tracked temporary files.
To remove, run `scripts/patch.sh reverse clipboard-capture` and rebuild.
```

## Glossary

The following terms define conversation state and presentation across hax:

- **Turn.** A single request-response exchange with a model provider. It starts with sending
  context and ends when the provider finishes streaming its response, producing one assistant
  message and zero or more tool calls.
- **User turn.** The complete execution cycle initiated by a user prompt. It comprises the
  initial user prompt plus every subsequent turn spawned by tool calls until the model finishes
  its answer or the user cancels execution.
- **Item log.** The canonical, in-memory sequence of `struct item` records owned by
  `struct agent_session`. It represents the complete, provider-independent history of the run,
  including user prompts, assistant text, tool calls, tool results, summaries, and turn boundaries.
- **Transcript.** The formatted model-facing context reconstructed from the item log. It can be
  inspected in the terminal using Ctrl-T or mirrored to a file using the `HAX_TRANSCRIPT`
  environment variable.
- **Display history.** The user-facing presentation rendered to the terminal screen by
  `render_ctx` and `disp`. It includes formatted Markdown, tool execution spinners, collapsed
  output previews, and status bars.
- **Session persistence.** The durable on-disk record of conversation items stored as JSONL
  under `$XDG_STATE_HOME/hax/sessions/`. It allows past sessions to be inspected or resumed with
  `hax --resume <id>` and streamed live to external orchestrators using `hax --json`.
