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

#define CONFIG_PATH "/home/debian/.config/alltool/.confs.json"

typedef struct {
    char *name;
    char *command;
    char **args;
    int argc;
    bool needs_sudo;
    int32_t predecessor_idx;
} alltool_process_t;

static int run_process_chain(alltool_process_t *processes, int count) {
    alltool_chain_ctx_t ctx;
    if (alltool_shm_attach(ALLTOOL_SHM_NAME, &ctx) != 0) {
        fprintf(stderr, "Failed to attach to shared memory\n");
        return -1;
    }

    for (int i = 0; i < count; i++) {
        pid_t pid = fork();
        if (pid < 0) {
            perror("fork");
            alltool_shm_detach(&ctx);
            return -1;
        }

        if (pid == 0) {
            alltool_chain_ctx_t child_ctx;
            if (alltool_shm_attach(ALLTOOL_SHM_NAME, &child_ctx) != 0) {
                _exit(1);
            }

            alltool_shm_register_process(&child_ctx, getpid(), processes[i].predecessor_idx);

            if (processes[i].predecessor_idx >= 0) {
                if (alltool_shm_wait_predecessor(&child_ctx, -1) != 0) {
                    alltool_shm_mark_done(&child_ctx, -1);
                    alltool_shm_detach(&child_ctx);
                    _exit(1);
                }
            }

            if (processes[i].needs_sudo) {
                alltool_sudo_creds_t creds;
                if (alltool_sudo_load_credentials(CONFIG_PATH, &creds) == 0) {
                    char *output = NULL;
                    char full_cmd[2048];
                    snprintf(full_cmd, sizeof(full_cmd), "%s", processes[i].command);
                    for (int j = 0; j < processes[i].argc; j++) {
                        strncat(full_cmd, " ", sizeof(full_cmd) - strlen(full_cmd) - 1);
                        strncat(full_cmd, processes[i].args[j], sizeof(full_cmd) - strlen(full_cmd) - 1);
                    }
                    int ret = alltool_sudo_run_with_creds(creds.username, creds.encrypted_password, full_cmd, &output);
                    alltool_sudo_free_creds(&creds);
                    if (output) free(output);
                    alltool_shm_mark_done(&child_ctx, ret);
                    alltool_shm_detach(&child_ctx);
                    _exit(ret);
                }
            } else {
                execvp(processes[i].command, (char *const *)processes[i].args);
                perror("execvp");
                alltool_shm_mark_done(&child_ctx, -1);
                alltool_shm_detach(&child_ctx);
                _exit(127);
            }
        }

        alltool_shm_register_process(&ctx, pid, processes[i].predecessor_idx);
    }

    for (int i = 0; i < count; i++) {
        int status;
        wait(&status);
    }

    alltool_shm_detach(&ctx);
    return 0;
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
            .cache_dir = "/home/debian/.config/alltool/cache",
            .temp_mode = temp_mode,
            .compiler_flags = "-O2 -pipe",
            .lang = alltool_detect_language(argv[2])
        };

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
        if (alltool_sudo_prompt_credentials("Enter sudo password to cache", &username, &password) == 0) {
            printf("Cache password for future use? (y/N): ");
            fflush(stdout);
            char response[16];
            if (fgets(response, sizeof(response), stdin) && (response[0] == 'y' || response[0] == 'Y')) {
                alltool_sudo_cache_credentials(CONFIG_PATH, username, password);
                printf("Credentials cached securely.\n");
            }
            free(username);
            free(password);
        }
        return 0;
    }

    if (strcmp(argv[1], "sudo-clear") == 0) {
        alltool_sudo_clear_cache(CONFIG_PATH);
        printf("Sudo cache cleared.\n");
        return 0;
    }

    fprintf(stderr, "Unknown command: %s\n", argv[1]);
    return 1;
}