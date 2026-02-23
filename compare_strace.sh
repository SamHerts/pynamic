#!/bin/bash
# compare_strace.sh
# Compare strace syscall timing for a Python module import on defiant1 vs defiant19.
#
# Usage: ./compare_strace.sh [module_name]
#   module_name defaults to libmodule0
#
# Output is printed to stdout and saved to strace_compare_<timestamp>/report.txt.

set -uo pipefail

MODULE="${1:-libmodule0}"
OUTDIR="strace_compare_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTDIR"

NODE1="defiant1"
NODE19="defiant19"
TOP_N=10

BUILD_DIR="$(pwd)/build"
SRUN_BASE="srun -A stf008 -t 5:00 -N 1 --ntasks-per-node 1"

REPORT="${OUTDIR}/report.txt"
exec > >(tee "$REPORT")

echo "=== strace comparison: import ${MODULE} ==="
echo "Date      : $(date)"
echo "Output dir: ${OUTDIR}"
echo ""

# ---------------------------------------------------------------------------
# 1. Capture strace from both nodes in parallel
# ---------------------------------------------------------------------------
echo "Capturing strace on ${NODE1} and ${NODE19} in parallel..."

$SRUN_BASE --nodelist="$NODE1" \
    strace -e trace=openat,mmap,mprotect -T \
    env PYTHONPATH="${BUILD_DIR}" python3 -c "import ${MODULE}" \
    >"${OUTDIR}/${NODE1}_stdout.txt" 2>"${OUTDIR}/${NODE1}_strace.txt" &
PID1=$!

$SRUN_BASE --nodelist="$NODE19" \
    strace -e trace=openat,mmap,mprotect -T \
    env PYTHONPATH="${BUILD_DIR}" python3 -c "import ${MODULE}" \
    >"${OUTDIR}/${NODE19}_stdout.txt" 2>"${OUTDIR}/${NODE19}_strace.txt" &
PID19=$!

STATUS1=0; STATUS19=0
wait $PID1  || STATUS1=$?
wait $PID19 || STATUS19=$?

[[ $STATUS1  -ne 0 ]] && echo "WARNING: ${NODE1}  srun exited with status ${STATUS1}"
[[ $STATUS19 -ne 0 ]] && echo "WARNING: ${NODE19} srun exited with status ${STATUS19}"
echo ""

for node in "$NODE1" "$NODE19"; do
    if [[ ! -s "${OUTDIR}/${node}_strace.txt" ]]; then
        echo "ERROR: no strace output captured for ${node}"
        exit 1
    fi
done

# ---------------------------------------------------------------------------
# Helper: parse "<syscall>(...) = N <time>" lines from a strace file.
# Fields extracted: syscall name, duration in seconds (from trailing <N.NNN>).
# ---------------------------------------------------------------------------

# summarize <file>  — per-syscall call count, total time, avg time
summarize() {
    awk '
    {
        p = index($0, "("); if (!p) next
        sc = substr($0, 1, p-1)
        last = $NF
        if (substr(last,1,1) != "<" || substr(last,length(last),1) != ">") next
        t = substr(last, 2, length(last)-2) + 0
        count[sc]++
        total[sc] += t
    }
    END {
        printf "  %-14s %8s %12s %10s\n", "syscall", "calls", "total(s)", "avg(ms)"
        printf "  %-14s %8s %12s %10s\n", "-------", "-----", "---------", "--------"
        for (sc in count)
            printf "  %-14s %8d %12.6f %10.4f\n",
                sc, count[sc], total[sc], total[sc]/count[sc]*1000
    }' "$1"
}

