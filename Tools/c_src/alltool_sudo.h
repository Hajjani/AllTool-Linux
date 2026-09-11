#ifndef ALLTOOL_SUDO_H
#define ALLTOOL_SUDO_H

#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    char *username;
    char *encrypted_password;
    char *salt;
    bool cached;
} alltool_sudo_creds_t;

int alltool_sudo_prompt_credentials(const char *prompt, char **username, char **password);
int alltool_sudo_encrypt_password(const char *password, const char *salt, char **encrypted);
int alltool_sudo_decrypt_password(const char *encrypted, const char *salt, const char *password, char **decrypted);
int alltool_sudo_verify_password(const char *encrypted, const char *salt, const char *password);
int alltool_sudo_generate_salt(char **salt);
int alltool_sudo_run_with_creds(const char *username, const char *password, const char *command, char **output);
int alltool_sudo_cache_credentials(const char *config_path, const char *username, const char *password);
int alltool_sudo_load_credentials(const char *config_path, alltool_sudo_creds_t *creds);
void alltool_sudo_free_creds(alltool_sudo_creds_t *creds);
int alltool_sudo_clear_cache(const char *config_path);

#ifdef __cplusplus
}
#endif

#endif