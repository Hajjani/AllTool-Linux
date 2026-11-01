/* Dependency-free crypto core for AllTool (.confs.json password-at-rest).
 *
 * Provides exactly what alltool_sudo.c needs and nothing else:
 *   - SHA-256 / HMAC-SHA256                 (integrity tags, KDF)
 *   - PBKDF2-HMAC-SHA256                    (password -> key derivation)
 *   - ChaCha20 (RFC 8439, 12-byte nonce)    (stream cipher for storage)
 *   - hex helpers + non-optimizable secure_zero
 *
 * No external libraries: C11 + libc only, so the .so list in the
 * Makefile/CI does not change. All sensitive buffers should be wiped
 * with alltool_secure_zero() by the callers.
 */
#ifndef ALLTOOL_CRYPTO_H
#define ALLTOOL_CRYPTO_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ALLTOOL_SHA256_LEN 32
#define ALLTOOL_HMAC_BLOCK 64
#define ALLTOOL_CHACHA_KEY_LEN 32
#define ALLTOOL_CHACHA_NONCE_LEN 12

/* ---- secure wipe ---- */
void alltool_secure_zero(void *ptr, size_t len);

/* ---- SHA-256 ---- */
typedef struct {
    uint32_t h[8];
    uint64_t total_len;
    unsigned char buf[ALLTOOL_HMAC_BLOCK];
    size_t buf_len;
} alltool_sha256_ctx;

void alltool_sha256_init(alltool_sha256_ctx *ctx);
void alltool_sha256_update(alltool_sha256_ctx *ctx,
                           const unsigned char *data, size_t len);
void alltool_sha256_final(alltool_sha256_ctx *ctx, unsigned char out[ALLTOOL_SHA256_LEN]);

void alltool_sha256(const unsigned char *data, size_t len,
                    unsigned char out[ALLTOOL_SHA256_LEN]);

/* ---- HMAC-SHA256 ---- */
void alltool_hmac_sha256(const unsigned char *key, size_t key_len,
                         const unsigned char *msg, size_t msg_len,
                         unsigned char out[ALLTOOL_SHA256_LEN]);

/* ---- PBKDF2-HMAC-SHA256 (dklen bytes into dk) ---- */
void alltool_pbkdf2_sha256(const unsigned char *pw, size_t pw_len,
                           const unsigned char *salt, size_t salt_len,
                           uint32_t iterations,
                           unsigned char *dk, size_t dk_len);

/* ---- ChaCha20 stream XOR (RFC 8439, 32B key / 12B nonce) ---- */
void alltool_chacha20_xor(const unsigned char key[ALLTOOL_CHACHA_KEY_LEN],
                          const unsigned char nonce[ALLTOOL_CHACHA_NONCE_LEN],
                          uint32_t initial_counter,
                          const unsigned char *data, size_t len,
                          unsigned char *out);

/* ---- hex ---- */
/* Encode n bytes into a freshly malloc'd (2n+1) lowercase hex string.
 * Returns NULL on allocation failure. */
char *alltool_hex_encode(const unsigned char *bin, size_t n);
/* Decode exactly 2*bin_len hex chars into bin. Returns 0 on success. */
int alltool_hex_decode(const char *hex, unsigned char *bin, size_t bin_len);

/* ---- constant-time compare ---- */
int alltool_consttime_eq(const unsigned char *a, const unsigned char *b, size_t n);

#ifdef __cplusplus
}
#endif

#endif /* ALLTOOL_CRYPTO_H */
