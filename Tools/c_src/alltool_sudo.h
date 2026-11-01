#ifndef ALLTOOL_SUDO_H
#define ALLTOOL_SUDO_H

#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Credential-record schemes stored in `.confs.json`.
 *
 * v1 (legacy; old installs get upgraded in place): salted
 *   repeating-key XOR -> "encrypted_password".
 * v2 (current): ChaCha20(password) under the key
 *   dk = PBKDF2-HMAC-SHA256(record_key, salt || username, iters, 64)
 * using a fresh random 32-byte `record_key` and 32-byte salt, plus an
 * HMAC-SHA256 tag over domain || username || nonce || ciphertext. The
 * record is therefore cryptographically bound to its owner's username
 * AND integrity-checked: a renamed user cannot reuse another user's
 * blob (tag failure -> self-heal), and edited blobs fail the tag.
 */
#define ALLTOOL_SUDO_SCHEME_V1 "v1"
#define ALLTOOL_SUDO_SCHEME_V2 "v2"
/* Defaults for newly cached records (override stored per record). */
#define ALLTOOL_SUDO_DEFAULT_ITERS 200000u

typedef struct {
    char *username;
    char *encrypted_password;
    char *salt;
    char *scheme;     /* NULL when absent in file -> treated as v1 */
    char *nonce;      /* v2 */
    char *auth_tag;   /* v2 */
    char *record_key; /* v2 (hex keystore of 32 bytes) */
    unsigned int iterations; /* v2; 0 when absent */
    bool cached;
} alltool_sudo_creds_t;

/* Prompt for (username, password). With `config_path != NULL`, the
 * username is resolved from `.confs.json` itself (sudo block, then the
 * top-level "username"), falling back to $USER — the config file is the
 * single source of truth for identity. Otherwise legacy $USER logic. */
int alltool_sudo_prompt_credentials(const char *prompt, char **username, char **password);
int alltool_sudo_prompt_credentials_conf(const char *prompt, const char *config_path,
                                         char **username, char **password);

/* v1 (legacy, kept ONLY for reading old records / verification). */
int alltool_sudo_encrypt_password(const char *password, const char *salt, char **encrypted);
int alltool_sudo_decrypt_password(const char *encrypted, const char *salt, const char *password, char **decrypted);
int alltool_sudo_verify_password(const char *encrypted, const char *salt, const char *password);
int alltool_sudo_generate_salt(char **salt);

/* v2 encryption bound to `username`. iteration_count 0 uses the default.
 * Outputs (malloc'd hex strings): salt(32B), nonce(12B), ct, HMAC tag,
 * plus the record_key (32B) that must be persisted alongside them. */
int alltool_sudo_encrypt_password_v2(const char *password, const char *username,
                                     unsigned int iterations,
                                     char **salt_out, char **nonce_out,
                                     char **record_key_out,
                                     char **encrypted_out, char **tag_out);
/* Verify the tag, then decrypt. `record_key` is the persisted 32-byte
 * hex keystore value. Fails (non-zero) on tag mismatch or bad inputs. */
int alltool_sudo_decrypt_password_v2(const char *encrypted, const char *salt,
                                     const char *nonce, const char *tag,
                                     unsigned int iterations, const char *username,
                                     const char *record_key_hex,
                                     char **password_out);

/* ---- generic entry points (single source of truth: .confs.json) ---- */
int alltool_sudo_run_with_creds(const char *username, const char *password, const char *command, char **output);
int alltool_sudo_cache_credentials(const char *config_path, const char *username, const char *password);
int alltool_sudo_load_credentials(const char *config_path, alltool_sudo_creds_t *creds);
void alltool_sudo_free_creds(alltool_sudo_creds_t *creds);
int alltool_sudo_clear_cache(const char *config_path);

/* Load the credentials record from `.confs.json`, verify/decrypt it
 * (v1 or v2 transparently), run `sudo <command>` with the recovered
 * password, wipe it, and — when the record was legacy v1 and the run
 * succeeded — transparently rewrite the record as v2. */
int alltool_sudo_run_cached(const char *config_path, const char *command, char **output);

#ifdef __cplusplus
}
#endif

#endif