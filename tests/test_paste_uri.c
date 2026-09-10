/* SPDX-License-Identifier: MIT */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>

#include "harness.h"
#include "xalloc.h"
#include "terminal/paste_uri.h"

static void test_uris_plain_file(void)
{
    char *out = paste_uri_list_to_paths("file:///etc/hostname");
    EXPECT(out != NULL);
    EXPECT_STR_EQ(out, "/etc/hostname ");
    free(out);
}

static void test_uris_percent_decode_and_localhost(void)
{
    char *out = paste_uri_list_to_paths("file://localhost/a%20dir/b%2Bc.txt");
    EXPECT(out != NULL);
    EXPECT_STR_EQ(out, "/a dir/b+c.txt ");
    free(out);
}

static void test_uris_image_extension_gets_marker_without_file_access(void)
{
    char *out = paste_uri_list_to_paths("file:///no/such/dir/pic.PNG");
    EXPECT(out != NULL);
    EXPECT_STR_EQ(out, "[pasted image: /no/such/dir/pic.PNG] ");
    free(out);
}

static void test_uris_multiple_lines(void)
{
    char *out = paste_uri_list_to_paths("file:///a\nfile:///b\n");
    EXPECT(out != NULL);
    EXPECT_STR_EQ(out, "/a\n/b ");
    free(out);
}

static void test_uris_fifo_is_not_opened(void)
{
    char *dir = t_tempdir();
    char *fifo = xasprintf("%s/fifo", dir);
    if (mkfifo(fifo, 0600) == 0) {
        char *uri = xasprintf("file://%s", fifo);
        char *out = paste_uri_list_to_paths(uri);
        EXPECT(out != NULL);
        char *want = xasprintf("%s ", fifo);
        EXPECT_STR_EQ(out, want);
        free(want);
        free(out);
        free(uri);
    }
    free(fifo);
}

static void test_uris_reject_non_uri_text(void)
{
    EXPECT(paste_uri_list_to_paths("hello world") == NULL);
    EXPECT(paste_uri_list_to_paths("file:///a\nnot a uri") == NULL);
    EXPECT(paste_uri_list_to_paths("https://example.com/x.png") == NULL);
    EXPECT(paste_uri_list_to_paths("file://remotehost/share/x") == NULL);
    EXPECT(paste_uri_list_to_paths("file://") == NULL);
    EXPECT(paste_uri_list_to_paths("") == NULL);
    EXPECT(paste_uri_list_to_paths("file:///tmp/a%00.png") == NULL);
}

int main(void)
{
    test_uris_plain_file();
    test_uris_percent_decode_and_localhost();
    test_uris_image_extension_gets_marker_without_file_access();
    test_uris_multiple_lines();
    test_uris_fifo_is_not_opened();
    test_uris_reject_non_uri_text();

    T_REPORT();
}
