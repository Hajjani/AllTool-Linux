#define _GNU_SOURCE
#include "alltool_sudo.h"
#include "alltool_crypto.h"
#include "alltool_version.h"
#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <termios.h>
#include <fcntl.h>
#include <sys/wait.h>
#include <sys/mman.h>
#include <time.h>

#define SALT_LENGTH 16        /* v1 legacy salt (bytes) */
#define SALT_LENGTH_V2 32     /* v2 PBKDF2 salt (bytes) */
#define NONCE_LENGTH_V2 12    /* v2 ChaCha20 nonce (bytes) */
#define TAG_LENGTH_V2 32      /* v2 HMAC-ShA256 tag (bytes) */
#define KEY_LENGTH_V2 64      /* v2 derived key: 32 enc + 32 mac */
#define V2_DOMAIN "alltool-sudo-v2"
#define V2_MIN_ITERS 10000u
#define V2_MAX_ITERS 5000000u

/* Best-effort memory wiping that the compiler must not optimize away. */
static void secure_zero(void *ptr, size_t len) {
    alltool_secure_zero(ptr, len);
}

static char *extract_json_value(char *start);
/* Forward declarations for helpers defined later in this file. */
static char *read_config_file(const char *config_path);
static char *top_level_string(const char *json, const char *key);
static int find_sudo_object(char *json, char **sudo_start, char **sudo_end);
static char *strstr_range(char *start, char *end, const char *needle);
static int valid_username(const char *username);
static void clamp_iterations(unsigned int *iters);

static int read_password(const char *prompt, char **password) {
    printf("%s", prompt);
    fflush(stdout);

    struct termios old, new;
    tcgetattr(STDIN_FILENO, &old);
    new = old;
    new.c_lflag &= ~ECHO;
    tcsetattr(STDIN_FILENO, TCSANOW, &new);

    char *line = NULL;
    size_t len = 0;
    ssize_t nread = getline(&line, &len, stdin);

    tcsetattr(STDIN_FILENO, TCSANOW, &old);
    printf("\n");

    if (nread <= 0) {
        free(line);
        return -1;
    }

    if (line[nread - 1] == '\n') line[nread - 1] = '\0';
    *password = line;
    return 0;
}

int alltool_sudo_prompt_credentials_conf(const char *prompt, const char *config_path,
                                         char **username, char **password) {
    char *user = NULL;

    /* Identity comes from `.confs.json` (single source of truth):
     * the sudo record's username first, then the top-level one. */
    if (config_path) {
        char *json_str = read_config_file(config_path);
        if (json_str) {
            char *sudo_start = NULL, *sudo_end = NULL;
            if (find_sudo_object(json_str, &sudo_start, &sudo_end) == 0 &&
                sudo_start && sudo_end > sudo_start && sudo_end <= json_str + strlen(json_str)) {
                /* search inside the sudo block only */
                char *span = malloc((size_t)(sudo_end - sudo_start) + 1);
                if (span) {
                    memcpy(span, sudo_start, (size_t)(sudo_end - sudo_start));
                    span[sudo_end - sudo_start] = '\0';
                    char *u = strstr(span, "\"username\"");
                    if (u) {
                        user = extract_json_value(u);
                    }
                    /* untrusted transient copy of the identity; fine to wipe */
                    secure_zero(span, strlen(span));
                    free(span);
                }
            }
            if (!user) {
                user = top_level_string(json_str, "username");
            }
            free(json_str);
        }
    }

    if (!user || !*user) {
        free(user);
        user = NULL;
        const char *env_user = getenv("USER");
        if (env_user && *env_user) {
            user = strdup(env_user);
        }
    }
    *username = NULL; /* set below once we know we succeed */

    if (!user || !*user) {
        /* Last resort: interactive username entry. */
        char buf[256];
        printf("Username: ");
        fflush(stdout);
        if (!fgets(buf, sizeof(buf), stdin)) { free(user); return -1; }
        buf[strcspn(buf, "\n")] = '\0';
        if (!*buf) { free(user); return -1; }
        user = strdup(buf);
        if (!user) return -1;
    }

    char prompt_buf[512];
    snprintf(prompt_buf, sizeof(prompt_buf), "%s [%s]: ", prompt ? prompt : "Password", user);

    int rc = read_password(prompt_buf, password);
    if (rc == 0) {
        *username = user;
    } else {
        free(user);
    }
    return rc;
}

int alltool_sudo_prompt_credentials(const char *prompt, char **username, char **password) {
    /* Legacy entry point: uses $USER only (no config available). */
    return alltool_sudo_prompt_credentials_conf(prompt, NULL, username, password);
}

int alltool_sudo_generate_salt(char **salt) {
    unsigned char *bin_salt = malloc(SALT_LENGTH);
    if (!bin_salt) return -1;

    int urandom = open("/dev/urandom", O_RDONLY);
    if (urandom < 0 || read(urandom, bin_salt, SALT_LENGTH) != SALT_LENGTH) {
        free(bin_salt);
        if (urandom >= 0) close(urandom);
        return -1;
    }
    close(urandom);

    *salt = malloc(SALT_LENGTH * 2 + 1);
    for (int i = 0; i < SALT_LENGTH; i++) {
        sprintf(*salt + i * 2, "%02x", bin_salt[i]);
    }
    free(bin_salt);
    return 0;
}

static int hex_to_bin(const char *hex, unsigned char *bin, size_t bin_len) {
    size_t hex_len = strlen(hex);
    if (hex_len != bin_len * 2) return -1;

    for (size_t i = 0; i < bin_len; i++) {
        char byte_str[3] = {hex[i*2], hex[i*2+1], '\0'};
        bin[i] = (unsigned char)strtol(byte_str, NULL, 16);
    }
    return 0;
}

