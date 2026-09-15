#!/bin/bash
# Build Lunar Randomizer for Java 8+ (Windows 7 friendly bytecode)
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/src"
OUT="$ROOT/out"
mkdir -p "$OUT"

# Prefer Java 8 if present; otherwise current javac with --release 8
JAVAC="javac"
if command -v javac >/dev/null 2>&1; then
  if javac --release 8 -version >/dev/null 2>&1; then
    RELEASE=(--release 8)
  else
    RELEASE=(-source 1.8 -target 1.8)
  fi
else
  echo "javac not found"
  exit 1
fi

echo "Compiling..."
find "$SRC" -name "*.java" > /tmp/lunar_sources.txt
"$JAVAC" "${RELEASE[@]}" -encoding UTF-8 -d "$OUT" @/tmp/lunar_sources.txt

echo "Creating jar..."
cd "$OUT"
jar cfe "$ROOT/LunarRandomizer.jar" lunar.randomizer.MainFrame $(find . -name "*.class" | sed 's|^\./||')
cd "$ROOT"

echo "Done: $ROOT/LunarRandomizer.jar"
echo "Run:  java -jar LunarRandomizer.jar"
