#define _GNU_SOURCE
#include "alltool_compiler.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <time.h>
#include <errno.h>
#include <libgen.h>

static alltool_lang_t detect_by_extension(const char *filename) {
    const char *ext = strrchr(filename, '.');
    if (!ext) return ALLTOOL_LANG_UNKNOWN;

    if (strcmp(ext, ".c") == 0) return ALLTOOL_LANG_C;
    if (strcmp(ext, ".cpp") == 0 || strcmp(ext, ".cc") == 0 || strcmp(ext, ".cxx") == 0) return ALLTOOL_LANG_CPP;
    if (strcmp(ext, ".rs") == 0) return ALLTOOL_LANG_RUST;
    if (strcmp(ext, ".go") == 0) return ALLTOOL_LANG_GO;
    if (strcmp(ext, ".zig") == 0) return ALLTOOL_LANG_ZIG;

    return ALLTOOL_LANG_UNKNOWN;
}

alltool_lang_t alltool_detect_language(const char *filename) {
    return detect_by_extension(filename);
}

const char *alltool_lang_to_string(alltool_lang_t lang) {
    switch (lang) {
        case ALLTOOL_LANG_C: return "c";
        case ALLTOOL_LANG_CPP: return "cpp";
        case ALLTOOL_LANG_RUST: return "rust";
        case ALLTOOL_LANG_GO: return "go";
        case ALLTOOL_LANG_ZIG: return "zig";
        default: return "unknown";
    }
}

const char *alltool_get_compiler(alltool_lang_t lang) {
    switch (lang) {
        case ALLTOOL_LANG_C: return "gcc";
        case ALLTOOL_LANG_CPP: return "g++";
        case ALLTOOL_LANG_RUST: return "rustc";
        case ALLTOOL_LANG_GO: return "go";
        case ALLTOOL_LANG_ZIG: return "zig";
        default: return NULL;
    }
}

static char *compute_source_hash(const char *source_path) {
    struct stat st;
    if (stat(source_path, &st) != 0) return NULL;

    char *hash = malloc(32);
    snprintf(hash, 32, "%lx%lx", st.st_mtime, st.st_size);
    return hash;
}

char *alltool_get_cache_path(const char *source_path, const char *cache_dir) {
    if (!source_path || !cache_dir) return NULL;
    char *hash = compute_source_hash(source_path);
    if (!hash) return NULL;

    size_t need = strlen(cache_dir) + strlen(hash) + 32;
    char *cache_path = malloc(need);
    if (!cache_path) { free(hash); return NULL; }
    int n = snprintf(cache_path, need, "%s/%s", cache_dir, hash);
    free(hash);
    if (n < 0 || (size_t)n >= need) { free(cache_path); return NULL; }
    return cache_path;
}

/* exec without a shell: no globbing, no $/`/`;` expansion. Filenames with
 * spaces, quotes or semicolons become inert argv entries. */
static int run_argv(char *const argv[], char **output) {
    int out_pipe[2] = { -1, -1 };
    if (pipe(out_pipe) < 0) return -1;
    pid_t pid = fork();
    if (pid < 0) {
        close(out_pipe[0]); close(out_pipe[1]);
        return -1;
    }
    if (pid == 0) {
        close(out_pipe[0]);
        dup2(out_pipe[1], STDOUT_FILENO);
        dup2(out_pipe[1], STDERR_FILENO);
        close(out_pipe[1]);
        execvp(argv[0], argv);
        _exit(127);
    }
    close(out_pipe[1]);
    char buffer[4096];
    size_t total = 0;
    size_t capacity = 4096;
    char *result = malloc(capacity);
    if (!result) {
        close(out_pipe[0]);
        int st; waitpid(pid, &st, 0);
        return -1;
    }
    ssize_t n;
    while ((n = read(out_pipe[0], buffer, sizeof(buffer))) > 0) {
        if (total + (size_t)n + 1 >= capacity) {
            capacity *= 2;
            char *nr = realloc(result, capacity);
            if (!nr) { free(result); close(out_pipe[0]); int st; waitpid(pid, &st, 0); return -1; }
            result = nr;
        }
        memcpy(result + total, buffer, (size_t)n);
        total += (size_t)n;
    }
    close(out_pipe[0]);
    int status = 0;
    waitpid(pid, &status, 0);
    result[total] = '\0';
    *output = result;
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    return -1;
}