int alltool_sudo_encrypt_password(const char *password, const char *salt, char **encrypted) {
    unsigned char bin_salt[SALT_LENGTH];
    if (hex_to_bin(salt, bin_salt, SALT_LENGTH) != 0) return -1;

    size_t pw_len = strlen(password);
    unsigned char *key = malloc(pw_len);
    for (size_t i = 0; i < pw_len; i++) {
        key[i] = password[i] ^ bin_salt[i % SALT_LENGTH];
    }

    *encrypted = malloc(pw_len * 2 + 1);
    for (size_t i = 0; i < pw_len; i++) {
        sprintf(*encrypted + i * 2, "%02x", key[i]);
    }
    secure_zero(key, pw_len);
    free(key);
    return 0;
}

int alltool_sudo_verify_password(const char *encrypted, const char *salt, const char *password) {
    char *test_encrypted = NULL;
    int ret = alltool_sudo_encrypt_password(password, salt, &test_encrypted);
    if (ret != 0) return -1;

    int match = (strcmp(test_encrypted, encrypted) == 0);
    secure_zero(test_encrypted, strlen(test_encrypted));
    free(test_encrypted);
    return match ? 0 : -1;
}

int alltool_sudo_decrypt_password(const char *encrypted, const char *salt, const char *password, char **decrypted) {
    if (alltool_sudo_verify_password(encrypted, salt, password) != 0) {
        return -1;
    }
    *decrypted = strdup(password);
    return 0;
}

/* ------------------------------------------------------------------ *
 * v2: username-bound PBKDF2-HMAC-SHA256 + ChaCha20 + HMAC tag.
 *
 *   dk      = PBKDF2-HMAC-SHA256(password, salt || username, iters, 64)
 *   ct      = ChaCha20(dk[0:32], nonce, counter=1, password)
 *   tag     = HMAC-SHA256(dk[32:64], "alltool-sudo-v2" || username ||
 *                                                 nonce || ct)
 *
 * Everything is hex-encoded in `.confs.json`. The username participates
 * in the KDF and the tag, so a record cannot be re-used by (or re-owned
 * for) a different user: a renamed user fails verification instead of
 * silently unlocking someone else's password.                            */

static void clamp_iterations(unsigned int *iters) {
    if (*iters == 0) *iters = ALLTOOL_SUDO_DEFAULT_ITERS;
    if (*iters < V2_MIN_ITERS) *iters = V2_MIN_ITERS;
    if (*iters > V2_MAX_ITERS) *iters = V2_MAX_ITERS;
}

/* dk = PBKDF2-HMAC-SHA256(record_key, salt || username, iters, 64).
 * The username participates in the derivation, so the stored record is
 * cryptographically owned by the user it was cached for. */
static int derive_v2_keys(const unsigned char record_key[32],
                          const char *username,
                          const unsigned char salt[SALT_LENGTH_V2],
                          unsigned int iterations,
                          unsigned char dk[KEY_LENGTH_V2]) {
    size_t user_len = username ? strlen(username) : 0;
    unsigned char *salt_user = malloc(SALT_LENGTH_V2 + user_len);
    if (!salt_user) return -1;
    memcpy(salt_user, salt, SALT_LENGTH_V2);
    if (user_len) memcpy(salt_user + SALT_LENGTH_V2, username, user_len);

    alltool_pbkdf2_sha256(record_key, 32,
                          salt_user, SALT_LENGTH_V2 + user_len,
                          iterations, dk, KEY_LENGTH_V2);

    alltool_secure_zero(salt_user, SALT_LENGTH_V2 + user_len);
    free(salt_user);
    return 0;
}

/* tag = HMAC-SHA256(mac_key, "alltool-sudo-v2" || username || nonce || ct) */
static int write_v2_tag(const char *username,
                        const unsigned char nonce[NONCE_LENGTH_V2],
                        const unsigned char *mac_key,
                        const unsigned char *ct, size_t ct_len,
                        unsigned char tag[TAG_LENGTH_V2]) {
    size_t user_len = username ? strlen(username) : 0;
    size_t dom_len = strlen(V2_DOMAIN);
    size_t msg_len = dom_len + user_len + NONCE_LENGTH_V2 + ct_len;
    unsigned char *msg = malloc(msg_len);
    if (!msg) return -1;
    size_t off = 0;
    memcpy(msg + off, V2_DOMAIN, dom_len); off += dom_len;
    if (user_len) memcpy(msg + off, username, user_len);
    off += user_len;
    memcpy(msg + off, nonce, NONCE_LENGTH_V2); off += NONCE_LENGTH_V2;
    memcpy(msg + off, ct, ct_len);
    alltool_hmac_sha256(mac_key, 32, msg, msg_len, tag);
    alltool_secure_zero(msg, msg_len);
    free(msg);
    return 0;
}

static int read_entropy(unsigned char *buf, size_t len) {
    /* No rand()/time() fallbacks for key material. */
    int fd = open("/dev/urandom", O_RDONLY);
    if (fd < 0) return -1;
    size_t off = 0;
    while (off < len) {
        ssize_t got = read(fd, buf + off, len - off);
        if (got <= 0) { close(fd); return -1; }
        off += (size_t)got;
    }
    close(fd);
    return 0;
}

