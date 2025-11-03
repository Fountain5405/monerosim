# Makefile for libminingshim.so

CC = gcc
CFLAGS = -Wall -Wextra -fPIC -O2 -DNDEBUG -D_POSIX_C_SOURCE=199309L
LDFLAGS = -shared
LIBS = -lpthread -lm -ldl

SOURCES = libminingshim.c
TARGET = libminingshim.so

# Test configuration
TEST_CFLAGS = -Wall -Wextra -O0 -g -D_POSIX_C_SOURCE=199309L -I.
TEST_LIBS = -lpthread -lm -ldl

all: $(TARGET)

$(TARGET): $(SOURCES)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^ $(LIBS)

local-install: $(TARGET)
	mkdir -p ../mining_shim
	cp $(TARGET) ../mining_shim/ 2>/dev/null || true

# Testing targets
test: test-build test-unit test-integration

test-build:
	@echo "Running build tests..."
	cd tests && ./test_build.sh

test-unit: $(TARGET)
	@echo "Running unit tests..."
	$(CC) $(TEST_CFLAGS) -o tests/test_determinism tests/test_determinism.c $(SOURCES) $(TEST_LIBS)
	MINER_HASHRATE=1000000 AGENT_ID=1 SIMULATION_SEED=12345 MININGSHIM_TEST_MODE=1 tests/test_determinism

test-integration: $(TARGET)
	@echo "Running integration tests..."
	cd tests && python3 test_integration.py

test-e2e: $(TARGET)
	@echo "Running end-to-end tests..."
	cd tests && ./test_e2e.sh

# Individual test compilation
tests/test_determinism: tests/test_determinism.c $(SOURCES) libminingshim.h
	$(CC) $(TEST_CFLAGS) -o $@ $< $(SOURCES) $(TEST_LIBS)

# Clean test artifacts
clean-tests:
	rm -f tests/test_determinism

clean: clean-tests
	rm -f $(TARGET)

.PHONY: all local-install clean test test-build test-unit test-integration test-e2e clean-tests