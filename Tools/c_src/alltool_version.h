#ifndef ALLTOOL_VERSION_H
#define ALLTOOL_VERSION_H

/* Fallback version mirror for C code.
 *
 * Canonical version lives in `.confs.json` ("version" key) at the repo root.
 * - meson.build reads `.confs.json` at configure time (single source).
 * - This header is only the no-config fallback used when C code must invent
 *   a fresh config file (alltool_sudo_cache_credentials with missing/empty
 *   file). Keep it in sync with `.confs.json` when releasing.
 */
#define ALLTOOL_VERSION "3.2.0"

#endif /* ALLTOOL_VERSION_H */
