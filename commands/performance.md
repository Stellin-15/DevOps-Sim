# Performance Engineering Command Reference

Source material for `scenarios/performance/`. Linux's performance
tutorial covers the first look (load, vmstat, iostat, top). This file is
the next step: finding *which code* is using the time, with profilers,
flame graphs, eBPF tools, and each runtime's own inspection commands.

## CPU Profiling with perf

```
sudo perf top                                  # live: hottest functions, system-wide
sudo perf top -p <pid>
sudo perf record -F 99 -g -p <pid> -- sleep 30 # sample stacks 99 times a second for 30s
sudo perf record -F 99 -a -g -- sleep 30       # all CPUs
sudo perf report --stdio | head -40
sudo perf stat -p <pid> sleep 10               # counters: cycles, instructions, context switches
```

## Flame Graphs

```
sudo perf script | stackcollapse-perf.pl | flamegraph.pl > flame.svg
```

Width is time on CPU; the y-axis is stack depth; left-to-right order is
alphabetical, not time. Look for the widest plateaus at the top.

## Python and Other Interpreters

```
py-spy top --pid <pid>
py-spy record -o profile.svg --pid <pid> --duration 30
py-spy dump --pid <pid>                        # every thread's current stack, once
python -X importtime app.py
python -m cProfile -s cumtime script.py | head -30
```

## The JVM

```
jcmd                                           # list Java processes
jcmd <pid> VM.flags
jcmd <pid> GC.heap_info
jcmd <pid> GC.class_histogram | head -20
jcmd <pid> Thread.print                        # thread dump
jcmd <pid> GC.heap_dump /tmp/heap.hprof
jstat -gcutil <pid> 1000 5                     # GC utilisation, every second, 5 times
asprof -d 30 -f flame.html <pid>               # async-profiler
```

## Go

```
go tool pprof -top http://localhost:6060/debug/pprof/profile?seconds=30
go tool pprof -top http://localhost:6060/debug/pprof/heap
go tool pprof -http=:8081 cpu.pprof
curl -s http://localhost:6060/debug/pprof/goroutine?debug=1 | head -30
go test -bench=. -benchmem ./...
```

## eBPF Tools (bcc and bpftrace)

```
sudo execsnoop-bpfcc                           # every new process
sudo opensnoop-bpfcc -p <pid>                  # files opened
sudo biolatency-bpfcc 10 1                     # disk I/O latency histogram
sudo runqlat-bpfcc 10 1                        # time waiting for a CPU
sudo tcplife-bpfcc                             # TCP sessions with duration and bytes
sudo offcputime-bpfcc -p <pid> 10              # where a process waits
sudo bpftrace -e 'tracepoint:syscalls:sys_enter_openat { @[comm] = count(); }'
```

## Waiting, Not Working

```
pidstat -w -p <pid> 1                          # context switches
pidstat -d 1                                   # I/O per process
iostat -x 1 3                                  # await, %util per device
sudo iotop -o                                  # processes doing I/O now
mpstat -P ALL 1 3                              # per-CPU, including %steal
```

## Benchmarks and Load

```
hyperfine 'command-a' 'command-b'
wrk -t4 -c100 -d30s --latency http://<host>/<path>
```
