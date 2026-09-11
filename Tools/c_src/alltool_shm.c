#define _GNU_SOURCE
#include "alltool_shm.h"
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>
#include <semaphore.h>
#include <time.h>

#define SHM_MAGIC 0x414C544F
#define SHM_VERSION 1

static sem_t *get_semaphore(alltool_shm_t *shm) {
    return (sem_t *)((char *)shm + sizeof(alltool_shm_t));
}

int alltool_shm_init(const char *name, size_t size) {
    int fd = shm_open(name, O_CREAT | O_EXCL | O_RDWR, 0600);
    if (fd < 0) {
        if (errno == EEXIST) {
            fd = shm_open(name, O_RDWR, 0600);
            if (fd < 0) return -1;
            struct stat st;
            if (fstat(fd, &st) == 0 && st.st_size >= (off_t)size) {
                return 0;
            }
        }
        return -1;
    }

    if (ftruncate(fd, size) < 0) {
        close(fd);
        shm_unlink(name);
        return -1;
    }

    void *ptr = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (ptr == MAP_FAILED) {
        close(fd);
        shm_unlink(name);
        return -1;
    }

    alltool_shm_t *shm = (alltool_shm_t *)ptr;
    memset(shm, 0, sizeof(alltool_shm_t));
    shm->magic = SHM_MAGIC;
    shm->version = SHM_VERSION;
    shm->initialized = true;

    sem_t *sem = get_semaphore(shm);
    sem_init(sem, 1, 1);

    munmap(ptr, size);
    close(fd);
    return 0;
}

int alltool_shm_attach(const char *name, alltool_chain_ctx_t *ctx) {
    int fd = shm_open(name, O_RDWR, 0600);
    if (fd < 0) return -1;

    struct stat st;
    if (fstat(fd, &st) < 0) {
        close(fd);
        return -1;
    }

    void *ptr = mmap(NULL, st.st_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (ptr == MAP_FAILED) {
        close(fd);
        return -1;
    }

    alltool_shm_t *shm = (alltool_shm_t *)ptr;
    if (shm->magic != SHM_MAGIC || !shm->initialized) {
        munmap(ptr, st.st_size);
        close(fd);
        return -1;
    }

    ctx->shm_fd = fd;
    ctx->shm = shm;
    ctx->my_index = UINT32_MAX;
    ctx->my_predecessor = -1;
    return 0;
}

int alltool_shm_register_process(alltool_chain_ctx_t *ctx, pid_t pid, int32_t predecessor_idx) {
    if (!ctx || !ctx->shm) return -1;

    sem_t *sem = get_semaphore(ctx->shm);
    sem_wait(sem);

    if (ctx->shm->process_count >= ALLTOOL_MAX_PROCESSES) {
        sem_post(sem);
        return -1;
    }

    uint32_t idx = ctx->shm->process_count;
    ctx->shm->pids[idx] = pid;
    ctx->shm->states[idx] = ALLTOOL_PROC_RUNNING;
    ctx->shm->predecessor[idx] = predecessor_idx;
    ctx->shm->payload_sizes[idx] = 0;
    ctx->shm->process_count++;
    ctx->shm->tail_index = idx;

    ctx->my_index = idx;
    ctx->my_predecessor = predecessor_idx;

    sem_post(sem);
    return 0;
}

int alltool_shm_wait_predecessor(alltool_chain_ctx_t *ctx, int timeout_ms) {
    if (!ctx || !ctx->shm || ctx->my_index == UINT32_MAX) return -1;
    if (ctx->my_predecessor < 0) return 0;

    sem_t *sem = get_semaphore(ctx->shm);
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    ts.tv_sec += timeout_ms / 1000;
    ts.tv_nsec += (timeout_ms % 1000) * 1000000;
    if (ts.tv_nsec >= 1000000000) {
        ts.tv_nsec -= 1000000000;
        ts.tv_sec++;
    }

    while (1) {
        sem_wait(sem);
        if (ctx->shm->states[ctx->my_predecessor] == ALLTOOL_PROC_DONE ||
            ctx->shm->states[ctx->my_predecessor] == ALLTOOL_PROC_ERROR) {
            sem_post(sem);
            return ctx->shm->states[ctx->my_predecessor] == ALLTOOL_PROC_DONE ? 0 : -1;
        }
        sem_post(sem);

        if (timeout_ms >= 0) {
            if (sem_timedwait(sem, &ts) == -1 && errno == ETIMEDOUT) {
                return -1;
            }
        } else {
            sem_wait(sem);
        }
        usleep(1000);
    }
}

int alltool_shm_send_payload(alltool_chain_ctx_t *ctx, const void *data, size_t size) {
    if (!ctx || !ctx->shm || ctx->my_index == UINT32_MAX) return -1;
    if (size > ALLTOOL_MAX_PAYLOAD) return -1;

    sem_t *sem = get_semaphore(ctx->shm);
    sem_wait(sem);

    memcpy(ctx->shm->payloads[ctx->my_index], data, size);
    ctx->shm->payload_sizes[ctx->my_index] = size;

    sem_post(sem);
    return 0;
}

int alltool_shm_recv_payload(alltool_chain_ctx_t *ctx, void *buffer, size_t *size) {
    if (!ctx || !ctx->shm || ctx->my_predecessor < 0) return -1;

    sem_t *sem = get_semaphore(ctx->shm);
    sem_wait(sem);

    size_t payload_size = ctx->shm->payload_sizes[ctx->my_predecessor];
    if (payload_size > 0 && payload_size <= *size) {
        memcpy(buffer, ctx->shm->payloads[ctx->my_predecessor], payload_size);
        *size = payload_size;
    } else {
        *size = 0;
    }

    sem_post(sem);
    return 0;
}

int alltool_shm_mark_done(alltool_chain_ctx_t *ctx, int status) {
    if (!ctx || !ctx->shm || ctx->my_index == UINT32_MAX) return -1;

    sem_t *sem = get_semaphore(ctx->shm);
    sem_wait(sem);

    ctx->shm->states[ctx->my_index] = status == 0 ? ALLTOOL_PROC_DONE : ALLTOOL_PROC_ERROR;

    sem_post(sem);
    return 0;
}

void alltool_shm_detach(alltool_chain_ctx_t *ctx) {
    if (ctx && ctx->shm) {
        struct stat st;
        if (fstat(ctx->shm_fd, &st) == 0) {
            munmap(ctx->shm, st.st_size);
        }
        close(ctx->shm_fd);
        ctx->shm = NULL;
        ctx->shm_fd = -1;
    }
}

void alltool_shm_cleanup(const char *name) {
    shm_unlink(name);
}