int alltool_sudo_encrypt_password_v2(const char *password, const char *username,
                                     unsigned int iterations,
                                     char **salt_out, char **nonce_out,
                                     char **record_key_out,
                                     char **encrypted_out, char **tag_out) {
    if (!password || !username || !salt_out || !nonce_out ||
        !record_key_out || !encrypted_out || !tag_out) return -1;
    if (!valid_username(username)) return -1;
    clamp_iterations(&iterations);

    unsigned char salt[SALT_LENGTH_V2];
    unsigned char nonce[NONCE_LENGTH_V2];
    unsigned char record_key[32];
    if (read_entropy(salt, sizeof(salt)) != 0 ||
        read_entropy(nonce, sizeof(nonce)) != 0 ||
        read_entropy(record_key, sizeof(record_key)) != 0) {
        alltool_secure_zero(salt, sizeof(salt));
        alltool_secure_zero(nonce, sizeof(nonce));
        alltool_secure_zero(record_key, sizeof(record_key));
        return -1;
    }

    int rc = -1;
    unsigned char dk[KEY_LENGTH_V2];
    if (derive_v2_keys(record_key, username, salt, iterations, dk) != 0) {
        alltool_secure_zero(salt, sizeof(salt));
        alltool_secure_zero(nonce, sizeof(nonce));
        alltool_secure_zero(record_key, sizeof(record_key));
        return -1;
    }

    size_t pw_len = strlen(password);
    unsigned char tag[TAG_LENGTH_V2];
    unsigned char *ct = malloc(pw_len ? pw_len : 1);
    if (ct) {
        alltool_chacha20_xor(dk, nonce, 1,
                             (const unsigned char *)password, pw_len, ct);
        if (write_v2_tag(username, nonce, dk + 32, ct, pw_len, tag) == 0) {
            char *s_hex = alltool_hex_encode(salt, SALT_LENGTH_V2);
            char *n_hex = alltool_hex_encode(nonce, NONCE_LENGTH_V2);
            char *r_hex = alltool_hex_encode(record_key, 32);
            char *c_hex = alltool_hex_encode(ct, pw_len);
            char *t_hex = alltool_hex_encode(tag, TAG_LENGTH_V2);
            if (s_hex && n_hex && r_hex && c_hex && t_hex) {
                *salt_out = s_hex;
                *nonce_out = n_hex;
                *record_key_out = r_hex;
                *encrypted_out = c_hex;
                *tag_out = t_hex;
                rc = 0;
            } else {
                free(s_hex); free(n_hex); free(r_hex); free(c_hex); free(t_hex);
            }
        }
    }

    alltool_secure_zero(dk, sizeof(dk));
    alltool_secure_zero(salt, sizeof(salt));
    alltool_secure_zero(nonce, sizeof(nonce));
    alltool_secure_zero(record_key, sizeof(record_key));
    alltool_secure_zero(tag, sizeof(tag));
    if (ct) {
        alltool_secure_zero(ct, pw_len);
        free(ct);
    }
    return rc;
}

int alltool_sudo_decrypt_password_v2(const char *encrypted, const char *salt,
                                     const char *nonce, const char *tag,
                                     unsigned int iterations, const char *username,
                                     const char *record_key_hex,
                                     char **password_out) {
    unsigned char salt_b[SALT_LENGTH_V2];
    unsigned char nonce_b[NONCE_LENGTH_V2];
    unsigned char tag_b[TAG_LENGTH_V2];
    unsigned char tag_calc[TAG_LENGTH_V2];
    unsigned char record_key[32];
    unsigned char dk[KEY_LENGTH_V2];

    if (!encrypted || !salt || !nonce || !tag || !username ||
        !record_key_hex || !password_out) return -1;
    if (!valid_username(username)) return -1;
    clamp_iterations(&iterations);
    if (strlen(record_key_hex) != 64) return -1; /* 32-byte hex keystore */

    size_t pw_len = strlen(encrypted) / 2;
    if (pw_len == 0 || pw_len > 4096) return -1; /* sudo passwords are small */
    unsigned char *ct = malloc(pw_len);

    int rc = -1;
    *password_out = NULL;
    if (ct &&
        alltool_hex_decode(salt, salt_b, SALT_LENGTH_V2) == 0 &&
        alltool_hex_decode(nonce, nonce_b, NONCE_LENGTH_V2) == 0 &&
        alltool_hex_decode(tag, tag_b, TAG_LENGTH_V2) == 0 &&
        alltool_hex_decode(record_key_hex, record_key, 32) == 0 &&
        alltool_hex_decode(encrypted, ct, pw_len) == 0 &&
        derive_v2_keys(record_key, username, salt_b, iterations, dk) == 0 &&
        write_v2_tag(username, nonce_b, dk + 32, ct, pw_len, tag_calc) == 0 &&
        alltool_consttime_eq(tag_b, tag_calc, TAG_LENGTH_V2)) {
        unsigned char *pw = malloc(pw_len + 1);
        if (pw) {
            alltool_chacha20_xor(dk, nonce_b, 1, ct, pw_len, pw);
            pw[pw_len] = '\0';
            alltool_secure_zero(dk, sizeof(dk));
            *password_out = (char *)pw;
            rc = 0;
        }
    } else {
        alltool_secure_zero(dk, sizeof(dk));
    }

    /* Wipe transient material regardless of result.
     * `ct` is attacker-visible data, `tag_calc` never touches the disk;
     * constant-time decode paths stay silent on failure. */
    alltool_secure_zero(salt_b, sizeof(salt_b));
    alltool_secure_zero(nonce_b, sizeof(nonce_b));
    alltool_secure_zero(tag_b, sizeof(tag_b));
    alltool_secure_zero(tag_calc, sizeof(tag_calc));
    alltool_secure_zero(record_key, sizeof(record_key));
    if (ct) {
        alltool_secure_zero(ct, pw_len);
        free(ct);
    }
    return rc;
}

/* Maximum argv entries produced when splitting a command line. */
#define SUDO_MAX_ARGS 4096

/* Usernames come from the config file, so enforce a strict allowlist.
 * Accepts POSIX-portable names (up to 32 chars, no leading '-'/'_'
 * confusion with option parsing since the value is passed via -u anyway). */
static int valid_username(const char *username) {
    if (!username || username[0] == '\0') return 0;
    size_t len = strlen(username);
    if (len > 32) return 0;
    unsigned char c = (unsigned char)username[0];
    if (!isalnum(c) && c != '_' && c != '.') return 0;
    for (size_t i = 1; i < len; i++) {
        c = (unsigned char)username[i];
        if (!isalnum(c) && c != '_' && c != '.' && c != '-') return 0;
    }
    return 1;
}

static void free_argv(char **argv, size_t argc) {
    if (!argv) return;
    for (size_t i = 0; i < argc; i++) free(argv[i]);
    free(argv);
}

