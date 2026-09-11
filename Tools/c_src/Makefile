CC = gcc
CFLAGS = -std=c11 -Wall -Wextra -O2 -fPIC -I.
LDFLAGS = -shared
LIBS = -lrt -lpthread

PREFIX = /home/debian/.config/alltool/bin

SHM_SOURCES = alltool_shm.c
COMPILER_SOURCES = alltool_compiler.c
SUDO_SOURCES = alltool_sudo.c
RUNNER_SOURCES = alltool_runner.c

SHM_LIB = $(PREFIX)/liballtool_shm.so
COMPILER_LIB = $(PREFIX)/liballtool_compiler.so
SUDO_LIB = $(PREFIX)/liballtool_sudo.so
RUNNER_BIN = $(PREFIX)/alltool_runner

all: $(SHM_LIB) $(COMPILER_LIB) $(SUDO_LIB) $(RUNNER_BIN)

$(SHM_LIB): $(SHM_SOURCES)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $< $(LIBS)

$(COMPILER_LIB): $(COMPILER_SOURCES)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $< $(LIBS)

$(SUDO_LIB): $(SUDO_SOURCES)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $< $(LIBS)

$(RUNNER_BIN): $(RUNNER_SOURCES) $(SHM_LIB) $(COMPILER_LIB) $(SUDO_LIB)
	$(CC) $(CFLAGS) -o $@ $< -L$(PREFIX) -lalltool_shm -lalltool_compiler -lalltool_sudo $(LIBS) -Wl,-rpath,$(PREFIX)

install: all
	mkdir -p $(PREFIX)
	cp $(SHM_LIB) $(COMPILER_LIB) $(SUDO_LIB) $(RUNNER_BIN) $(PREFIX)/

clean:
	rm -f $(SHM_LIB) $(COMPILER_LIB) $(SUDO_LIB) $(RUNNER_BIN)

.PHONY: all install clean