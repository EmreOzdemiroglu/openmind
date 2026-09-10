/* SPDX-License-Identifier: MIT */
#include "terminal/clipboard.h"

#include <fcntl.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
/* fstat backs the __APPLE__-only osascript path, which the Linux lint pass
 * cannot see; the wait macros are used unconditionally but glibc also leaks
 * them through <stdlib.h>, so the include cleaner cannot attribute them. */
#include <sys/stat.h> // IWYU pragma: keep
#include <sys/wait.h> // IWYU pragma: keep

#include "xalloc.h"
#include "system/clock.h"
/* The buf builders are __APPLE__-only here, invisible to the Linux lint pass. */
#include "buf.h" // IWYU pragma: keep
#include "system/fd.h"
/* path_join is __APPLE__-only here, invisible to the Linux lint pass. */
#include "system/path.h" // IWYU pragma: keep
#include "system/spawn.h"
#include "terminal/ansi.h"
#include "text/base64.h"

/* Cap untrusted helper output before it reaches the editor or image decoder. */
#define CLIPBOARD_IMAGE_MAX_BYTES (64u << 20)
#define CLIPBOARD_TEXT_MAX_BYTES  (1u << 20)
#define CLIPBOARD_TYPES_MAX_BYTES (64u << 10)

#define OSC52_PREFIX      ANSI_ESC "]52;c;"
#define OSC52_SUFFIX      ANSI_BEL
#define TMUX_OSC52_PREFIX ANSI_TMUX_PASSTHROUGH_BEGIN OSC52_PREFIX
#define TMUX_OSC52_SUFFIX OSC52_SUFFIX ANSI_TMUX_PASSTHROUGH_END

char *clipboard_osc52_sequence(const char *text, size_t text_len, int tmux_wrap, size_t *out_len)
{
    if (text_len > CLIPBOARD_OSC52_MAX_BYTES)
        return NULL;

    size_t encoded_len;
    char *encoded = base64_encode(text, text_len, &encoded_len);
    const char *prefix = tmux_wrap ? TMUX_OSC52_PREFIX : OSC52_PREFIX;
    const char *suffix = tmux_wrap ? TMUX_OSC52_SUFFIX : OSC52_SUFFIX;
    size_t prefix_len = strlen(prefix);
    size_t suffix_len = strlen(suffix);
    size_t sequence_len = prefix_len + encoded_len + suffix_len;
    char *sequence = xmalloc(sequence_len + 1);

    memcpy(sequence, prefix, prefix_len);
    memcpy(sequence + prefix_len, encoded, encoded_len);
    memcpy(sequence + prefix_len + encoded_len, suffix, suffix_len + 1);
    free(encoded);

    if (out_len)
        *out_len = sequence_len;
    return sequence;
}

/* Use argv-based exec so probing PATH never invokes a shell. */
static int run_copy_helper(const char *const *argv, const char *text, size_t text_len)
{
    int pipe_fds[2];
    if (pipe(pipe_fds) < 0)
        return -1;

    struct spawn_signal_state signals;
    spawn_parent_ignore_signals(&signals);

    pid_t pid = fork();
    if (pid < 0) {
        close(pipe_fds[0]);
        close(pipe_fds[1]);
        spawn_parent_restore_signals(&signals);
        return -1;
    }
    if (pid == 0) {
        close(pipe_fds[1]);
        if (pipe_fds[0] != STDIN_FILENO) {
            if (dup2(pipe_fds[0], STDIN_FILENO) < 0)
                _exit(127);
            close(pipe_fds[0]);
        }

        int null_fd = open("/dev/null", O_WRONLY);
        if (null_fd >= 0) {
            dup2(null_fd, STDOUT_FILENO);
            dup2(null_fd, STDERR_FILENO);
            if (null_fd > STDERR_FILENO)
                close(null_fd);
        }
        spawn_child_reset_signals();
        execvp(argv[0], (char *const *)argv);
        _exit(127);
    }

    close(pipe_fds[0]);
    int write_status = fd_write_all(pipe_fds[1], text, text_len);
    close(pipe_fds[1]);
    int status = spawn_wait_child(pid);
    spawn_parent_restore_signals(&signals);
    if (status < 0 || write_status < 0)
        return -1;
    return WIFEXITED(status) && WEXITSTATUS(status) == 0 ? 0 : -1;
}

static int copy_with_native_helper(const char *text, size_t text_len)
{
    /* pbcopy is also available on some non-macOS systems, so probe PATH everywhere. */
    {
        const char *argv[] = {"pbcopy", NULL};
        if (run_copy_helper(argv, text, text_len) == 0)
            return 0;
    }
    /* Prefer the Wayland clipboard over the potentially stale XWayland selection. */
    if (getenv("WAYLAND_DISPLAY")) {
        const char *argv[] = {"wl-copy", NULL};
        if (run_copy_helper(argv, text, text_len) == 0)
            return 0;
    }
    {
        const char *argv[] = {"xclip", "-selection", "clipboard", NULL};
        if (run_copy_helper(argv, text, text_len) == 0)
            return 0;
    }
    {
        const char *argv[] = {"xsel", "-b", "-i", NULL};
        if (run_copy_helper(argv, text, text_len) == 0)
            return 0;
    }
    return -1;
}

static int copy_with_osc52(const char *text, size_t text_len)
{
    int tmux_wrap = getenv("TMUX") != NULL;
    size_t sequence_len;
    char *sequence = clipboard_osc52_sequence(text, text_len, tmux_wrap, &sequence_len);
    if (!sequence)
        return -1;

    /* Write to the terminal even when stdout is redirected. */
    int fd = open("/dev/tty", O_WRONLY | O_NOCTTY);
    int owns_fd = fd >= 0;
    if (!owns_fd)
        fd = STDOUT_FILENO;
    int result = fd_write_all(fd, sequence, sequence_len);
    if (owns_fd)
        close(fd);
    free(sequence);
    return result;
}

static int is_ssh_session(void)
{
    return getenv("SSH_TTY") != NULL || getenv("SSH_CONNECTION") != NULL;
}

int clipboard_copy(const char *text, size_t text_len, const char **error)
{
    if (is_ssh_session()) {
        if (copy_with_osc52(text, text_len) == 0)
            return 0;
        if (error) {
            *error = text_len > CLIPBOARD_OSC52_MAX_BYTES
                         ? "response too large for OSC 52 over SSH"
                         : "terminal did not accept OSC 52 sequence";
        }
        return -1;
    }
    if (copy_with_native_helper(text, text_len) == 0)
        return 0;
    if (copy_with_osc52(text, text_len) == 0)
        return 0;
    if (error)
        *error =
            "no clipboard helper available "
            "(install pbcopy / wl-copy / xclip / xsel, or use a terminal that supports OSC 52)";
    return -1;
}