int alltool_compile_and_run(const alltool_compile_opts_t *opts, alltool_compile_result_t *result) {
    if (!opts || !result) return -1;

    memset(result, 0, sizeof(alltool_compile_result_t));

    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);

    char *cache_path = NULL;
    if (!opts->temp_mode && opts->cache_dir) {
        cache_path = alltool_get_cache_path(opts->source_path, opts->cache_dir);
    }

    const char *compiler = alltool_get_compiler(opts->lang);
    if (!compiler) {
        result->error_message = strdup("Unknown language");
        return -1;
    }

    const char *output = opts->output_path;
    int output_owned = 0;
    if (!output && cache_path) {
        output = cache_path;
    } else if (!output) {
        char *tmp = strdup(opts->source_path);
        if (!tmp) { if (cache_path) free(cache_path); return -1; }
        char *base = basename(tmp);
        char *dot = strrchr(base, '.');
        if (dot) *dot = '\0';
        size_t need = strlen("/tmp/alltool_") + strlen(base) + 1;
        char *buf = malloc(need);
        if (!buf) { free(tmp); if (cache_path) free(cache_path); return -1; }
        int n = snprintf(buf, need, "/tmp/alltool_%s", base);
        free(tmp);
        if (n < 0 || (size_t)n >= need) { free(buf); if (cache_path) free(cache_path); return -1; }
        output = buf;
        output_owned = 1;
    }

    // Build argv without a shell. Flags are split on whitespace (no quote
    // handling — matches previous simple behavior but without injection).
    char *flags_copy = NULL;
    const char *flags = opts->compiler_flags ? opts->compiler_flags : "-O2 -pipe";
    // Count flag words.
    size_t nflags = 0;
    {
        char *t = strdup(flags);
        if (!t) { if (output_owned) free((void*)output); if (cache_path) free(cache_path); return -1; }
        char *save = NULL;
        for (char *tok = strtok_r(t, " \t\r\n", &save); tok; tok = strtok_r(NULL, " \t\r\n", &save))
            nflags++;
        free(t);
    }
    size_t max_argv = nflags + 8;
    char **cargv = calloc(max_argv, sizeof(char *));
    if (!cargv) { if (output_owned) free((void*)output); if (cache_path) free(cache_path); return -1; }
    flags_copy = strdup(flags);
    if (!flags_copy) { free(cargv); if (output_owned) free((void*)output); if (cache_path) free(cache_path); return -1; }
    size_t ai = 0;
    int use_flags = 1;
    switch (opts->lang) {
        case ALLTOOL_LANG_C:
        case ALLTOOL_LANG_CPP:
        case ALLTOOL_LANG_RUST:
            cargv[ai++] = (char *)compiler;
            {
                char *save = NULL;
                for (char *tok = strtok_r(flags_copy, " \t\r\n", &save); tok; tok = strtok_r(NULL, " \t\r\n", &save))
                    cargv[ai++] = tok;
            }
            cargv[ai++] = "-o";
            cargv[ai++] = (char *)output;
            cargv[ai++] = (char *)opts->source_path;
            break;
        case ALLTOOL_LANG_GO:
            use_flags = 0;
            cargv[ai++] = (char *)compiler;
            cargv[ai++] = "build";
            cargv[ai++] = "-o";
            cargv[ai++] = (char *)output;
            cargv[ai++] = (char *)opts->source_path;
            break;
        case ALLTOOL_LANG_ZIG:
            use_flags = 0;
            cargv[ai++] = (char *)compiler;
            cargv[ai++] = "build-exe";
            cargv[ai++] = (char *)opts->source_path;
            cargv[ai++] = "-o";
            cargv[ai++] = (char *)output;
            break;
        default:
            result->error_message = strdup("Unsupported language");
            free(flags_copy); free(cargv);
            if (output_owned) free((void*)output);
            if (cache_path) free(cache_path);
            return -1;
    }
    (void)use_flags;
    cargv[ai] = NULL;

    char *compile_output = NULL;
    int compile_status = run_argv(cargv, &compile_output);
    free(flags_copy);
    free(cargv);
    clock_gettime(CLOCK_MONOTONIC, &end);
    result->compile_time_ms = (end.tv_sec - start.tv_sec) * 1000.0 + (end.tv_nsec - start.tv_nsec) / 1e6;

    if (compile_status != 0) {
        result->exit_code = compile_status;
        result->error_message = compile_output ? compile_output : strdup("Compilation failed");
        if (output_owned) free((void*)output);
        if (cache_path) free(cache_path);
        return compile_status;
    }

    if (compile_output) free(compile_output);
    result->output_path = strdup(output);

    clock_gettime(CLOCK_MONOTONIC, &start);
    char *run_argv_list[2] = { (char *)output, NULL };
    char *run_output = NULL;
    int run_status = run_argv(run_argv_list, &run_output);
    clock_gettime(CLOCK_MONOTONIC, &end);
    result->exec_time_ms = (end.tv_sec - start.tv_sec) * 1000.0 + (end.tv_nsec - start.tv_nsec) / 1e6;

    result->exit_code = run_status;
    if (run_output) {
        if (run_status != 0) {
            result->error_message = run_output;
        } else {
            result->exec_output = run_output;
        }
    }

    if (output_owned) free((void*)output);
    if (cache_path) free(cache_path);
    return run_status;
}

void alltool_free_result(alltool_compile_result_t *result) {
    if (!result) return;
    free(result->output_path);
    free(result->error_message);
    free(result->exec_output);
    result->output_path = NULL;
    result->error_message = NULL;
    result->exec_output = NULL;
}