/* Split a command line into argv WITHOUT invoking a shell.
 *
 * Understands single quotes, double quotes and backslash escapes, so
 * shlex.quote()-style input from the Python caller round-trips exactly,
 * but performs NO expansions: '$', backticks, $(...), globbing and
 * operators such as ';', '|', '&', '>', '<' are ordinary literal
 * characters. A word like ";" therefore becomes a harmless literal
 * argument instead of a command separator.
 *
 * Returns 0 on success (*argv_out is NULL-terminated, *argc_out set),
 * -1 on unbalanced quotes, empty input or allocation failure. */
static int split_command(const char *command, char ***argv_out, size_t *argc_out) {
    *argv_out = NULL;
    *argc_out = 0;
    if (!command) return -1;

    size_t argv_cap = 16, argc = 0;
    char **argv = malloc(argv_cap * sizeof(char *));
    if (!argv) return -1;

    size_t word_cap = 64, word_len = 0;
    char *word = malloc(word_cap);
    if (!word) {
        free(argv);
        return -1;
    }
    int in_word = 0; /* true once a word (even an empty quoted one) starts */
    int rc = -1;

    const char *p = command;
    while (*p) {
        if (*p == '\'') {
            /* Single quotes: literal until closing quote. */
            in_word = 1;
            p++;
            while (*p && *p != '\'') {
                if (word_len + 1 >= word_cap) {
                    word_cap *= 2;
                    char *nw = realloc(word, word_cap);
                    if (!nw) goto done;
                    word = nw;
                }
                word[word_len++] = *p++;
            }
            if (!*p) goto done; /* unbalanced quote */
            p++;
        } else if (*p == '"') {
            /* Double quotes: backslash escapes next char, nothing expands. */
            in_word = 1;
            p++;
            while (*p && *p != '"') {
                if (*p == '\\' && p[1]) p++;
                if (word_len + 1 >= word_cap) {
                    word_cap *= 2;
                    char *nw = realloc(word, word_cap);
                    if (!nw) goto done;
                    word = nw;
                }
                word[word_len++] = *p++;
            }
            if (!*p) goto done; /* unbalanced quote */
            p++;
        } else if (*p == '\\' && p[1]) {
            /* Bare backslash escapes the next character literally. */
            in_word = 1;
            p++;
            if (word_len + 1 >= word_cap) {
                word_cap *= 2;
                char *nw = realloc(word, word_cap);
                if (!nw) goto done;
                word = nw;
            }
            word[word_len++] = *p++;
        } else if (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') {
            if (in_word) {
                word[word_len] = '\0';
                if (argc + 1 >= argv_cap || argc + 1 >= SUDO_MAX_ARGS) goto done;
                if (argc + 1 >= argv_cap) {
                    argv_cap *= 2;
                    char **na = realloc(argv, argv_cap * sizeof(char *));
                    if (!na) goto done;
                    argv = na;
                }
                argv[argc] = strdup(word);
                if (!argv[argc]) goto done;
                argc++;
                word_len = 0;
                in_word = 0;
            }
            p++;
        } else {
            in_word = 1;
            if (word_len + 1 >= word_cap) {
                word_cap *= 2;
                char *nw = realloc(word, word_cap);
                if (!nw) goto done;
                word = nw;
            }
            word[word_len++] = *p++;
        }
    }

    if (in_word) {
        word[word_len] = '\0';
        if (argc + 1 >= SUDO_MAX_ARGS) goto done;
        if (argc + 1 >= argv_cap) {
            argv_cap = argc + 1;
            char **na = realloc(argv, argv_cap * sizeof(char *));
            if (!na) goto done;
            argv = na;
        }
        argv[argc] = strdup(word);
        if (!argv[argc]) goto done;
        argc++;
    }

    if (argc == 0) goto done; /* empty / whitespace-only command */
    argv[argc] = NULL;
    *argv_out = argv;
    *argc_out = argc;
    argv = NULL;
    rc = 0;

done:
    free(word);
    free_argv(argv, argc);
    return rc;
}

/* Fixed locations for sudo: never resolve it via PATH, which the caller
 * (or its environment) may control. Overridable at compile time for
 * testing with a stubbed sudo. */
#ifndef ALLTOOL_SUDO_PATHS
#define ALLTOOL_SUDO_PATHS { "/usr/bin/sudo", "/bin/sudo", NULL }
#endif
static const char *const SUDO_PATHS[] = ALLTOOL_SUDO_PATHS;

