# Clipboard image and text capture

Capture images and text from the system clipboard using Ctrl-V in the REPL.

- Base revision: `02d3afa400540176ba1eba1a2ec6f4251fdd9560`
- Dependencies: none.
- Conflicts: other patches modifying editor paste hooks in `src/agent.c`.
- Verification: `scripts/check.sh test paste_image agent`

## Usage

```sh
scripts/patch.sh inspect clipboard-capture
scripts/patch.sh check clipboard-capture
scripts/patch.sh apply clipboard-capture
make tests
make
```

Press Ctrl-V in the REPL to paste clipboard image content as tracked temporary files.
To remove, run `scripts/patch.sh reverse clipboard-capture` and rebuild.
