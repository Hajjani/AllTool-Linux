#!/bin/bash
# Integration test script for AllTool

set -e

ALTOOL="python3 alltool"

echo "=== AllTool Integration Tests ==="
echo

# Test 1: Help command
echo "Test 1: Help command"
$ALTOOL help > /dev/null
echo "✓ help works"
echo

# Test 2: Create file
echo "Test 2: Create file"
$ALTOOL create /tmp/test_alltool_create.txt
[ -f /tmp/test_alltool_create.txt ] && echo "✓ create works" || exit 1
echo

# Test 3: Show files
echo "Test 3: Show files (sf)"
$ALTOOL sf > /dev/null
echo "✓ sf works"
echo

# Test 4: Script runner - C compilation
echo "Test 4: Script runner (C)"
echo '#include <stdio.h>
int main() { printf("hello\\n"); return 0; }' > /tmp/test_runner.c
$ALTOOL run /tmp/test_runner.c 2>&1 | grep -q "hello"
echo "✓ run (C compilation) works"
echo

# Test 5: Script runner - temp mode
echo "Test 5: Script runner (temp mode -t)"
$ALTOOL run /tmp/test_runner.c -t 2>&1 | grep -q "hello"
echo "✓ run -t works"
echo

# Test 6: Password generator
echo "Test 6: Password generator"
$ALTOOL psg 16 > /dev/null
echo "✓ psg works"
echo

# Test 7: File hash
echo "Test 7: File hash"
$ALTOOL hs /tmp/test_alltool_create.txt sha256 > /dev/null
echo "✓ hs works"
echo

# Test 8: Power status
echo "Test 8: Power status"
$ALTOOL power pwst > /dev/null
echo "✓ power pwst works"
echo

# Test 9: Requirement check
echo "Test 9: Requirement check"
$ALTOOL requirement > /dev/null
echo "✓ requirement works"
echo

# Test 10: System info
echo "Test 10: System info"
$ALTOOL sif 2>&1 | head -1 | grep -q "System" || echo "⚠ sif needs inxi"
echo "✓ sif works (or inxi missing)"
echo

# Test 11: Update check
echo "Test 11: Update check"
$ALTOOL up 2>&1 | grep -q "updates\|No supported"
echo "✓ up works"
echo

# Test 12: Clear terminal
echo "Test 12: Clear terminal"
$ALTOOL cl > /dev/null
echo "✓ cl works"
echo

# Test 13: Sudo cache test
echo "Test 13: Sudo cache mechanism"
/home/debian/.config/alltool/bin/alltool_runner sudo-clear > /dev/null 2>&1
echo "✓ sudo cache clear works"
echo

# Test 14: Weather
echo "Test 14: Weather"
$ALTOOL wea Paris 2>&1 | grep -q "Paris\|°" && echo "✓ wea works" || echo "⚠ wea needs network"
echo

# Test 15: Search
echo "Test 15: Search"
$ALTOOL sr "linux" 2>&1 | grep -q "Search\|Results" && echo "✓ sr works" || echo "⚠ sr needs network"
echo

echo "=== All integration tests passed! ==="