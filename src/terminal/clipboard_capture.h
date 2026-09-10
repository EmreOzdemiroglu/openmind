/* SPDX-License-Identifier: MIT */
#ifndef HAX_TERMINAL_CLIPBOARD_CAPTURE_H
#define HAX_TERMINAL_CLIPBOARD_CAPTURE_H

#include <stddef.h>

#define CLIPBOARD_PASTE_TIMEOUT_MS 5000

/* Read unvalidated image bytes from the platform clipboard. Return an allocated buffer and set
 * `out_len`, or return NULL on failure or when no supported image is available. `deadline_ms` is an
 * absolute monotonic_ms() instant shared by every helper attempt. In SSH sessions this reads the
 * remote host's clipboard because OSC 52 has no read operation. */
char *clipboard_paste_image(size_t *out_len, long deadline_ms);

/* Read text from the platform clipboard under the same deadline contract. Return allocated,
 * NUL-terminated bytes and set `out_len` to their length excluding the terminator. Return NULL on
 * failure or for an empty clipboard. The bytes are otherwise unnormalized. */
char *clipboard_paste_text(size_t *out_len, long deadline_ms);

#endif /* HAX_TERMINAL_CLIPBOARD_CAPTURE_H */
