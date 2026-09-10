/* SPDX-License-Identifier: MIT */
#include "terminal/clipboard_capture.h"

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>

#include "buf.h"
#include "xalloc.h"
#include "system/clock.h"
#include "system/path.h"
#include "system/spawn.h"

#define CLIPBOARD_IMAGE_MAX_BYTES (20 * 1024 * 1024)
#define CLIPBOARD_TEXT_MAX_BYTES  (10 * 1024 * 1024)
#define CLIPBOARD_TYPES_MAX_BYTES (16 * 1024)

static char *capture_helper_output(const char *const *argv, size_t max_bytes, long deadline_ms,
                                   size_t *out_len)
{
    long remaining_ms = deadline_ms - monotonic_ms();
    if (remaining_ms <= 0)
        return NULL;
    int timeout_ms = remaining_ms > INT_MAX ? INT_MAX : (int)remaining_ms;
    return spawn_capture_stdout(argv, max_bytes, timeout_ms, out_len);
}

#ifdef __APPLE__
/* AppleScript writes binary clipboard data through a file rather than stdout. */
static char *paste_image_with_osascript(size_t *out_len, long deadline_ms)
{
    const char *temp_dir = getenv("TMPDIR");
    if (!temp_dir || !*temp_dir)
        temp_dir = "/tmp";
    char *path = path_join(temp_dir, "hax-clip-XXXXXX");
    int fd = mkstemp(path);
    if (fd < 0) {
        free(path);
        return NULL;
    }

    /* Escape backslashes and double quotes for an AppleScript string literal. */
    struct buf escaped;
    buf_init(&escaped);
    for (const char *cursor = path; *cursor; cursor++) {
        if (*cursor == '\\' || *cursor == '"')
            buf_append(&escaped, "\\", 1);
        buf_append(&escaped, cursor, 1);
    }
    char *escaped_path = buf_steal(&escaped);
    /* The UTF-8 guillemets delimit AppleScript's raw PNG class name. */
    char *script = xasprintf("set f to open for access POSIX file \"%s\" with write permission\n"
                             "write (the clipboard as \xc2\xab"
                             "class PNGf\xc2\xbb) to f\n"
                             "close access f",
                             escaped_path);
    free(escaped_path);

    const char *argv[] = {"osascript", "-e", script, NULL};
    size_t ignored_len;
    char *helper_output =
        capture_helper_output(argv, CLIPBOARD_IMAGE_MAX_BYTES, deadline_ms, &ignored_len);
    free(helper_output);
    free(script);

    char *image = NULL;
    struct stat status;
    if (fstat(fd, &status) == 0 && status.st_size > 0 &&
        (size_t)status.st_size <= CLIPBOARD_IMAGE_MAX_BYTES) {
        size_t image_len = (size_t)status.st_size;
        image = xmalloc(image_len);
        ssize_t bytes_read = 0;
        size_t offset = 0;
        while (offset < image_len &&
               (bytes_read = pread(fd, image + offset, image_len - offset, (off_t)offset)) > 0) {
            offset += (size_t)bytes_read;
        }
        if (offset != image_len) {
            free(image);
            image = NULL;
        } else {
            *out_len = image_len;
        }
    }
    close(fd);
    unlink(path);
    free(path);
    return image;
}
#else

/* Return the most preferred supported MIME type, borrowed from a static table. */
static const char *pick_image_mime_type(const char *offered_types)
{
    static const char *const SUPPORTED_TYPES[] = {"image/png", "image/jpeg", "image/gif",
                                                  "image/webp"};
    const char *selected_type = NULL;
    size_t selected_rank = sizeof(SUPPORTED_TYPES) / sizeof(SUPPORTED_TYPES[0]);
    const char *line = offered_types;

    while (*line) {
        const char *newline = strchr(line, '\n');
        size_t line_len = newline ? (size_t)(newline - line) : strlen(line);
        for (size_t rank = 0; rank < selected_rank; rank++) {
            const char *supported_type = SUPPORTED_TYPES[rank];
            if (line_len == strlen(supported_type) &&
                strncmp(line, supported_type, line_len) == 0) {
                selected_type = supported_type;
                selected_rank = rank;
                break;
            }
        }
        if (!newline)
            break;
        line = newline + 1;
    }
    return selected_type;
}

