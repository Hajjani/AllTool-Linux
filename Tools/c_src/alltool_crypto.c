#define _GNU_SOURCE
#include "alltool_crypto.h"
#include <stdlib.h>
#include <string.h>

/* ------------------------------------------------------------------ *
 * secure_zero: volatile-store loop the optimizer must keep (no
 * dead-store elimination on a byte wipe).                               */
void alltool_secure_zero(void *ptr, size_t len) {
    if (!ptr || len == 0) return;
    volatile unsigned char *p = (volatile unsigned char *)ptr;
    while (len--) *p++ = 0;
}

/* ------------------------------------------------------------------ *
 * SHA-256 (FIPS 180-4).                                                 */

static const uint32_t SHA256_K[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u,
    0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
    0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
    0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
    0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
    0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
    0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
    0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
    0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
    0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u,
    0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u,
    0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
    0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
    0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u
};

static const uint32_t SHA256_IV[8] = {
    0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
    0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u
};

static uint32_t rotr32(uint32_t x, unsigned n) {
    return (x >> n) | (x << (32u - n));
}

static void sha256_be32_enc(unsigned char *out, uint32_t v) {
    out[0] = (unsigned char)(v >> 24);
    out[1] = (unsigned char)(v >> 16);
    out[2] = (unsigned char)(v >> 8);
    out[3] = (unsigned char)(v);
}

static uint32_t sha256_be32_dec(const unsigned char *in) {
    return ((uint32_t)in[0] << 24) | ((uint32_t)in[1] << 16) |
           ((uint32_t)in[2] << 8)  | (uint32_t)in[3];
}

static void sha256_compress(alltool_sha256_ctx *c, const unsigned char block[64]) {
    uint32_t w[64];
    for (int i = 0; i < 16; i++) {
        w[i] = sha256_be32_dec(block + i * 4);
    }
    for (int i = 16; i < 64; i++) {
        uint32_t s0 = rotr32(w[i - 15], 7) ^ rotr32(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = rotr32(w[i - 2], 17) ^ rotr32(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }

    uint32_t a = c->h[0], b = c->h[1], cc = c->h[2], d = c->h[3];
    uint32_t e = c->h[4], f = c->h[5], g = c->h[6], h = c->h[7];

    for (int i = 0; i < 64; i++) {
        uint32_t S1 = rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25);
        uint32_t ch = (e & f) ^ ((~e) & g);
        uint32_t t1 = h + S1 + ch + SHA256_K[i] + w[i];
        uint32_t S0 = rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22);
        uint32_t maj = (a & b) ^ (a & cc) ^ (b & cc);
        uint32_t t2 = S0 + maj;
        h = g; g = f; f = e; e = d + t1;
        d = cc; cc = b; b = a; a = t1 + t2;
    }

    c->h[0] += a; c->h[1] += b; c->h[2] += cc; c->h[3] += d;
    c->h[4] += e; c->h[5] += f; c->h[6] += g; c->h[7] += h;

    alltool_secure_zero(w, sizeof(w));
}

void alltool_sha256_init(alltool_sha256_ctx *c) {
    for (int i = 0; i < 8; i++) c->h[i] = SHA256_IV[i];
    c->total_len = 0;
    c->buf_len = 0;
    memset(c->buf, 0, sizeof(c->buf));
}

void alltool_sha256_update(alltool_sha256_ctx *c, const unsigned char *data, size_t len) {
    if (!data && len != 0) return;
    c->total_len += len;
    while (len > 0) {
        size_t take = ALLTOOL_HMAC_BLOCK - c->buf_len;
        if (take > len) take = len;
        memmove(c->buf + c->buf_len, data, take);
        c->buf_len += take;
        data += take;
        len -= take;
        if (c->buf_len == ALLTOOL_HMAC_BLOCK) {
            sha256_compress(c, c->buf);
            c->buf_len = 0;
        }
    }
}

void alltool_sha256_final(alltool_sha256_ctx *c, unsigned char out[ALLTOOL_SHA256_LEN]) {
    uint64_t bit_len = c->total_len * 8;
    unsigned char pad_buf[ALLTOOL_HMAC_BLOCK];
    size_t i;

    /* append 0x80, zeros to 56, then big-endian 64-bit length */
    memset(pad_buf, 0, sizeof(pad_buf));
    pad_buf[0] = 0x80;
    size_t pad_len = (c->buf_len < 56) ? 56 - c->buf_len : (120 - c->buf_len);
    alltool_sha256_update(c, pad_buf, pad_len);
    for (i = 0; i < 8; i++) {
        pad_buf[i] = (unsigned char)(bit_len >> (56 - 8 * i));
    }
    alltool_sha256_update(c, pad_buf, 8);
    /* update may have queued another block hash it now */
    if (c->buf_len == ALLTOOL_HMAC_BLOCK) {
        sha256_compress(c, c->buf);
        c->buf_len = 0;
    }

    for (i = 0; i < 8; i++) {
        sha256_be32_enc(out + i * 4, c->h[i]);
    }
    alltool_secure_zero(c, sizeof(*c));
    alltool_secure_zero(pad_buf, sizeof(pad_buf));
}

