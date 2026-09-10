# Customize hax with source patches

The [catalog](../patches/README.md) contains optional features as versioned unified diffs.
This follows the [suckless patch workflow](https://suckless.org/hacking/): select a feature,
review its source changes, apply it, and rebuild your binary. Existing hax features remain in
the base for this first version. Future optional features can live entirely in the catalog.
See [docs/core.md](core.md) for the core architecture boundary, inclusion rules, and the
optional-feature migration contract.

## Selectors and operations

Patches are identified by selectors:
- Exact selector: `feature@revision` (e.g. `compact-banner@1`).
- Short selector: `feature` (e.g. `compact-banner`), which resolves to the single `active` revision.

Public operations provided by `scripts/patch.sh`:
- `scripts/patch.sh list`: lists all patches in the catalog (`feature@revision`, marking archived).
- `scripts/patch.sh inspect <selector>`: displays patch metadata (base commit, diff, digest,
  requirements, conflicts, status).
- `scripts/patch.sh catalog-check`: validates catalog schema, commit existence, digests, and
  consistency offline.
- `scripts/patch.sh check <selector>`: checks hunks without modifying source.
- `scripts/patch.sh apply <selector>`: applies the diff to the working tree.
- `scripts/patch.sh reverse <selector>`: reverses the diff from the working tree.

## Apply a patch

Start from a clean checkout so your local feature changes are easy to review and commit.
Inspect the patch metadata before applying.

```sh
scripts/patch.sh list
scripts/patch.sh inspect compact-banner
scripts/patch.sh check compact-banner
scripts/patch.sh apply compact-banner
make tests
make
```

`check` checks all hunks without modifying source. `apply` changes the working tree without
staging files or creating commits. If a hunk conflicts, Git rejects the patch without applying
its other hunks. The helper does not use fuzzy conflict resolution or leave `.rej` files.
Unrelated local edits are preserved. The recorded base commit is reported for compatibility only;
manual mode does not require `HEAD` to equal that commit and does not reproduce dependencies.
Apply and reverse dependencies explicitly, one selected artifact at a time. Inspect `git diff`
before committing your custom build.

The `check`, `apply`, and `reverse` actions require Git and a POSIX shell; `list` only
requires the shell. Python is used by the development tests and catalog validation. To use a diff
without the helper, including from an extracted source release:

```sh
git apply --check patches/compact-banner/1/hax-compact-banner-20260905-95e0179.diff
git apply patches/compact-banner/1/hax-compact-banner-20260905-95e0179.diff
# Or use the standard patch utility:
patch -p1 < patches/compact-banner/1/hax-compact-banner-20260905-95e0179.diff
```

## CI verification

The patch CI runner validates every catalog entry, discovers the active revisions, and resolves
each active artifact's complete `requires` closure in dependency-first order. It applies that
closure in a temporary worktree at the declared `base_commit`, then builds and tests it. It also
applies the same closure to a temporary worktree at the candidate `HEAD`, runs the full tests, and
runs the lint gate. This catches both an invalid recorded patch and drift in the current source.

The base worktree does not need to contain the catalog or runner. The runner reads those files
from the candidate checkout and passes their diff paths to Git, so a base commit may predate the
patch system. Archived entries are still checked for schema and digest validity but are not
tested as standalone CI candidates.

Run the same verification locally after fetching the repository history:

```sh
python3 scripts/patch_ci.py --discover
python3 scripts/patch_ci.py
```

## Catalog metadata schema (Schema 1)

Each revision directory `patches/<feature>/<revision>/` contains a `patch.json` file.
Fields:
- `schema`: Integer (currently `1`).
- `feature`: Lowercase ASCII string (`^[a-z][a-z0-9-]*$`).
- `revision`: Positive integer (`1, 2, ...`).
- `base_commit`: Exactly 40 lowercase hex characters referencing a valid local commit object.
- `diff`: Revision-directory-relative filename of the diff.
- `sha256`: Exactly 64 lowercase hex characters matching the diff's SHA-256 digest.
- `requires`: Explicitly ordered full prerequisite closure of exact selectors (`feature@rev`).
- `conflicts`: List of conflicting feature IDs (either-side exclusion).
- `status`: `"active"` or `"archived"`. Only one revision per feature can be active.

Example (`patches/compact-banner/1/patch.json`):

```json
{
  "schema": 1,
  "feature": "compact-banner",
  "revision": 1,
  "base_commit": "95e0179c00266601b2c8345981e98895b1250699",
  "diff": "hax-compact-banner-20260905-95e0179.diff",
  "sha256": "21b43358ea5bb86d18790f4d2283ce371ecf79c146a6f83a7c70d34bc34d098d",
  "requires": [],
  "conflicts": [],
  "status": "active"
}
```

## Maintain a custom build

Stock release binaries represent the pure base code without patches. When distributing or
reporting issues on custom builds, state which catalog patches or local edits are applied.

Keep your customization commits on a personal branch. Apply dependencies first, then dependent
patches, one command at a time. Record that order in your branch's documentation. A sequence of
commands is not a transaction: earlier successful patches remain if a later patch fails.
The helper does not track installed patches or resolve feature dependencies.

Manual commands therefore apply and reverse only the artifact named by each command; `requires`
is descriptive and does not trigger additional operations. A future recipe-based path will
enforce the complete selected dependency and conflict set as one validated selection.

To remove a feature, reverse dependent patches first, then rebuild:

```sh
scripts/patch.sh reverse compact-banner
make tests
make
```

Reversal fails if later edits conflict with the patch. Keep your local work and resolve the
source changes manually in that case. After updating the base, review and retest your custom
branch. A patch that applies cleanly can still conflict semantically with another feature.
CI tests each catalog patch individually; it does not promise compatibility between all pairs.

## Publish a patch

Features must follow the inclusion rules and the extraction checklist in [docs/core.md](core.md).

Create a feature branch from a known base revision. Change the source and its tests, then run
`clang-format -i` on changed C files, `make tests`, and `make lint`. Commit the feature with a
message that explains its behavior. Export that single feature commit:

```sh
git format-patch -1 --stdout > /tmp/hax-my-feature-YYYYMMDD-BASEHASH.diff
```

Create a new directory `patches/<feature>/<rev>/`, save the diff there, compute its SHA-256 digest,
and write `patch.json`. Add documentation in `patches/<feature>/README.md`. Run
`scripts/patch.sh catalog-check` to validate.

## Custom-build recipes (Schema 1)

A locked build recipe (`recipe.json`) pins a common base commit and an exact ordered sequence
of catalog patches, plus optional personal defaults:

```json
{
  "schema": 1,
  "base_commit": "95e0179c00266601b2c8345981e98895b1250699",
  "patches": [
    {
      "id": "compact-banner@1",
      "sha256": "21b43358ea5bb86d18790f4d2283ce371ecf79c146a6f83a7c70d34bc34d098d"
    }
  ]
}
```

Validate a recipe offline without modifying source or Git state:

```sh
scripts/patch.sh recipe-check path/to/recipe.json
```

## Preparing locked patched source

Turn a validated recipe into a standalone source tree with `scripts/patch.sh prepare`:

```sh
scripts/patch.sh prepare path/to/recipe.json --output /path/to/destination
```

This exports the pinned base commit from Git, applies patches sequentially into an isolated
staging directory, writes a `receipt.json` files inventory, and moves the final result to the
destination directory without modifying the caller's working tree or index.

## Building and verifying prepared source

Build or verify a prepared tree with fixed project commands:

```sh
scripts/patch.sh build /path/to/destination
scripts/patch.sh verify /path/to/destination
```

`build` compiles the prepared source. `verify` compiles, validates personal defaults (if
configured), and runs tests. Upon completion, a `build-result.json` artifact records the exact
inputs, compiler/tool versions, and phase outcomes.
