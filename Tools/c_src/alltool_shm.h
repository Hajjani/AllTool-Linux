#ifndef ALLTOOL_SHM_H
#define ALLTOOL_SHM_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ALLTOOL_SHM_NAME "/alltool_chain"
#define ALLTOOL_MAX_PROCESSES 64
#define ALLTOOL_MAX_PAYLOAD 4096

typedef enum {
    ALLTOOL_PROC_IDLE = 0,
    ALLTOOL_PROC_RUNNING = 1,
    ALLTOOL_PROC_DONE = 2,
    ALLTOOL_PROC_ERROR = 3
} alltool_proc_state_t;

typedef struct {
    uint32_t magic;
    uint32_t version;
    pid_t pids[ALLTOOL_MAX_PROCESSES];
    alltool_proc_state_t states[ALLTOOL_MAX_PROCESSES];
    int32_t predecessor[ALLTOOL_MAX_PROCESSES];
    char payloads[ALLTOOL_MAX_PROCESSES][ALLTOOL_MAX_PAYLOAD];
    size_t payload_sizes[ALLTOOL_MAX_PROCESSES];
    uint32_t process_count;
    uint32_t head_index;
    uint32_t tail_index;
    bool initialized;
} alltool_shm_t;

typedef struct {
    int shm_fd;
    alltool_shm_t *shm;
    uint32_t my_index;
    int32_t my_predecessor;
} alltool_chain_ctx_t;

int alltool_shm_init(const char *name, size_t size);
int alltool_shm_attach(const char *name, alltool_chain_ctx_t *ctx);
int alltool_shm_register_process(alltool_chain_ctx_t *ctx, pid_t pid, int32_t predecessor_idx);
int alltool_shm_wait_predecessor(alltool_chain_ctx_t *ctx, int timeout_ms);
int alltool_shm_send_payload(alltool_chain_ctx_t *ctx, const void *data, size_t size);
int alltool_shm_recv_payload(alltool_chain_ctx_t *ctx, void *buffer, size_t *size);
int alltool_shm_mark_done(alltool_chain_ctx_t *ctx, int status);
void alltool_shm_detach(alltool_chain_ctx_t *ctx);
void alltool_shm_cleanup(const char *name);

#ifdef __cplusplus
}
#endif

#endif