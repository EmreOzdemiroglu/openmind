/* SPDX-License-Identifier: MIT */
#ifndef HAX_PASTE_IMAGE_H
#define HAX_PASTE_IMAGE_H

#include <stddef.h>

/* Capture the clipboard for insertion at the REPL cursor. A valid image is persisted to a tracked
 * temporary file and returned as a "[pasted image: <path>] " marker; otherwise clipboard text is
 * returned. The caller owns the returned string. Return NULL when neither form is available. */
char *paste_image_capture(void);

/* Normalize CRLF and lone CR to LF and remove NUL bytes in place. Return the new length. */
size_t paste_image_normalize_text(char *text, size_t text_len);

#endif /* HAX_PASTE_IMAGE_H */
