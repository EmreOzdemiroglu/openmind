# Compact banner

Remove the `ctrl-d quit · try /help` row from the interactive banner, including after `/new`
and a settings change. Provider, model, effort, and preset information remain visible. `/help`
and the keyboard shortcuts still work.

- Base revision: `95e0179c00266601b2c8345981e98895b1250699`
- Dependencies: none.
- Conflicts: other patches that change `banner_print()` or its test may need manual adjustment.
- Verification: `scripts/check.sh test banner agent` after applying the patch.

```sh
scripts/patch.sh inspect compact-banner
scripts/patch.sh check compact-banner
scripts/patch.sh apply compact-banner
make
```

The diff includes the changed banner and agent tests. Remove it with
`scripts/patch.sh reverse compact-banner`, then rebuild.
