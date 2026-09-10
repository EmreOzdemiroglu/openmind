/* SPDX-License-Identifier: MIT */
#ifndef HAX_TERMINAL_PASTE_URI_H
#define HAX_TERMINAL_PASTE_URI_H

#include <stddef.h>

/* Convert a newline-separated list of local file:// URIs to paths. Paths with recognized image
 * extensions become pasted-image markers without accessing the filesystem. Return an allocated
 * replacement, or NULL when `text` is not a non-empty URI list. */
char *paste_uri_list_to_paths(const char *text);

#endif /* HAX_TERMINAL_PASTE_URI_H */
