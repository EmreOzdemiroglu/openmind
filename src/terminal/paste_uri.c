/* SPDX-License-Identifier: MIT */
#include "terminal/paste_uri.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#include "buf.h"
#include "xalloc.h"

static int hex_digit_value(char digit)
{
    if (digit >= '0' && digit <= '9')
        return digit - '0';
    if (digit >= 'a' && digit <= 'f')
        return digit - 'a' + 10;
    if (digit >= 'A' && digit <= 'F')
        return digit - 'A' + 10;
    return -1;
}

/* Accept only local file URIs. Keep malformed escapes verbatim, but reject decoded NULs because
 * downstream filesystem APIs would silently truncate the path. */
static char *file_uri_to_path(const char *uri, size_t uri_len)
{
    static const char SCHEME[] = "file://";
    if (uri_len < sizeof(SCHEME) - 1 || strncmp(uri, SCHEME, sizeof(SCHEME) - 1) != 0)
        return NULL;
    const char *cursor = uri + sizeof(SCHEME) - 1;
    const char *end = uri + uri_len;
    if (cursor < end && *cursor != '/') {
        const char *slash = memchr(cursor, '/', (size_t)(end - cursor));
        if (!slash || (size_t)(slash - cursor) != 9 || strncmp(cursor, "localhost", 9) != 0)
            return NULL;
        cursor = slash;
    }
    if (cursor >= end || *cursor != '/')
        return NULL;

    struct buf path;
    buf_init(&path);
    while (cursor < end) {
        char byte = *cursor;
        int high, low;
        if (byte == '%' && cursor + 2 < end && (high = hex_digit_value(cursor[1])) >= 0 &&
            (low = hex_digit_value(cursor[2])) >= 0) {
            byte = (char)((high << 4) | low);
            if (byte == '\0') {
                buf_free(&path);
                return NULL;
            }
            cursor += 3;
        } else {
            cursor++;
        }
        buf_append(&path, &byte, 1);
    }
    return buf_steal(&path);
}

/* Avoid filesystem access in the raw-mode editor: a URI may name a FIFO or stalled mount. */
static int path_has_image_extension(const char *path)
{
    const char *extension = strrchr(path, '.');
    if (!extension)
        return 0;
    static const char *const IMAGE_EXTENSIONS[] = {".png", ".jpg", ".jpeg", ".gif", ".webp"};
    for (size_t i = 0; i < sizeof(IMAGE_EXTENSIONS) / sizeof(IMAGE_EXTENSIONS[0]); i++)
        if (strcasecmp(extension, IMAGE_EXTENSIONS[i]) == 0)
            return 1;
    return 0;
}

char *paste_uri_list_to_paths(const char *text)
{
    struct buf output;
    buf_init(&output);
    size_t converted_lines = 0;
    const char *line = text;
    while (*line) {
        const char *newline = strchr(line, '\n');
        size_t line_len = newline ? (size_t)(newline - line) : strlen(line);
        if (line_len > 0) {
            char *path = file_uri_to_path(line, line_len);
            if (!path) {
                buf_free(&output);
                return NULL;
            }
            if (converted_lines)
                buf_append(&output, "\n", 1);
            if (path_has_image_extension(path)) {
                char *marker = xasprintf("[pasted image: %s]", path);
                buf_append_str(&output, marker);
                free(marker);
            } else {
                buf_append_str(&output, path);
            }
            free(path);
            converted_lines++;
        }
        if (!newline)
            break;
        line = newline + 1;
    }
    if (!converted_lines) {
        buf_free(&output);
        return NULL;
    }
    buf_append(&output, " ", 1);
    return buf_steal(&output);
}