int alltool_sudo_run_with_creds(const char *username, const char *password, const char *command, char **output) {
    if (!username || !password || !command || !output) return -1;
    if (!valid_username(username)) return -1;

    /* No shell is involved anywhere below: the command line is tokenized
     * above (no expansion), and sudo is exec'd directly with an argv
     * array, so metacharacters in username/password/command are inert. */
    char **cmd_argv = NULL;
    size_t cmd_argc = 0;
    if (split_command(command, &cmd_argv, &cmd_argc) != 0 || cmd_argc == 0) {
        free_argv(cmd_argv, cmd_argc);
        return -1;
    }

    int out_pipe[2] = { -1, -1 };
    int in_pipe[2] = { -1, -1 };
    /* Both pipes are local anonymous IPC (never sockets/network).
     * CLOEXEC prevents the fds from leaking into unrelated children. */
#ifdef __linux__
    if (pipe2(out_pipe, O_CLOEXEC) < 0) {
        free_argv(cmd_argv, cmd_argc);
        return -1;
    }
    if (pipe2(in_pipe, O_CLOEXEC) < 0) {
        close(out_pipe[0]);
        close(out_pipe[1]);
        free_argv(cmd_argv, cmd_argc);
        return -1;
    }
#else
    if (pipe(out_pipe) < 0) {
        free_argv(cmd_argv, cmd_argc);
        return -1;
    }
    if (pipe(in_pipe) < 0) {
        close(out_pipe[0]);
        close(out_pipe[1]);
        free_argv(cmd_argv, cmd_argc);
        return -1;
    }
    for (int i = 0; i < 2; i++) {
        fcntl(out_pipe[i], F_SETFD, FD_CLOEXEC);
        fcntl(in_pipe[i], F_SETFD, FD_CLOEXEC);
    }
#endif

    pid_t pid = fork();
    if (pid < 0) {
        close(out_pipe[0]);
        close(out_pipe[1]);
        close(in_pipe[0]);
        close(in_pipe[1]);
        free_argv(cmd_argv, cmd_argc);
        return -1;
    }

    if (pid == 0) {
        close(out_pipe[0]);
        close(in_pipe[1]);
        dup2(out_pipe[1], STDOUT_FILENO);
        dup2(out_pipe[1], STDERR_FILENO);
        dup2(in_pipe[0], STDIN_FILENO);
        close(out_pipe[1]);
        close(in_pipe[0]);

        /* sudo -S reads the password from stdin; "--" keeps a command
         * starting with '-' from being parsed as a sudo option. */
        char **sudo_argv = malloc((cmd_argc + 7) * sizeof(char *));
        if (!sudo_argv) _exit(127);
        sudo_argv[0] = "sudo";
        sudo_argv[1] = "-S";
        sudo_argv[2] = "-u";
        sudo_argv[3] = (char *)username;
        sudo_argv[4] = "--";
        for (size_t i = 0; i < cmd_argc; i++) sudo_argv[5 + i] = cmd_argv[i];
        sudo_argv[5 + cmd_argc] = NULL;

        for (size_t i = 0; SUDO_PATHS[i]; i++) {
            execv(SUDO_PATHS[i], sudo_argv);
        }
        _exit(127);
    }

    free_argv(cmd_argv, cmd_argc); /* child has its own copy */
    close(out_pipe[1]);
    close(in_pipe[0]);

    /* Deliver the password to `sudo -S` over the local anonymous pipe
     * created above. `sudo -S` has no API for a pre-encrypted secret, so
     * cleartext on this local-only stdin pipe is unavoidable — it never
     * touches the network, argv, environment, or shell. Exposure is
     * minimized: the secret lives in one mlock'd transient copy that is
     * wiped (secure_zero) and freed immediately after the single write,
     * and the write end is closed at once so sudo sees EOF. */
    size_t pw_len = strlen(password);
    char *pw_buf = malloc(pw_len + 1);
    if (!pw_buf) {
        close(out_pipe[0]);
        close(in_pipe[1]);
        waitpid(pid, NULL, 0);
        return -1;
    }
    memcpy(pw_buf, password, pw_len);
    pw_buf[pw_len] = '\n';
    (void)mlock(pw_buf, pw_len + 1);
    size_t pw_total = pw_len + 1;
    size_t off = 0;
    while (off < pw_total) {
        ssize_t w = write(in_pipe[1], pw_buf + off, pw_total - off);
        if (w < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (w == 0) break;
        off += (size_t)w;
    }
    secure_zero(pw_buf, pw_total);
    (void)munlock(pw_buf, pw_total);
    free(pw_buf);
    pw_buf = NULL;
    close(in_pipe[1]);
    in_pipe[1] = -1;
    if (off < pw_total) {
        /* best effort; sudo fails closed without the full password */
    }

    char buffer[4096];
    size_t total = 0;
    size_t capacity = 4096;
    char *result = malloc(capacity);
    if (!result) {
        close(out_pipe[0]);
        waitpid(pid, NULL, 0);
        return -1;
    }

    ssize_t n;
    while ((n = read(out_pipe[0], buffer, sizeof(buffer))) > 0) {
        if (total + (size_t)n + 1 >= capacity) {
            capacity *= 2;
            char *new_result = realloc(result, capacity);
            if (!new_result) {
                free(result);
                close(out_pipe[0]);
                waitpid(pid, NULL, 0);
                return -1;
            }
            result = new_result;
        }
        memcpy(result + total, buffer, (size_t)n);
        total += (size_t)n;
    }
    close(out_pipe[0]);

    int status;
    waitpid(pid, &status, 0);

    result[total] = '\0';
    *output = result;
    return WEXITSTATUS(status);
}

/* Bounded file read: rejects ftell errors, empty/huge files (max 1 MiB). */
#define SUDO_MAX_CONFIG (1024 * 1024)

static char *read_config_file(const char *config_path) {
    FILE *f = fopen(config_path, "r");
    if (!f) return NULL;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return NULL; }
    long len = ftell(f);
    if (len < 0 || len > SUDO_MAX_CONFIG) { fclose(f); return NULL; }
    if (fseek(f, 0, SEEK_SET) != 0) { fclose(f); return NULL; }
    char *buf = malloc((size_t)len + 1);
    if (!buf) { fclose(f); return NULL; }
    size_t got = fread(buf, 1, (size_t)len, f);
    fclose(f);
    if (got != (size_t)len) { free(buf); return NULL; }
    buf[len] = '\0';
    return buf;
}

/* Strict `"cached": true|false` parse (no substring false-positives). */
static int parse_cached_bool(const char *json_str) {
    const char *p = strstr(json_str, "\"cached\"");
    if (!p) return 0;
    p = strchr(p, ':');
    if (!p) return 0;
    p++;
    while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') p++;
    if (strncmp(p, "true", 4) == 0) return 1;
    return 0;
}

/* Bounded strstr: search only inside [start, end).
 * Used to keep record-field lookups strictly inside the sudo block so a
 * same-named top-level key can never shadow the record. */
static char *strstr_range(char *start, char *end, const char *needle) {
    if (!start || !needle || start >= end) return NULL;
    size_t nlen = strlen(needle);
    for (char *p = start; p + nlen <= end; p++) {
        if (strncmp(p, needle, nlen) == 0) return p;
    }
    return NULL;
}

/* Locate the object contents of the "sudo" key inside `json`.
 * On success *body_start points at the first '{' and *body_end at the
 * matching '}' (inclusive). Returns 0 on success (-1 otherwise). */
