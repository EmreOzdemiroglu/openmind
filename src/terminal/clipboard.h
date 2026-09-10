/* SPDX-License-Identifier: MIT */
#ifndef HAX_TERMINAL_CLIPBOARD_H
#define HAX_TERMINAL_CLIPBOARD_H

#include <stddef.h>

/* Terminals may silently discard larger OSC 52 payloads. */
#define CLIPBOARD_OSC52_MAX_BYTES 100000

/* Copy `text` to the user's clipboard. Local native helpers are preferred; SSH sessions and the
 * local fallback use OSC 52, with tmux passthrough when needed. Return 0 on success or -1 on
 * failure. When `error` is non-NULL, failure sets it to a borrowed static message. */
int clipboard_copy(const char *text, size_t text_len, const char **error);

/* Build an OSC 52 sequence for `text`, optionally wrapped for tmux passthrough. Return an
 * allocated, NUL-terminated sequence, or NULL when `text_len` exceeds CLIPBOARD_OSC52_MAX_BYTES.
 * `out_len` may receive the sequence length excluding the terminator. */
char *clipboard_osc52_sequence(const char *text, size_t text_len, int tmux_wrap, size_t *out_len);

#endif /* HAX_TERMINAL_CLIPBOARD_H */
