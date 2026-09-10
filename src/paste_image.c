/* SPDX-License-Identifier: MIT */
#include "paste_image.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "xalloc.h"
#include "system/clock.h"
#include "system/fd.h"
#include "system/tempfiles.h"
#include "terminal/clipboard_capture.h"
#include "terminal/paste_uri.h"
#include "tools/image_sniff.h"

size_t paste_image_normalize_text(char *text, size_t text_len)
{
    size_t write_offset = 0;
    for (size_t i = 0; i < text_len; i++) {
        char byte = text[i];
        if (byte == '\0')
            continue;
        if (byte == '\r') {
            if (i + 1 < text_len && text[i + 1] == '\n')
                continue;
            byte = '\n';
        }
        text[write_offset++] = byte;
    }
    text[write_offset] = '\0';
    return write_offset;
}

/* The read tool verifies content; the extension only hints at the already-sniffed data's type. */
static const char *extension_for_mime_type(const char *mime_type)
{
    if (strcmp(mime_type, "image/png") == 0)
        return ".png";
    if (strcmp(mime_type, "image/jpeg") == 0)
        return ".jpg";
    if (strcmp(mime_type, "image/gif") == 0)
        return ".gif";
    if (strcmp(mime_type, "image/webp") == 0)
        return ".webp";
    return "";
}

static char *persist_clipboard_image(const char *image, size_t image_len, const char *mime_type)
{
    char *path = NULL;
    int fd = tempfile_create("paste-", extension_for_mime_type(mime_type), &path);
    if (fd < 0)
        return NULL;
    int write_status = fd_write_all(fd, image, image_len);
    close(fd);
    if (write_status < 0) {
        unlink(path);
        tempfile_untrack(path);
        free(path);
        return NULL;
    }
    /* Trailing space so the user can keep typing after the marker. */
    char *marker = xasprintf("[pasted image: %s] ", path);
    free(path);
    return marker;
}

char *paste_image_capture(void)
{
    long deadline_ms = monotonic_ms() + CLIPBOARD_PASTE_TIMEOUT_MS;
    size_t image_len;
    char *image = clipboard_paste_image(&image_len, deadline_ms);
    if (image) {
        struct image_info info;
        char *marker = NULL;
        if (image_sniff(image, image_len, &info) && info.complete)
            marker = persist_clipboard_image(image, image_len, info.mime);
        free(image);
        if (marker)
            return marker;
    }

    size_t text_len;
    char *text = clipboard_paste_text(&text_len, deadline_ms);
    if (!text)
        return NULL;
    if (paste_image_normalize_text(text, text_len) == 0) {
        free(text);
        return NULL;
    }

    char *converted_uris = paste_uri_list_to_paths(text);
    if (converted_uris) {
        free(text);
        return converted_uris;
    }
    return text;
}
