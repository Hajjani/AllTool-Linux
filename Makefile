PREFIX ?= /usr/local
BINDIR = $(PREFIX)/bin
LIBDIR = $(PREFIX)/lib/alltool
SHAREDIR = $(PREFIX)/share/alltool

HOME_CONFIG = $(HOME)/.config/alltool
HOME_BIN = $(HOME)/.config/alltool/bin
HOME_CACHE = $(HOME)/.config/alltool/cache
HOME_LOGS = $(HOME)/.config/alltool/logs

.PHONY: all build-c install-c install-user install-python install-config install uninstall test clean

all: build-c

build-c:
	@echo "Building C components..."
	$(MAKE) -C Tools/c_src

install-c: build-c
	@echo "Installing C libraries and binary to $(LIBDIR) and $(BINDIR)..."
	install -d $(LIBDIR) $(BINDIR)
	install -m 755 Tools/c_src/liballtool_shm.so $(LIBDIR)/
	install -m 755 Tools/c_src/liballtool_compiler.so $(LIBDIR)/
	install -m 755 Tools/c_src/liballtool_sudo.so $(LIBDIR)/
	install -m 755 Tools/c_src/alltool_runner $(BINDIR)/
	@echo "Run 'ldconfig' if installing system-wide"

install-python:
	@echo "Installing Python package..."
	pip3 install -e . --break-system-packages 2>/dev/null || pip3 install -e .

# User-space install for the installer.sh flow: no root, no pip, no network.
# Puts the C libraries where Tools/bindings.py actually loads them from
# (~/.config/alltool/bin) and drops in the default configs.
install-user: build-c install-config
	@echo "Installing C libraries and binary to $(HOME_BIN)..."
	install -d $(HOME_BIN)
	install -m 755 Tools/c_src/liballtool_shm.so $(HOME_BIN)/
	install -m 755 Tools/c_src/liballtool_compiler.so $(HOME_BIN)/
	install -m 755 Tools/c_src/liballtool_sudo.so $(HOME_BIN)/
	install -m 755 Tools/c_src/alltool_runner $(HOME_BIN)/

install-config:
	@echo "Creating user config directory at $(HOME_CONFIG)..."
	install -d $(HOME_BIN) $(HOME_CACHE) $(HOME_LOGS)
	install -m 644 Tools/c_src/alltool_shm.h $(HOME_CONFIG)/ 2>/dev/null || true
	install -m 644 .confs.json $(HOME_CONFIG)/.confs.json 2>/dev/null || true
	install -m 644 .help.json $(HOME_CONFIG)/.help.json 2>/dev/null || true

install: install-c install-python install-config
	@echo ""
	@echo "Installation complete!"
	@echo "Add $(HOME_BIN) to your PATH or run: alltool refresh"
	@echo ""

uninstall:
	@echo "Uninstalling AllTool..."
	@if [ -f $(HOME_BIN)/alltool_runner ]; then \
		$(HOME_BIN)/alltool_runner sudo-clear 2>/dev/null || true; \
	fi
	@python3 -m Tools un 2>/dev/null || true
	@rm -f $(BINDIR)/alltool_runner
	@rm -f $(LIBDIR)/liballtool_shm.so
	@rm -f $(LIBDIR)/liballtool_compiler.so
	@rm -f $(LIBDIR)/liballtool_sudo.so
	@rm -rf $(HOME_CONFIG)
	@pip3 uninstall -y alltool 2>/dev/null || true
	@echo "Uninstall complete."

test: install
	@echo "Running integration tests..."
	@./test_integration.sh

clean:
	$(MAKE) -C Tools/c_src clean
	rm -rf build dist *.egg-info
	rm -rf $(HOME_CONFIG)

# Development targets
dev-install: build-c
	@echo "Installing for development (user-space)..."
	install -d $(HOME_BIN) $(HOME_CACHE) $(HOME_LOGS)
	install -m 755 Tools/c_src/liballtool_shm.so $(HOME_BIN)/
	install -m 755 Tools/c_src/liballtool_compiler.so $(HOME_BIN)/
	install -m 755 Tools/c_src/liballtool_sudo.so $(HOME_BIN)/
	install -m 755 Tools/c_src/alltool_runner $(HOME_BIN)/
	install -m 644 .confs.json $(HOME_CONFIG)/.confs.json 2>/dev/null || true
	install -m 644 .help.json $(HOME_CONFIG)/.help.json 2>/dev/null || true
	pip3 install -e . --break-system-packages 2>/dev/null || pip3 install -e .
	@echo "Run 'alltool refresh' to update PATH"

dev-test:
	@echo "Testing development install..."
	@HOME=$(HOME) python3 alltool help
	@HOME=$(HOME) python3 alltool create /tmp/test_alltool_file.txt
	@HOME=$(HOME) python3 alltool sf
	@HOME=$(HOME) python3 alltool run /tmp/test.c 2>&1 | head -5
	@HOME=$(HOME) python3 alltool psg 12
	@HOME=$(HOME) python3 alltool hs /tmp/test_alltool_file.txt sha256
	@HOME=$(HOME) python3 alltool power pwst
	@HOME=$(HOME) python3 alltool requirement 2>&1 | tail -5
	@echo "Basic tests passed!"