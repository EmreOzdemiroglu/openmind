# Keep-awake sleep inhibition

Inhibit system idle sleep while model turns are running.

- Base revision: `78277be073aa9250794852c7559c15319f6950f4`
- Dependencies: none.
- Conflicts: other patches modifying the main loop in `src/agent_loop.c`.
- Verification: `scripts/check.sh test system/keepawake agent_loop`

## Usage

```sh
scripts/patch.sh inspect keep-awake
scripts/patch.sh check keep-awake
scripts/patch.sh apply keep-awake
make tests
make
```

Configure with `"keep_awake": 1` (or `0`) in `config.json` or via `HAX_KEEP_AWAKE`.
To remove, run `scripts/patch.sh reverse keep-awake` and rebuild.