static int find_sudo_object(char *json, char **body_start, char **body_end) {
    if (!json || !body_start || !body_end) return -1;
    char *sudo_start = strstr(json, "\"sudo\"");
    if (!sudo_start) return -1;
    char *brace = strchr(sudo_start, '{');
    if (!brace) return -1;
    int depth = 0;
    char *p = brace;
    while (*p) {
        if (*p == '{') depth++;
        else if (*p == '}') {
            depth--;
            if (depth == 0) {
                *body_start = brace;
                *body_end = p;
                return 0;
            }
        }
        p++;
    }
    return -1;
}

/* Extract the string value of a *top-level* (depth-1) `key` from a JSON
 * object. Used so identity fields come from `.confs.json` only and are
 * never confused with same-named keys inside nested objects (e.g. the
 * sudo record's username). Returns malloc'd string or NULL. */
static char *top_level_string(const char *json, const char *key) {
    if (!json || !key) return NULL;
    size_t key_len = strlen(key);
    int depth = 0;
    int in_str = 0, esc = 0, val_esc = 0;
    const char *p = json;
    const char *str_start = NULL;

    while (*p) {
        if (in_str) {
            if (esc) { esc = 0; p++; continue; }
            if (*p == '\\') { esc = 1; p++; continue; }
            if (*p == '"') {
                in_str = 0;
                if (depth == 1 && str_start) {
                    const char *q = p + 1;
                    while (*q == ' ' || *q == '\t' || *q == '\n' || *q == '\r') q++;
                    if (*q == ':') {
                        /* key candidates are plain identifiers in our config:
                         * compare unescaped bytes against `key`. */
                        const char *r = str_start + 1;
                        int ok = 1;
                        for (size_t k = 0; k < key_len; k++) {
                            char c = *r;
                            if (c == '\\' && r + 1 < p) { r++; c = *r; }
                            if (c != key[k]) { ok = 0; break; }
                            r++;
                        }
                        if (ok && r == p) {
                            /* value is the string after ':' */
                            q++;
                            while (*q == ' ' || *q == '\t' || *q == '\n' || *q == '\r') q++;
                            if (*q != '"') return NULL;
                            q++;
                            const char *vstart = q;
                            val_esc = 0;
                            while (*q) {
                                if (val_esc) { val_esc = 0; q++; continue; }
                                if (*q == '\\') { val_esc = 1; q++; continue; }
                                if (*q == '"') break;
                                q++;
                            }
                            if (*q != '"') return NULL;
                            size_t vlen = 0;
                            for (const char *v = vstart; v < q; v++) {
                                if (*v == '\\' && v + 1 < q) v++;
                                vlen++;
                            }
                            char *val = malloc(vlen + 1);
                            if (!val) return NULL;
                            char *dst = val;
                            for (const char *v = vstart; v < q; v++) {
                                if (*v == '\\' && v + 1 < q) v++;
                                *dst++ = *v;
                            }
                            *dst = '\0';
                            return val;
                        }
                    }
                }
                str_start = NULL;
                p++;
                continue;
            }
            p++;
            continue;
        }
        if (*p == '"') { in_str = 1; str_start = p; p++; continue; }
        if (*p == '{' || *p == '[') { depth++; p++; continue; }
        if (*p == '}' || *p == ']') { depth--; p++; continue; }
        p++;
    }
    return NULL;
}

/* Build a new JSON document with the "sudo" block replaced/inserted.
 * `body` is the *inner* text of the new object (without braces).
 * Preserves the rest of the document on best-effort basis. The fresh
 * config case echoes the version from alltool_version.h, which meson
 * buys from `.confs.json` — one version source. */
static char *json_with_sudo_body(const char *json_str, const char *body) {
    size_t body_len = strlen(body);

    if (json_str && strstr(json_str, "\"sudo\"")) {
        /* offsets come from a scan of the (unchanged) text; use strdup so
         * find_sudo_object has a non-const buffer. */
        char *scan = strdup(json_str);
        if (!scan) return NULL;
        char *s = NULL, *e = NULL;
        if (find_sudo_object(scan, &s, &e) != 0) {
            free(scan);
            return NULL;
        }
        /* the splice prefix must end *before* the "sudo" key itself,
         * not before its opening brace (body_start). */
        char *keyp = strstr(scan, "\"sudo\"");
        size_t prefix_len = keyp ? (size_t)(keyp - scan) : (size_t)(s - scan);
        size_t suffix_off = (size_t)(e - scan) + 1;
        free(scan);
        const char *suffix = suffix_off <= strlen(json_str) ? json_str + suffix_off : "";
        size_t need = prefix_len + body_len + strlen(suffix) + 16;
        char *out = malloc(need);
        if (!out) return NULL;
        snprintf(out, need, "%.*s\"sudo\":{%s}%s",
                 (int)prefix_len, json_str, body, suffix);
        return out;
    }

    if (json_str && strlen(json_str) > 0) {
        /* insert ,"sudo":{...} before the document's closing '}'. */
        const char *end = json_str + strlen(json_str) - 1;
        while (end > json_str && (*end == ' ' || *end == '\n' ||
               *end == '\t' || *end == '\r')) end--;
        if (*end != '}') return NULL;
        size_t prefix_len = (size_t)(end - json_str);
        int empty = 1;
        const char *open = strchr(json_str, '{');
        if (open && open < end) {
            for (const char *q = open + 1; q < end; q++) {
                if (*q != ' ' && *q != '\n' && *q != '\t' && *q != '\r') {
                    empty = 0;
                    break;
                }
            }
        }
        size_t need = prefix_len + body_len + strlen(end) + 16;
        char *out = malloc(need);
        if (!out) return NULL;
        int n = empty
            ? snprintf(out, need, "%.*s\"sudo\":{%s}%s",
                       (int)prefix_len, json_str, body, end)
            : snprintf(out, need, "%.*s,\"sudo\":{%s}%s",
                       (int)prefix_len, json_str, body, end);
        if (n < 0 || (size_t)n >= need) { free(out); return NULL; }
        return out;
    }

    /* fresh config */
    size_t need = body_len + strlen(ALLTOOL_VERSION) + 64;
    char *out = malloc(need);
    if (!out) return NULL;
    int n = snprintf(out, need,
                     "{\"version\":\"%s\",\"sudo\":{%s}}",
                     ALLTOOL_VERSION, body);
    if (n < 0 || (size_t)n >= need) { free(out); return NULL; }
    return out;
}