/* `listing_succeeded` distinguishes an authoritative no-image result from an unavailable helper. */
static const char *list_image_mime_type(const char *const *argv, int *listing_succeeded,
                                        long deadline_ms)
{
    size_t listing_len;
    char *listing =
        capture_helper_output(argv, CLIPBOARD_TYPES_MAX_BYTES, deadline_ms, &listing_len);
    if (!listing)
        return NULL;

    if (listing_succeeded)
        *listing_succeeded = 1;
    const char *mime_type = pick_image_mime_type(listing);
    free(listing);
    return mime_type;
}
#endif /* __APPLE__ */

char *clipboard_paste_image(size_t *out_len, long deadline_ms)
{
#ifdef __APPLE__
    return paste_image_with_osascript(out_len, deadline_ms);
#else
    /* Prefer the Wayland clipboard over the potentially stale XWayland selection. */
    if (getenv("WAYLAND_DISPLAY")) {
        const char *list_argv[] = {"wl-paste", "--list-types", NULL};
        int listing_succeeded = 0;
        const char *mime_type = list_image_mime_type(list_argv, &listing_succeeded, deadline_ms);
        if (mime_type) {
            const char *read_argv[] = {"wl-paste", "-t", mime_type, NULL};
            return capture_helper_output(read_argv, CLIPBOARD_IMAGE_MAX_BYTES, deadline_ms,
                                         out_len);
        }
        if (listing_succeeded)
            return NULL;
    }

    const char *list_argv[] = {"xclip", "-selection", "clipboard", "-t", "TARGETS", "-o", NULL};
    const char *mime_type = list_image_mime_type(list_argv, NULL, deadline_ms);
    if (!mime_type)
        return NULL;
    const char *read_argv[] = {"xclip", "-selection", "clipboard", "-t", mime_type, "-o", NULL};
    return capture_helper_output(read_argv, CLIPBOARD_IMAGE_MAX_BYTES, deadline_ms, out_len);
#endif
}

char *clipboard_paste_text(size_t *out_len, long deadline_ms)
{
    {
        const char *argv[] = {"pbpaste", NULL};
        char *text = capture_helper_output(argv, CLIPBOARD_TEXT_MAX_BYTES, deadline_ms, out_len);
        if (text)
            return text;
    }
    if (getenv("WAYLAND_DISPLAY")) {
        /* A responding Wayland clipboard is authoritative over the XWayland selection. */
        const char *list_argv[] = {"wl-paste", "--list-types", NULL};
        size_t listing_len;
        char *listing =
            capture_helper_output(list_argv, CLIPBOARD_TYPES_MAX_BYTES, deadline_ms, &listing_len);
        if (listing) {
            free(listing);
            /* Pin the documented any-text alias; untyped wl-paste may select raw image bytes. */
            const char *read_argv[] = {"wl-paste", "-n", "-t", "text", NULL};
            return capture_helper_output(read_argv, CLIPBOARD_TEXT_MAX_BYTES, deadline_ms, out_len);
        }
    }
    {
        const char *argv[] = {"xclip", "-selection", "clipboard", "-o", NULL};
        char *text = capture_helper_output(argv, CLIPBOARD_TEXT_MAX_BYTES, deadline_ms, out_len);
        if (text)
            return text;
    }
    {
        const char *argv[] = {"xsel", "-b", "-o", NULL};
        char *text = capture_helper_output(argv, CLIPBOARD_TEXT_MAX_BYTES, deadline_ms, out_len);
        if (text)
            return text;
    }
    return NULL;
}
