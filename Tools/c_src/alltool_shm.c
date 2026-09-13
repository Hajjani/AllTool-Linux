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
    size_t need = sizeof(alltool_shm_t) + sizeof(sem_t);
    if (size < need) size = need;
    int fd = shm_open(name, O_CREAT | O_EXCL | O_RDWR, 0600);
    if (fd < 0) {
        if (errno == EEXIST) {
            fd = shm_open(name, O_RDWR, 0600);
            if (fd < 0) return -1;
            struct stat st;
            int ok = 0;
            if (fstat(fd, &st) == 0 && st.st_size >= (off_t)need) {
                void *v = mmap(NULL, st.st_size, PROT_READ, MAP_SHARED, fd, 0);
                if (v != MAP_FAILED) {
                    alltool_shm_t *e = (alltool_shm_t *)v;
                    if (e->magic == SHM_MAGIC && e->version == SHM_VERSION && e->initialized)
                        ok = 1;
                    munmap(v, st.st_size);
                }
            }
            // Always close the probe fd; attach() opens its own.
            close(fd);
            return ok ? 0 : -1;
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
    if (shm->magic != SHM_MAGIC || shm->version != SHM_VERSION || !shm->initialized) {
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
    if (ctx->my_predecessor >= ALLTOOL_MAX_PROCESSES) return -1;

    sem_t *sem = get_semaphore(ctx->shm);
    struct timespec start, now;
    clock_gettime(CLOCK_MONOTONIC, &start);

    while (1) {
        int state;
        // Short critical section only; never block on timedwait with the mutex held.
        if (sem_wait(sem) != 0) return -1;
        state = ctx->shm->states[ctx->my_predecessor];
        sem_post(sem);
        if (state == ALLTOOL_PROC_DONE) return 0;
        if (state == ALLTOOL_PROC_ERROR) return -1;

        if (timeout_ms >= 0) {
            clock_gettime(CLOCK_MONOTONIC, &now);
            long elapsed = (long)(now.tv_sec - start.tv_sec) * 1000
                + (long)(now.tv_nsec - start.tv_nsec) / 1000000;
            if (elapsed >= timeout_ms) return -1;
        }
        // Poll interval 1ms.
        struct timespec rq = { .tv_sec = 0, .tv_nsec = 1000000 };
        nanosleep(&rq, NULL);
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