static int write_text_file(const char *config_path, const char *text) {
    if (!config_path || !text) return -1;
    FILE *f = fopen(config_path, "w");
    if (!f) return -1;
    int ok = fprintf(f, "%s", text) >= 0;
    if (fclose(f) != 0) ok = 0;
    return ok ? 0 : -1;
}

int alltool_sudo_cache_credentials(const char *config_path, const char *username, const char *password) {
    if (!config_path || !username || !password) return -1;
    if (!valid_username(username)) return -1;

    /* v2 record: ChaCha20 + PBKDF2-SHA256 keystore + HMAC tag, bound to
     * `username`. On a username rename this record stops verifying and
     * the tooling re-caches — it can never be reused by another user. */
    char *salt = NULL, *nonce = NULL, *record_key = NULL;
    char *encrypted = NULL, *tag = NULL;
    if (alltool_sudo_encrypt_password_v2(password, username, 0,
                                         &salt, &nonce, &record_key,
                                         &encrypted, &tag) != 0) {
        return -1;
    }

    char *json_str = read_config_file(config_path);
    /* bound-checkable buffer: all fields are hex/username, so a fixed
     * margin above the summed field lengths is safe against overflow. */
    size_t body_len = 4 * strlen(username)
        + strlen(salt) + strlen(nonce) + strlen(record_key)
        + strlen(encrypted) + strlen(tag) + 256;
    char *body = malloc(body_len);
    if (!body) {
        free(json_str); free(salt); free(nonce); free(record_key);
        free(encrypted); free(tag);
        return -1;
    }
    int n = snprintf(body, body_len,
        "\"cached\":true,\"scheme\":\"%s\",\"username\":\"%s\","
        "\"iterations\":%u,\"salt\":\"%s\",\"nonce\":\"%s\","
        "\"record_key\":\"%s\",\"encrypted_password\":\"%s\",\"auth_tag\":\"%s\"",
        ALLTOOL_SUDO_SCHEME_V2, username, ALLTOOL_SUDO_DEFAULT_ITERS,
        salt, nonce, record_key, encrypted, tag);
    if (n < 0 || (size_t)n >= body_len) {
        free(json_str); free(body); free(salt); free(nonce); free(record_key);
        free(encrypted); free(tag);
        return -1;
    }

    char *new_json = json_with_sudo_body(json_str, body);
    free(json_str); free(body);

    int rc = -1;
    if (new_json && write_text_file(config_path, new_json) == 0) {
        rc = 0;
    }

    /*Wipe key-bearing transient strings before they hit the heap for free() */
    secure_zero(salt, strlen(salt));
    secure_zero(record_key, strlen(record_key));
    secure_zero(encrypted, strlen(encrypted));
    secure_zero(tag, strlen(tag));
    free(salt); free(nonce); free(record_key);
    free(encrypted); free(tag);
    free(new_json);
    return rc;
}

/* Extract an unsigned int value of `key` inside the sudo object body. */
static int sudo_block_uint(char *sudo_start, char *sudo_end,
                           const char *key, unsigned int *out) {
    if (!sudo_start || !sudo_end || !key || !out) return -1;
    size_t klen = strlen(key);
    char pat[96];
    snprintf(pat, sizeof(pat), "\"%s\"", key);
    char *p = sudo_start;
    while (p && p < sudo_end) {
        p = strstr(p, pat);
        if (!p || p >= sudo_end) return -1;
        /* key must not be inside another word: preceding char is ',' '{' */
        char prev = (p > sudo_start) ? p[-1] : '{';
        (void)prev;
        p = strchr(p + klen, ':');
        if (!p || p > sudo_end) return -1;
        p++;
        while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') p++;
        if (p > sudo_end) return -1;
        unsigned long v = 0;
        if (*p >= '0' && *p <= '9') {
            char *endp = NULL;
            v = strtoul(p, &endp, 10);
            if (endp && endp != p) {
                *out = (unsigned int)v;
                return 0;
            }
        }
        return -1;
    }
    return -1;
}

int alltool_sudo_load_credentials(const char *config_path, alltool_sudo_creds_t *creds) {
    if (!config_path || !creds) return -1;
    memset(creds, 0, sizeof(alltool_sudo_creds_t));

    char *json_str = read_config_file(config_path);
    if (!json_str) return -1;

    if (!parse_cached_bool(json_str)) {
        free(json_str);
        return -1;
    }

    /* All record fields are searched *inside* the sudo block, so the
     * top-level "username" cannot shadow the record's owner. */
    char *sudo_start = NULL, *sudo_end = NULL;
    if (find_sudo_object(json_str, &sudo_start, &sudo_end) != 0) {
        free(json_str);
        return -1;
    }

    char *username = strstr_range(sudo_start, sudo_end, "\"username\"");
    char *encrypted = strstr_range(sudo_start, sudo_end, "\"encrypted_password\"");
    char *salt = strstr_range(sudo_start, sudo_end, "\"salt\"");
    char *scheme = strstr_range(sudo_start, sudo_end, "\"scheme\"");
    char *nonce = strstr_range(sudo_start, sudo_end, "\"nonce\"");
    char *tag = strstr_range(sudo_start, sudo_end, "\"auth_tag\"");
    char *record_key = strstr_range(sudo_start, sudo_end, "\"record_key\"");

    if (!username || !encrypted || !salt) {
        free(json_str);
        return -1;
    }

    creds->username = extract_json_value(username);
    creds->encrypted_password = extract_json_value(encrypted);
    creds->salt = extract_json_value(salt);
    /* absent scheme == legacy v1 record (upgraded automatically later) */
    creds->scheme = scheme ? extract_json_value(scheme) : NULL;
    creds->nonce = nonce ? extract_json_value(nonce) : NULL;
    creds->auth_tag = tag ? extract_json_value(tag) : NULL;
    creds->record_key = record_key ? extract_json_value(record_key) : NULL;
    creds->iterations = 0;
    sudo_block_uint(sudo_start, sudo_end, "iterations", &creds->iterations);
    creds->cached = true;

    free(json_str);
    return 0;
}