void alltool_sha256(const unsigned char *data, size_t len,
                    unsigned char out[ALLTOOL_SHA256_LEN]) {
    alltool_sha256_ctx c;
    alltool_sha256_init(&c);
    alltool_sha256_update(&c, data, len);
    alltool_sha256_final(&c, out);
}

/* ------------------------------------------------------------------ *
 * HMAC-SHA256 (RFC 2104).                                               */

void alltool_hmac_sha256(const unsigned char *key, size_t key_len,
                         const unsigned char *msg, size_t msg_len,
                         unsigned char out[ALLTOOL_SHA256_LEN]) {
    unsigned char k_block[ALLTOOL_HMAC_BLOCK];
    unsigned char inner[ALLTOOL_SHA256_LEN];
    alltool_sha256_ctx ctx;

    unsigned char k_short[ALLTOOL_SHA256_LEN];
    if (key_len > ALLTOOL_HMAC_BLOCK) {
        alltool_sha256(key, key_len, k_short);
        key = k_short;
        key_len = ALLTOOL_SHA256_LEN;
    }
    memset(k_block, 0, sizeof(k_block));
    memcpy(k_block, key, key_len);

    int i;
    /* inner: H(K^ipad, msg) */
    for (i = 0; i < ALLTOOL_HMAC_BLOCK; i++) k_block[i] ^= 0x36;
    alltool_sha256_init(&ctx);
    alltool_sha256_update(&ctx, k_block, ALLTOOL_HMAC_BLOCK);
    alltool_sha256_update(&ctx, msg, msg_len);
    alltool_sha256_final(&ctx, inner);

    /* outer: H(K^opad, inner) */
    for (i = 0; i < ALLTOOL_HMAC_BLOCK; i++) k_block[i] ^= 0x36 ^ 0x5c;
    alltool_sha256_init(&ctx);
    alltool_sha256_update(&ctx, k_block, ALLTOOL_HMAC_BLOCK);
    alltool_sha256_update(&ctx, inner, ALLTOOL_SHA256_LEN);
    alltool_sha256_final(&ctx, out);

    alltool_secure_zero(k_block, sizeof(k_block));
    alltool_secure_zero(k_short, sizeof(k_short));
    alltool_secure_zero(inner, sizeof(inner));
}

/* ------------------------------------------------------------------ *
 * PBKDF2-HMAC-SHA256 (RFC 8018).                                        */

void alltool_pbkdf2_sha256(const unsigned char *pw, size_t pw_len,
                           const unsigned char *salt, size_t salt_len,
                           uint32_t iterations,
                           unsigned char *dk, size_t dk_len) {
    if (!dk || !dk_len || !pw || !pw_len) return;
    uint32_t iters = iterations ? iterations : 1;
    size_t it;

    size_t blocks = dk_len / ALLTOOL_SHA256_LEN;
    if (dk_len % ALLTOOL_SHA256_LEN) blocks++;

    unsigned char *salt_idx = malloc(salt_len + 4);
    unsigned char u1[ALLTOOL_SHA256_LEN];
    unsigned char uj[ALLTOOL_SHA256_LEN];
    unsigned char acc[ALLTOOL_SHA256_LEN];
    if (!salt_idx) return; /* dk untouched; caller reports failure */

    for (size_t bi = 0; bi < blocks; bi++) {
        /* INT(1-based block index) big-endian appended to salt */
        if (salt && salt_len) memcpy(salt_idx, salt, salt_len);
        sha256_be32_enc(salt_idx + salt_len, (uint32_t)(bi + 1));

        alltool_hmac_sha256(pw, pw_len, salt_idx, salt_len + 4, u1);
        memcpy(uj, u1, ALLTOOL_SHA256_LEN);
        memcpy(acc, u1, ALLTOOL_SHA256_LEN);

        for (uint32_t j = 2; j <= iters; j++) {
            alltool_hmac_sha256(pw, pw_len, uj, ALLTOOL_SHA256_LEN, uj);
            for (it = 0; it < ALLTOOL_SHA256_LEN; it++) {
                acc[it] ^= uj[it];
            }
        }

        size_t copy_len = dk_len - bi * ALLTOOL_SHA256_LEN;
        if (copy_len > ALLTOOL_SHA256_LEN) copy_len = ALLTOOL_SHA256_LEN;
        memcpy(dk + bi * ALLTOOL_SHA256_LEN, acc, copy_len);
    }

    alltool_secure_zero(salt_idx, salt_len + 4);
    alltool_secure_zero(u1, sizeof(u1));
    alltool_secure_zero(uj, sizeof(uj));
    alltool_secure_zero(acc, sizeof(acc));
    free(salt_idx);
}

/* ------------------------------------------------------------------ *
 * ChaCha20 (RFC 8439) 32-bit core.                                      */

