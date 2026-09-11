#define _GNU_SOURCE
#include "alltool_sudo.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <termios.h>
#include <fcntl.h>
#include <sys/wait.h>
#include <time.h>

#define SALT_LENGTH 16

static char *extract_json_value(char *start);

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

int alltool_sudo_prompt_credentials(const char *prompt, char **username, char **password) {
    char *user = getenv("USER");
    if (user) {
        *username = strdup(user);
    } else {
        char buf[256];
        printf("Username: ");
        fflush(stdout);
        if (!fgets(buf, sizeof(buf), stdin)) return -1;
        buf[strcspn(buf, "\n")] = '\0';
        *username = strdup(buf);
    }

    char prompt_buf[512];
    snprintf(prompt_buf, sizeof(prompt_buf), "%s [%s]: ", prompt ? prompt : "Password", *username);
    return read_password(prompt_buf, password);
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
    free(key);
    return 0;
}

int alltool_sudo_verify_password(const char *encrypted, const char *salt, const char *password) {
    char *test_encrypted = NULL;
    int ret = alltool_sudo_encrypt_password(password, salt, &test_encrypted);
    if (ret != 0) return -1;

    int match = (strcmp(test_encrypted, encrypted) == 0);
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

int alltool_sudo_run_with_creds(const char *username, const char *password, const char *command, char **output) {
    int pipefd[2];
    if (pipe(pipefd) < 0) return -1;

    pid_t pid = fork();
    if (pid < 0) {
        close(pipefd[0]);
        close(pipefd[1]);
        return -1;
    }

    if (pid == 0) {
        close(pipefd[0]);
        dup2(pipefd[1], STDOUT_FILENO);
        dup2(pipefd[1], STDERR_FILENO);
        close(pipefd[1]);

        char sudo_cmd[2048];
        snprintf(sudo_cmd, sizeof(sudo_cmd), "echo %s | sudo -S -u %s %s", password, username, command);
        execl("/bin/sh", "sh", "-c", sudo_cmd, (char *)NULL);
        _exit(127);
    }

    close(pipefd[1]);

    char buffer[4096];
    size_t total = 0;
    size_t capacity = 4096;
    char *result = malloc(capacity);
    if (!result) {
        close(pipefd[0]);
        waitpid(pid, NULL, 0);
        return -1;
    }

    ssize_t n;
    while ((n = read(pipefd[0], buffer, sizeof(buffer))) > 0) {
        if (total + n + 1 >= capacity) {
            capacity *= 2;
            char *new_result = realloc(result, capacity);
            if (!new_result) {
                free(result);
                close(pipefd[0]);
                waitpid(pid, NULL, 0);
                return -1;
            }
            result = new_result;
        }
        memcpy(result + total, buffer, n);
        total += n;
    }
    close(pipefd[0]);

    int status;
    waitpid(pid, &status, 0);

    result[total] = '\0';
    *output = result;
    return WEXITSTATUS(status);
}

int alltool_sudo_cache_credentials(const char *config_path, const char *username, const char *password) {
    char *salt = NULL;
    if (alltool_sudo_generate_salt(&salt) != 0) return -1;

    char *encrypted = NULL;
    if (alltool_sudo_encrypt_password(password, salt, &encrypted) != 0) {
        free(salt);
        return -1;
    }

    FILE *f = fopen(config_path, "r");
    char *json_str = NULL;
    if (f) {
        fseek(f, 0, SEEK_END);
        long len = ftell(f);
        fseek(f, 0, SEEK_SET);
        json_str = malloc(len + 1);
        fread(json_str, 1, len, f);
        json_str[len] = '\0';
        fclose(f);
    }

    char *new_json = malloc((json_str ? strlen(json_str) : 2) + 512);
    if (json_str && strstr(json_str, "\"sudo\"")) {
        char *sudo_start = strstr(json_str, "\"sudo\"");
        char *brace_start = strchr(sudo_start, '{');
        int depth = 0;
        char *brace_end = brace_start;
        while (*brace_end) {
            if (*brace_end == '{') depth++;
            else if (*brace_end == '}') {
                depth--;
                if (depth == 0) break;
            }
            brace_end++;
        }
        size_t prefix_len = sudo_start - json_str;
        size_t suffix_len = strlen(brace_end + 1);
        snprintf(new_json, prefix_len + 512 + suffix_len + 1,
            "%.*s\"sudo\":{\"cached\":true,\"username\":\"%s\",\"encrypted_password\":\"%s\",\"salt\":\"%s\"}%s",
            (int)prefix_len, json_str, username, encrypted, salt, brace_end + 1);
    } else {
        snprintf(new_json, 512,
            "{\"version\":\"2.0.0\",\"sudo\":{\"cached\":true,\"username\":\"%s\",\"encrypted_password\":\"%s\",\"salt\":\"%s\"}}",
            username, encrypted, salt);
    }

    f = fopen(config_path, "w");
    if (!f) {
        free(new_json);
        free(json_str);
        free(salt);
        free(encrypted);
        return -1;
    }

    fprintf(f, "%s", new_json);
    fclose(f);

    free(new_json);
    free(json_str);
    free(salt);
    free(encrypted);
    return 0;
}

int alltool_sudo_load_credentials(const char *config_path, alltool_sudo_creds_t *creds) {
    memset(creds, 0, sizeof(alltool_sudo_creds_t));

    FILE *f = fopen(config_path, "r");
    if (!f) return -1;

    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *json_str = malloc(len + 1);
    fread(json_str, 1, len, f);
    json_str[len] = '\0';
    fclose(f);

    char *cached = strstr(json_str, "\"cached\"");
    if (!cached || strstr(cached, "false")) {
        free(json_str);
        return -1;
    }

    char *username = strstr(json_str, "\"username\"");
    char *encrypted = strstr(json_str, "\"encrypted_password\"");
    char *salt = strstr(json_str, "\"salt\"");

    if (!username || !encrypted || !salt) {
        free(json_str);
        return -1;
    }

    creds->username = extract_json_value(username);
    creds->encrypted_password = extract_json_value(encrypted);
    creds->salt = extract_json_value(salt);
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
    char *end = strchr(start, '"');
    if (!end) return NULL;
    size_t len = end - start;
    char *val = malloc(len + 1);
    memcpy(val, start, len);
    val[len] = '\0';
    return val;
}

void alltool_sudo_free_creds(alltool_sudo_creds_t *creds) {
    if (!creds) return;
    free(creds->username);
    free(creds->encrypted_password);
    free(creds->salt);
    memset(creds, 0, sizeof(alltool_sudo_creds_t));
}

int alltool_sudo_clear_cache(const char *config_path) {
    FILE *f = fopen(config_path, "r");
    if (!f) return -1;

    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *json_str = malloc(len + 1);
    fread(json_str, 1, len, f);
    json_str[len] = '\0';
    fclose(f);

    char *sudo_start = strstr(json_str, "\"sudo\"");
    if (sudo_start) {
        char *brace_start = strchr(sudo_start, '{');
        int depth = 0;
        char *brace_end = brace_start;
        while (*brace_end) {
            if (*brace_end == '{') depth++;
            else if (*brace_end == '}') {
                depth--;
                if (depth == 0) break;
            }
            brace_end++;
        }
        size_t prefix_len = sudo_start - json_str;
        size_t suffix_len = strlen(brace_end + 1);
        char *new_json = malloc(prefix_len + 200 + suffix_len + 1);
        snprintf(new_json, prefix_len + 200 + suffix_len + 1,
            "%.*s\"sudo\":{\"cached\":false,\"username\":\"\",\"encrypted_password\":\"\",\"salt\":\"\"}%s",
            (int)prefix_len, json_str, brace_end + 1);

        f = fopen(config_path, "w");
        if (f) {
            fprintf(f, "%s", new_json);
            fclose(f);
        }
        free(new_json);
    }

    free(json_str);
    return 0;
}