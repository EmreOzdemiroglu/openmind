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
Unrelated local edits are preserved. Inspect `git diff` before committing your custom build.

The `check`, `apply`, and `reverse` actions require Git and a POSIX shell; `list` only
requires the shell. Python is used by the development tests and catalog validation. To use a diff
without the helper, including from an extracted source release:

```sh
git apply --check patches/compact-banner/1/hax-compact-banner-20260905-95e0179.diff
git apply patches/compact-banner/1/hax-compact-banner-20260905-95e0179.diff
# Or use the standard patch utility:
patch -p1 < patches/compact-banner/1/hax-compact-banner-20260905-95e0179.diff
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
