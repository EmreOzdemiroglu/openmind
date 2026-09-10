# Source patches

Customize hax by applying source diffs and rebuilding. Each directory contains one optional
feature, its documentation, and one `.diff`. The normal build uses the base source as checked in.
There is no runtime patch loader and no additional binary dependency.

| Patch | Effect |
| --- | --- |
| [compact-banner](compact-banner/README.md) | Keep the startup identity row, remove the key tips. |
| [notify](notify/README.md) | Emit terminal bell or OSC 9 notification sequences when turns finish. |

See [the patch workflow](../docs/patches.md) to apply, remove, or publish a patch, and [the core
migration contract](../docs/core.md) for architectural boundaries and extraction criteria.
| [keep-awake](keep-awake/README.md) | Inhibit system idle sleep while model turns are running. |
| [clipboard-capture](clipboard-capture/README.md) | Capture images and text from clipboard via Ctrl-V in REPL. |
