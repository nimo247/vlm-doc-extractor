"""Measure client end-to-end latency under explicit concurrency; GPU metrics require server-side measurement."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import statistics
import time
from urllib.parse import urlsplit
import httpx


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file",type=Path)
    parser.add_argument("--url",default="http://127.0.0.1:8000")
    parser.add_argument("--backend",default="baseline",choices=["baseline","ocr","vlm"])
    parser.add_argument("--requests",type=int,default=10)
    parser.add_argument("--concurrency",type=int,default=1)
    parser.add_argument("--warmup",type=int,default=1)
    parser.add_argument("--max-edge",type=int,default=1600)
    parser.add_argument("--output",type=Path,default=Path("outputs/benchmark.json"))
    args=parser.parse_args()
    if args.requests<1 or args.concurrency<1 or args.warmup<0:parser.error("Invalid request counts")
    data=args.file.read_bytes()
    def request(_):
        start=time.perf_counter()
        try:
            response=httpx.post(args.url.rstrip("/")+"/api/parse",params={"backend":args.backend,"max_edge":args.max_edge},files={"file":(args.file.name,data)},timeout=240,trust_env=urlsplit(args.url).hostname not in {"localhost","127.0.0.1","::1"})
            response.raise_for_status();result=response.json()
            return {"seconds":time.perf_counter()-start,"pages":result["metadata"]["page_count"],"ok":True}
        except Exception as exc:return {"seconds":time.perf_counter()-start,"pages":0,"ok":False,"error":type(exc).__name__}
    for i in range(args.warmup):request(i)
    start=time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:measurements=list(pool.map(request,range(args.requests)))
    elapsed=time.perf_counter()-start
    times=sorted(m["seconds"] for m in measurements if m["ok"])
    p95=times[min(len(times)-1,max(0,__import__('math').ceil(.95*len(times))-1))] if times else None
    report={"backend":args.backend,"resolution":args.max_edge,"requests":args.requests,"concurrency":args.concurrency,"warmup":args.warmup,"successful_requests":len(times),"failed_requests":args.requests-len(times),"median_seconds":statistics.median(times) if times else None,"p95_seconds":p95,"pages_per_minute":60*sum(m["pages"] for m in measurements)/elapsed,"wall_seconds":elapsed,"peak_gpu_memory_bytes":None,"gpu_memory_note":"Not observable from this HTTP client. Measure on the model server; nvidia-smi polling gives sampled process memory, not torch allocation peaks.","measurements":measurements}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
