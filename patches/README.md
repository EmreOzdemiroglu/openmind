# Source patches

Customize hax by applying source diffs and rebuilding. Each directory contains one optional
feature, its documentation, and one `.diff`. The normal build uses the base source as checked in.
There is no runtime patch loader and no additional binary dependency.

| Patch | Effect |
| --- | --- |
| [compact-banner](compact-banner/README.md) | Keep the startup identity row, remove the key tips. |

See [the patch workflow](../docs/patches.md) to apply, remove, or publish a patch, and [the core
migration contract](../docs/core.md) for architectural boundaries and extraction criteria.