static uint32_t load32_le(const unsigned char *b) {
    return (uint32_t)b[0] | ((uint32_t)b[1] << 8) |
           ((uint32_t)b[2] << 16) | ((uint32_t)b[3] << 24);
}

static void store32_le(unsigned char *b, uint32_t v) {
    b[0] = (unsigned char)(v & 0xFFu);
    b[1] = (unsigned char)((v >> 8) & 0xFFu);
    b[2] = (unsigned char)((v >> 16) & 0xFFu);
    b[3] = (unsigned char)((v >> 24) & 0xFFu);
}

#define CHACHA_ROTL(x, n) ( ((x) << (n)) | ((x) >> (32u - (n))) )
#define CHACHA_QR(a, b, c, d)                                  \
    a += b; d ^= a; d = CHACHA_ROTL(d, 16);                    \
    c += d; b ^= c; b = CHACHA_ROTL(b, 12);                    \
    a += b; d ^= a; d = CHACHA_ROTL(d, 8);                     \
    c += d; b ^= c; b = CHACHA_ROTL(b, 7);

static void chacha20_block(uint32_t state[16], unsigned char keystream[64]) {
    uint32_t x[16];
    memcpy(x, state, 16 * sizeof(uint32_t));
    for (int i = 0; i < 10; i++) {
        CHACHA_QR(x[0], x[4], x[8],  x[12]); /* column rounds */
        CHACHA_QR(x[1], x[5], x[9],  x[13]);
        CHACHA_QR(x[2], x[6], x[10], x[14]);
        CHACHA_QR(x[3], x[7], x[11], x[15]);
        CHACHA_QR(x[0], x[5], x[10], x[15]); /* diagonal rounds */
        CHACHA_QR(x[1], x[6], x[11], x[12]);
        CHACHA_QR(x[2], x[7], x[8],  x[13]);
        CHACHA_QR(x[3], x[4], x[9],  x[14]);
    }
    for (int i = 0; i < 16; i++) {
        store32_le(keystream + i * 4, x[i] + state[i]);
    }
    alltool_secure_zero(x, sizeof(x));
}

void alltool_chacha20_xor(const unsigned char key[ALLTOOL_CHACHA_KEY_LEN],
                          const unsigned char nonce[ALLTOOL_CHACHA_NONCE_LEN],
                          uint32_t initial_counter,
                          const unsigned char *data, size_t len,
                          unsigned char *out) {
    if (!data && len != 0) return;
    uint32_t state[16];
    unsigned char keystream[64];
    size_t off = 0;

    state[0] = 0x61707865u; /* "expa" */
    state[1] = 0x3320646eu; /* "nd 3" */
    state[2] = 0x79622d32u; /* "2-by" */
    state[3] = 0x6b206574u; /* "te k" */
    for (int i = 0; i < 8; i++) {
        state[4 + i] = load32_le(key + i * 4);
    }
    state[12] = initial_counter;
    for (int i = 0; i < 3; i++) {
        state[13 + i] = load32_le(nonce + i * 4);
    }

    while (off < len) {
        size_t chunk = len - off;
        if (chunk > 64) chunk = 64;
        chacha20_block(state, keystream);
        for (size_t i = 0; i < chunk; i++) {
            out[off + i] = data[off + i] ^ keystream[i];
        }
        off += chunk;
        if (++state[12] == 0) {
            /* 2^32 blocks = 256 GiB of keystream per (key, nonce);
             * a sudo password never gets close. Fail closed. */
            break;
        }
    }

    alltool_secure_zero(state, sizeof(state));
    alltool_secure_zero(keystream, sizeof(keystream));
}

/* ------------------------------------------------------------------ *
 * hex helpers                                                           */

char *alltool_hex_encode(const unsigned char *bin, size_t n) {
    static const char digits[] = "0123456789abcdef";
    char *hex = malloc(n * 2 + 1);
    if (!hex) return NULL;
    for (size_t i = 0; i < n; i++) {
        hex[i * 2]     = digits[bin[i] >> 4];
        hex[i * 2 + 1] = digits[bin[i] & 0x0Fu];
    }
    hex[n * 2] = '\0';
    return hex;
}

static int hexval(unsigned char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int alltool_hex_decode(const char *hex, unsigned char *bin, size_t bin_len) {
    if (!hex || bin_len * 2 != strlen(hex)) return -1;
    for (size_t i = 0; i < bin_len; i++) {
        int hi = hexval((unsigned char)hex[i * 2]);
        int lo = hexval((unsigned char)hex[i * 2 + 1]);
        if (hi < 0 || lo < 0) return -1;
        bin[i] = (unsigned char)((hi << 4) | lo);
    }
    return 0;
}

int alltool_consttime_eq(const unsigned char *a, const unsigned char *b, size_t n) {
    unsigned char diff = 0;
    for (size_t i = 0; i < n; i++) diff |= a[i] ^ b[i];
    return diff == 0 ? 1 : 0;
}
