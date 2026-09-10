# Customize hax with source patches

The [catalog](../patches/README.md) contains optional features as ordinary unified diffs.
This follows the [suckless patch workflow](https://suckless.org/hacking/): select a feature,
review its source changes, apply it, and rebuild your binary. Existing hax features remain in
the base for this first version. Future optional features can live entirely in the catalog.

## Apply a patch

Start from a clean checkout so your local feature changes are easy to review and commit.
Read the patch's README for its base revision, dependencies, and conflicts.

```sh
scripts/patch.sh list
scripts/patch.sh check compact-banner
scripts/patch.sh apply compact-banner
make tests
make
```

`check` checks all hunks without modifying source. `apply` changes the working tree without
staging files or creating commits. If a hunk conflicts, Git rejects the patch without applying
its other hunks. The helper does not use fuzzy conflict resolution or leave `.rej` files.
Unrelated local edits are preserved. Inspect `git diff` before committing your custom build.

The helper requires Git and a POSIX shell. Python is used by the development tests, as it is
elsewhere in this repository. There is one active diff per catalog directory. To use a diff
without the helper, including from an extracted source release:

```sh
git apply --check patches/compact-banner/hax-compact-banner-20260905-95e0179.diff
git apply patches/compact-banner/hax-compact-banner-20260905-95e0179.diff
# Or use the standard patch utility:
patch -p1 < patches/compact-banner/hax-compact-banner-20260905-95e0179.diff
```

The standard `patch` utility can partially apply a conflicting diff. The helper's all-hunks
conflict check comes from `git apply`.

## Maintain a custom build

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

Create a feature branch from a known base revision. Change the source and its tests, then run
`clang-format -i` on changed C files, `make tests`, and `make lint`. Commit the feature with a
message that explains its behavior. Export that single feature commit:

```sh
git format-patch -1 --stdout > /tmp/hax-my-feature-YYYYMMDD-BASEHASH.diff
```

Use the modification date and the short hash of the **base** commit in the filename. Then, on
a branch with the unmodified base source, add the exported diff to `patches/my-feature/`.
Add a README with behavior, full base revision, dependencies, conflicts, and verification
commands. Link it from `patches/README.md` and add its name to the patch matrix in
`.github/workflows/ci.yml`. Each patch must contain its tests and apply with `git apply` or
`patch -p1`. Keep one feature per diff and one current diff per directory.

The catalog PR contains the diff, not the already-applied feature. This keeps the base build
independent of optional customizations. CI applies each selected patch before building and
running the C and end-to-end tests.
