# Desktop notifications

Emit terminal bell or OSC 9 notification sequences when background turns complete.

- Base revision: `349d100df94bf48d711d45d88a0e602a74275412`
- Dependencies: none.
- Conflicts: other patches modifying REPL turn completion in `src/agent.c`.
- Verification: `scripts/check.sh test config agent`

## Usage

```sh
scripts/patch.sh inspect notify
scripts/patch.sh check notify
scripts/patch.sh apply notify
make tests
make
```

Configure with `"notify": "auto"` (or `bel`, `osc9`, `off`) in `config.json` or via `HAX_NOTIFY`.
To remove, run `scripts/patch.sh reverse notify` and rebuild.
