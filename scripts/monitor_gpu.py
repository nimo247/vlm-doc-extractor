"""Sample NVIDIA device memory/utilization while running a command. Not a torch allocator measurement."""
import argparse
import csv
from io import StringIO
import json
from pathlib import Path
import subprocess
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("outputs/gpu_samples.json"))
    parser.add_argument("--interval",type=float,default=.5)
    parser.add_argument("command",nargs=argparse.REMAINDER)
    args=parser.parse_args()
    command=args.command[1:] if args.command and args.command[0]=="--" else args.command
    if not command or args.interval<=0:parser.error("Supply a command after -- and a positive interval")
    # Check availability before launching the requested workload.
    query=["nvidia-smi","--query-gpu=index,memory.used,utilization.gpu","--format=csv,noheader,nounits"]
    subprocess.run(query,check=True,capture_output=True,text=True)
    process=subprocess.Popen(command)
    samples=[];start=time.perf_counter()
    try:
        while process.poll() is None:
            result=subprocess.run(query,check=True,capture_output=True,text=True)
            for row in csv.reader(StringIO(result.stdout)):
                samples.append({"seconds":time.perf_counter()-start,"gpu_index":int(row[0]),"device_memory_mib":float(row[1]),"gpu_utilization_percent":float(row[2])})
            time.sleep(args.interval)
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=20)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps({"measurement":"sampled total device memory; includes other processes and may miss transient peaks","interval_seconds":args.interval,"command_exit_code":process.returncode,"samples":samples},indent=2))
    raise SystemExit(process.returncode)


if __name__=="__main__":main()
