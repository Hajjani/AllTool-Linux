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
    char *hash = compute_source_hash(source_path);
    if (!hash) return NULL;

    char *cache_path = malloc(strlen(cache_dir) + strlen(hash) + 32);
    sprintf(cache_path, "%s/%s", cache_dir, hash);
    free(hash);
    return cache_path;
}

static int run_command(const char *cmd, char **output) {
    FILE *fp = popen(cmd, "r");
    if (!fp) return -1;

    char buffer[4096];
    size_t total = 0;
    size_t capacity = 4096;
    char *result = malloc(capacity);
    if (!result) {
        pclose(fp);
        return -1;
    }

    while (fgets(buffer, sizeof(buffer), fp)) {
        size_t len = strlen(buffer);
        if (total + len + 1 >= capacity) {
            capacity *= 2;
            char *new_result = realloc(result, capacity);
            if (!new_result) {
                free(result);
                pclose(fp);
                return -1;
            }
            result = new_result;
        }
        memcpy(result + total, buffer, len);
        total += len;
    }

    int status = pclose(fp);
    result[total] = '\0';
    *output = result;
    return WEXITSTATUS(status);
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
    if (!output && cache_path) {
        output = cache_path;
    } else if (!output) {
        char *tmp = strdup(opts->source_path);
        char *base = basename(tmp);
        char *dot = strrchr(base, '.');
        if (dot) *dot = '\0';
        output = malloc(strlen("/tmp/alltool_") + strlen(base) + 1);
        sprintf((char *)output, "/tmp/alltool_%s", base);
        free(tmp);
    }

    char cmd[4096];
    const char *flags = opts->compiler_flags ? opts->compiler_flags : "-O2 -pipe";

    switch (opts->lang) {
        case ALLTOOL_LANG_C:
            snprintf(cmd, sizeof(cmd), "%s %s -o %s %s", compiler, flags, output, opts->source_path);
            break;
        case ALLTOOL_LANG_CPP:
            snprintf(cmd, sizeof(cmd), "%s %s -o %s %s", compiler, flags, output, opts->source_path);
            break;
        case ALLTOOL_LANG_RUST:
            snprintf(cmd, sizeof(cmd), "%s %s -o %s %s", compiler, flags, output, opts->source_path);
            break;
        case ALLTOOL_LANG_GO:
            snprintf(cmd, sizeof(cmd), "%s build -o %s %s", compiler, output, opts->source_path);
            break;
        case ALLTOOL_LANG_ZIG:
            snprintf(cmd, sizeof(cmd), "%s build-exe %s -o %s", compiler, opts->source_path, output);
            break;
        default:
            result->error_message = strdup("Unsupported language");
            if (cache_path) free(cache_path);
            return -1;
    }

    char *compile_output = NULL;
    int compile_status = run_command(cmd, &compile_output);
    clock_gettime(CLOCK_MONOTONIC, &end);
    result->compile_time_ms = (end.tv_sec - start.tv_sec) * 1000.0 + (end.tv_nsec - start.tv_nsec) / 1e6;

    if (compile_status != 0) {
        result->exit_code = compile_status;
        result->error_message = compile_output ? compile_output : strdup("Compilation failed");
        if (cache_path) free(cache_path);
        return compile_status;
    }

    if (compile_output) free(compile_output);
    result->output_path = strdup(output);

    clock_gettime(CLOCK_MONOTONIC, &start);
    char run_cmd[1024];
    snprintf(run_cmd, sizeof(run_cmd), "%s", output);
    char *run_output = NULL;
    int run_status = run_command(run_cmd, &run_output);
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