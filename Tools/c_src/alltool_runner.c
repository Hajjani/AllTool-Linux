#define _GNU_SOURCE
#include "alltool_shm.h"
#include "alltool_compiler.h"
#include "alltool_sudo.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <signal.h>
#include <semaphore.h>
#include <pwd.h>
#include <limits.h>

static void get_config_path(char *buf, size_t bufsz) {
    const char *home = getenv("HOME");
    if (!home || !*home) {
        struct passwd *pw = getpwuid(getuid());
        if (pw && pw->pw_dir) home = pw->pw_dir;
    }
    if (!home) home = "/tmp";
    snprintf(buf, bufsz, "%s/.config/alltool/.confs.json", home);
}

static void get_cache_dir(char *buf, size_t bufsz) {
    const char *home = getenv("HOME");
    if (!home || !*home) {
        struct passwd *pw = getpwuid(getuid());
        if (pw && pw->pw_dir) home = pw->pw_dir;
    }
    if (!home) home = "/tmp";
    snprintf(buf, bufsz, "%s/.config/alltool/cache", home);
}



int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <command> [args...]\n", argv[0]);
        return 1;
    }

    size_t shm_size = sizeof(alltool_shm_t) + sizeof(sem_t);
    alltool_shm_init(ALLTOOL_SHM_NAME, shm_size);

    if (strcmp(argv[1], "run") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: %s run <script> [-t]\n", argv[0]);
            return 1;
        }

        bool temp_mode = false;
        for (int i = 3; i < argc; i++) {
            if (strcmp(argv[i], "-t") == 0) temp_mode = true;
        }

        alltool_compile_opts_t opts = {
            .source_path = argv[2],
            .output_path = NULL,
            .cache_dir = NULL,
            .temp_mode = temp_mode,
            .compiler_flags = "-O2 -pipe",
            .lang = alltool_detect_language(argv[2])
        };
        char cache_dir_buf[PATH_MAX];
        get_cache_dir(cache_dir_buf, sizeof(cache_dir_buf));
        opts.cache_dir = cache_dir_buf;

        if (opts.lang == ALLTOOL_LANG_UNKNOWN) {
            char *args[argc - 2];
            args[0] = argv[2];
            for (int i = 3; i < argc; i++) args[i-2] = argv[i];
            args[argc-2] = NULL;
            execvp(argv[2], args);
            perror("execvp");
            return 127;
        }

        alltool_compile_result_t result;
        int ret = alltool_compile_and_run(&opts, &result);
        if (result.error_message) {
            fprintf(stderr, "%s\n", result.error_message);
        }
        printf("Compile time: %.2f ms, Exec time: %.2f ms\n", result.compile_time_ms, result.exec_time_ms);
        alltool_free_result(&result);
        return ret;
    }

    if (strcmp(argv[1], "sudo-cache") == 0) {
        char *username = NULL, *password = NULL;
        char config_path[PATH_MAX];
        get_config_path(config_path, sizeof(config_path));
        /* Username is resolved from `.confs.json` first — the config file
         * is the single source of truth; $USER is only a fallback. */
        if (alltool_sudo_prompt_credentials_conf("Enter sudo password to cache", config_path, &username, &password) == 0) {
            printf("Cache password for future use? (y/N): ");
            fflush(stdout);
            char response[16];
            if (fgets(response, sizeof(response), stdin) && (response[0] == 'y' || response[0] == 'Y')) {
                alltool_sudo_cache_credentials(config_path, username, password);
                printf("Credentials cached securely.\n");
            }
            free(username);
            free(password);
        }
        return 0;
    }

    if (strcmp(argv[1], "sudo-clear") == 0) {
        char config_path[PATH_MAX];
        get_config_path(config_path, sizeof(config_path));
        alltool_sudo_clear_cache(config_path);
        printf("Sudo cache cleared.\n");
        return 0;
    }

    fprintf(stderr, "Unknown command: %s\n", argv[1]);
    return 1;
}