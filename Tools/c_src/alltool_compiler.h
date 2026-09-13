#ifndef ALLTOOL_COMPILER_H
#define ALLTOOL_COMPILER_H

#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    ALLTOOL_LANG_C = 0,
    ALLTOOL_LANG_CPP = 1,
    ALLTOOL_LANG_RUST = 2,
    ALLTOOL_LANG_GO = 3,
    ALLTOOL_LANG_ZIG = 4,
    ALLTOOL_LANG_UNKNOWN = 255
} alltool_lang_t;

typedef struct {
    const char *source_path;
    const char *output_path;
    const char *cache_dir;
    bool temp_mode;
    const char *compiler_flags;
    alltool_lang_t lang;
} alltool_compile_opts_t;

typedef struct {
    int exit_code;
    char *output_path;
    char *error_message;
    char *exec_output;
    double compile_time_ms;
    double exec_time_ms;
} alltool_compile_result_t;

alltool_lang_t alltool_detect_language(const char *filename);
const char *alltool_lang_to_string(alltool_lang_t lang);
const char *alltool_get_compiler(alltool_lang_t lang);
int alltool_compile_and_run(const alltool_compile_opts_t *opts, alltool_compile_result_t *result);
void alltool_free_result(alltool_compile_result_t *result);
char *alltool_get_cache_path(const char *source_path, const char *cache_dir);

#ifdef __cplusplus
}
#endif

#endif