# compare <file1> <file2>  — side-by-side avg(ms) with delta and slowdown factor
compare() {
    awk -v n1="$NODE1" -v n19="$NODE19" '
    FNR == NR {
        p = index($0, "("); if (!p) next
        sc = substr($0, 1, p-1)
        last = $NF
        if (substr(last,1,1) != "<" || substr(last,length(last),1) != ">") next
        t = substr(last, 2, length(last)-2) + 0
        c1[sc]++; s1[sc] += t
        next
    }
    {
        p = index($0, "("); if (!p) next
        sc = substr($0, 1, p-1)
        last = $NF
        if (substr(last,1,1) != "<" || substr(last,length(last),1) != ">") next
        t = substr(last, 2, length(last)-2) + 0
        c19[sc]++; s19[sc] += t
    }
    END {
        for (sc in c1)  syscalls[sc] = 1
        for (sc in c19) syscalls[sc] = 1
        fmt = "  %-14s %14s %14s %12s %10s\n"
        printf fmt, "syscall", n1" avg(ms)", n19" avg(ms)", "delta(ms)", "factor"
        printf fmt, "-------", "-----------", "------------", "---------", "------"
        for (sc in syscalls) {
            a1  = (c1[sc]  > 0) ? s1[sc]  / c1[sc]  * 1000 : 0
            a19 = (c19[sc] > 0) ? s19[sc] / c19[sc] * 1000 : 0
            delta  = a19 - a1
            factor = (a1 > 0) ? a19 / a1 : 0
            printf "  %-14s %14.4f %14.4f %12.4f %9.2fx\n",
                sc, a1, a19, delta, factor
        }
    }' "$1" "$2"
}

# slowest <file> <n>  — top N individual calls by duration
slowest() {
    awk '
    {
        p = index($0, "("); if (!p) next
        last = $NF
        if (substr(last,1,1) != "<" || substr(last,length(last),1) != ">") next
        t = substr(last, 2, length(last)-2) + 0
        printf "%.6f %s\n", t, $0
    }' "$1" | sort -rn | head -"$2" | \
    awk '{printf "  %10.6f s  ", $1; $1=""; sub(/^ /, ""); print}'
}

# opened <file>  — unique successfully opened file paths
opened() {
    awk '/^openat\(/ && !/= -1 / {
        n = split($0, a, "\"")
        if (n >= 2 && length(a[2]) > 0) print a[2]
    }' "$1" | sort -u
}

# ---------------------------------------------------------------------------
# 2. Per-node syscall summary
# ---------------------------------------------------------------------------
echo "=== Per-node syscall summary ==="
echo "--- ${NODE1} ---"
summarize "${OUTDIR}/${NODE1}_strace.txt"
echo ""
echo "--- ${NODE19} ---"
summarize "${OUTDIR}/${NODE19}_strace.txt"
echo ""

# ---------------------------------------------------------------------------
# 3. Side-by-side comparison (delta + slowdown factor)
# ---------------------------------------------------------------------------
echo "=== Timing comparison (positive delta = ${NODE19} slower) ==="
compare "${OUTDIR}/${NODE1}_strace.txt" "${OUTDIR}/${NODE19}_strace.txt"
echo ""

# ---------------------------------------------------------------------------
# 4. Slowest individual calls
# ---------------------------------------------------------------------------
echo "=== Top ${TOP_N} slowest individual calls ==="
echo "--- ${NODE1} ---"
slowest "${OUTDIR}/${NODE1}_strace.txt" "$TOP_N"
echo ""
echo "--- ${NODE19} ---"
slowest "${OUTDIR}/${NODE19}_strace.txt" "$TOP_N"
echo ""

# ---------------------------------------------------------------------------
# 5. File-open diff
# ---------------------------------------------------------------------------
echo "=== Opened-file diff ==="

ONLY_1=$(comm -23 \
    <(opened "${OUTDIR}/${NODE1}_strace.txt") \
    <(opened "${OUTDIR}/${NODE19}_strace.txt"))

ONLY_19=$(comm -13 \
    <(opened "${OUTDIR}/${NODE1}_strace.txt") \
    <(opened "${OUTDIR}/${NODE19}_strace.txt"))

echo "--- Opened on ${NODE1} only ---"
[[ -z "$ONLY_1"  ]] && echo "  (none)" || echo "$ONLY_1"  | sed 's/^/  /'
echo ""
echo "--- Opened on ${NODE19} only ---"
[[ -z "$ONLY_19" ]] && echo "  (none)" || echo "$ONLY_19" | sed 's/^/  /'
echo ""

echo "Raw strace logs: ${OUTDIR}/${NODE1}_strace.txt  ${OUTDIR}/${NODE19}_strace.txt"
echo "Report saved  : ${REPORT}"
