/* SPDX-License-Identifier: MIT */
#ifndef HAX_CONFIG_DEF_H
#define HAX_CONFIG_DEF_H

/* Schema version for compile-time personal display defaults. */
#define HAX_DEFAULTS_SCHEMA 1

/* Shipped compiled defaults for display settings. These apply when not overridden by
 * runtime configuration, environment variables, state, or command-line flags. */
#define HAX_DEFAULT_MARKDOWN      "1"
#define HAX_DEFAULT_DISPLAY_WIDTH "auto"
#define HAX_DEFAULT_THEME         "auto"
#define HAX_DEFAULT_TINT          "teal"

#endif /* HAX_CONFIG_DEF_H */