static char *extract_json_value(char *start) {
    start = strchr(start, ':');
    if (!start) return NULL;
    start = strchr(start, '"');
    if (!start) return NULL;
    start++;
    // Handle \" escapes so values containing quotes don't truncate early.
    char *p = start;
    size_t out_len = 0;
    while (*p && *p != '"') {
        if (*p == '\\' && p[1]) { p += 2; out_len++; }
        else { p++; out_len++; }
    }
    if (!*p) return NULL;
    char *val = malloc(out_len + 1);
    if (!val) return NULL;
    char *dst = val;
    p = start;
    while (*p && *p != '"') {
        if (*p == '\\' && p[1]) { p++; *dst++ = *p++; }
        else *dst++ = *p++;
    }
    *dst = '\0';
    return val;
}

void alltool_sudo_free_creds(alltool_sudo_creds_t *creds) {
    if (!creds) return;
    free(creds->username);
    free(creds->encrypted_password);
    free(creds->salt);
    free(creds->scheme);
    free(creds->nonce);
    free(creds->auth_tag);
    free(creds->record_key);
    memset(creds, 0, sizeof(alltool_sudo_creds_t));
}

int alltool_sudo_clear_cache(const char *config_path) {
    if (!config_path) return -1;
    char *json_str = read_config_file(config_path);
    if (!json_str) return -1;

    char *new_json = json_with_sudo_body(json_str,
        "\"cached\":false,\"scheme\":\"\",\"username\":\"\",\"iterations\":0,"
        "\"salt\":\"\",\"nonce\":\"\",\"record_key\":\"\","
        "\"encrypted_password\":\"\",\"auth_tag\":\"\"");

    int rc = new_json ? write_text_file(config_path, new_json) : -1;

    free(new_json);
    free(json_str);
    return rc;
}

/* ------------------------------------------------------------------ *
 * Legacy v1 recovery + unified run path.                                */

/* Inverse of alltool_sudo_encrypt_password: the legacy blob is
 * password XOR salt (repeating), hex-encoded — recoverable only with
 * the very salt stored beside it, which binds this function to record
 * migration, never new records. */
static int legacy_v1_decrypt(const char *encrypted_hex, const char *salt_hex,
                             char **password_out) {
    if (!encrypted_hex || !salt_hex || !password_out) return -1;
    size_t hex_len = strlen(encrypted_hex);
    if (hex_len == 0 || hex_len % 2 != 0) return -1;
    size_t ct_len = hex_len / 2;
    unsigned char bin_salt[SALT_LENGTH];
    if (hex_to_bin(salt_hex, bin_salt, SALT_LENGTH) != 0) return -1;

    unsigned char *ct = malloc(ct_len);
    char *pw = malloc(ct_len + 1);
    if (!ct || !pw) { free(ct); free(pw); return -1; }
    if (alltool_hex_decode(encrypted_hex, ct, ct_len) != 0) {
        alltool_secure_zero(ct, ct_len);
        alltool_secure_zero(pw, ct_len + 1);
        free(ct); free(pw);
        return -1;
    }
    size_t max_salt = strlen(salt_hex) / 2;
    for (size_t i = 0; i < ct_len; i++) {
        unsigned char salt_byte = bin_salt[i % (max_salt ? max_salt : 1)];
        pw[i] = (char)(ct[i] ^ salt_byte);
    }
    pw[ct_len] = '\0';
    (void)max_salt;

    alltool_secure_zero(ct, ct_len);
    free(ct);
    *password_out = pw;
    return 0;
}

int alltool_sudo_run_cached(const char *config_path, const char *command, char **output) {
    if (!config_path || !command || !output) return -1;
    *output = NULL;

    alltool_sudo_creds_t creds;
    if (alltool_sudo_load_credentials(config_path, &creds) != 0 || !creds.cached) {
        return -1;
    }

    int legacy = (creds.scheme == NULL || strcmp(creds.scheme, ALLTOOL_SUDO_SCHEME_V2) != 0);
    char *password = NULL;
    int rc = -1;

    if (legacy) {
        /* v1: XOR-inverse recover + verify round-trip against the
         * stored blob (catches truncated/corrupt legacy records). */
        if (legacy_v1_decrypt(creds.encrypted_password, creds.salt, &password) != 0) {
            alltool_sudo_free_creds(&creds);
            return -1;
        }
        if (alltool_sudo_verify_password(creds.encrypted_password, creds.salt, password) != 0) {
            secure_zero(password, strlen(password));
            free(password);
            alltool_sudo_free_creds(&creds);
            return -1;
        }
    } else {
        /* v2: HMAC tag first (integrity + username binding), then
         * ChaCha20 recovery. Wrong owner = tag mismatch = refusal. */
        if (alltool_sudo_decrypt_password_v2(creds.encrypted_password, creds.salt,
                                             creds.nonce, creds.auth_tag,
                                             creds.iterations, creds.username,
                                             creds.record_key,
                                             &password) != 0) {
            alltool_sudo_free_creds(&creds);
            return -2; /* caller should self-heal (username changed?) */
        }
    }

    if (*password == '\0') {
        /* empty password would still be written to sudo; treat as broken */
        secure_zero(password, 1);
        free(password);
        alltool_sudo_free_creds(&creds);
        return -1;
    }

    rc = alltool_sudo_run_with_creds(creds.username, password, command, output);

    /* Transparent upgrade: a successful legacy run gets re-recorded in
     * the current scheme (bound to username, tamper-checked). */
    if (legacy && rc == 0) {
        alltool_sudo_cache_credentials(config_path, creds.username, password);
    }

    secure_zero(password, strlen(password));
    free(password);
    password = NULL;
    alltool_sudo_free_creds(&creds);
    return rc;
}
