import math
import torch

def bytes_to_gb(x): 
    return x / (1024**3)

def print_header(title):
    print("\n" + "="*len(title))
    print(title)
    print("="*len(title))

def get_prop(obj, *names, default="N/A"):
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)
    return default

print_header("PyTorch & CUDA Info")
print("Torch version:", torch.__version__)
print("CUDA (in torch):", getattr(torch.version, "cuda", None))
print("cuDNN version:", torch.backends.cudnn.version())
print("CUDA available:", torch.cuda.is_available())

if not torch.cuda.is_available():
    raise SystemExit("CUDA not available. Aborting GPU diagnostics.")

device_id = torch.cuda.current_device()
props = torch.cuda.get_device_properties(device_id)

print_header("Device Properties")
print(f"Device index: {device_id}")
print(f"GPU name: {get_prop(props, 'name')}")
print(f"Compute capability: {get_prop(props, 'major')}.{get_prop(props, 'minor')}")
print(f"SM count (multiprocessors): {get_prop(props, 'multi_processor_count')}")
print(f"Total VRAM: {bytes_to_gb(get_prop(props, 'total_memory', default=0)):.2f} GB")
print(f"PCI Bus ID: {get_prop(props, 'pci_bus_id', 'pci_device_id', default='N/A')}")
print(f"Warp size: {get_prop(props, 'warp_size', 'warpSize', default='N/A')}")
print(f"Max threads / SM: {get_prop(props, 'max_threads_per_multi_processor', 'max_threads_per_multiprocessor', default='N/A')}")
print(f"Max threads / block: {get_prop(props, 'max_threads_per_block', 'maxThreadsPerBlock', default='N/A')}")
print(f"Max shared mem / block (bytes): {get_prop(props, 'shared_memory_per_block', 'sharedMemPerBlock', default='N/A')}")

# Memory snapshot
free_bytes, total_bytes = torch.cuda.mem_get_info()
reserved = torch.cuda.memory_reserved(device_id)
allocated = torch.cuda.memory_allocated(device_id)

print_header("CUDA Memory (Snapshot)")
print(f"Driver-reported total: {bytes_to_gb(total_bytes):.2f} GB")
print(f"Driver-reported free : {bytes_to_gb(free_bytes):.2f} GB")
print(f'Torch reserved       : {bytes_to_gb(reserved):.2f} GB')
print(f'Torch allocated      : {bytes_to_gb(allocated):.2f} GB')

# Optional NVML telemetry
try:
    import pynvml
    pynvml.nvmlInit()
    h = pynvml.nvmlDeviceGetHandleByIndex(device_id)
    temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
    pwr  = pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0
    pwr_lim = pynvml.nvmlDeviceGetEnforcedPowerLimit(h) / 1000.0
    sm_clock = pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_SM)
    mem_clock = pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_MEM)
    util = pynvml.nvmlDeviceGetUtilizationRates(h)

    print_header("NVML (Runtime Telemetry)")
    print(f"Temperature: {temp} °C")
    print(f"Power: {pwr:.1f} W  (limit {pwr_lim:.1f} W)")
    print(f"Clocks: SM {sm_clock} MHz, MEM {mem_clock} MHz")
    print(f"Utilization: GPU {util.gpu}%  MEM {util.memory}%")
except Exception as e:
    print_header("NVML (Runtime Telemetry)")
    print("pynvml not available or failed to query:", repr(e))
    print('Optional install: "C:\\Program Files\\Python311\\python.exe" -m pip install nvidia-ml-py3')

# Achieved TFLOPS benchmark via GEMM
def choose_problem_size(dtype: torch.dtype, mem_fraction: float = 0.25, cap: int = 16384, floor: int = 1024):
    dtype_size = torch.finfo(dtype).bits // 8
    free_now = torch.cuda.mem_get_info()[0]
    target_bytes = max(int(free_now * mem_fraction), 64 * 1024 * 1024)
    n = int((target_bytes / (3 * dtype_size)) ** 0.5)
    n = max(floor, min(cap, (n // 128) * 128))
    return n

@torch.inference_mode()
def matmul_tflops(n: int, dtype: torch.dtype):
    a = torch.randn((n, n), device="cuda", dtype=dtype)
    b = torch.randn((n, n), device="cuda", dtype=dtype)
    for _ in range(3):
        _ = a @ b
    torch.cuda.synchronize()
    t0 = torch.cuda.Event(enable_timing=True)
    t1 = torch.cuda.Event(enable_timing=True)
    t0.record()
    c = a @ b
    t1.record()
    torch.cuda.synchronize()
    ms = t0.elapsed_time(t1)
    secs = ms / 1000.0
    flops = 2.0 * n * n * n
    tflops = flops / secs / 1e12
    del a, b, c
    torch.cuda.empty_cache()
    return tflops, secs, n

print_header("Achieved TFLOPS (MatMul)")
torch.set_float32_matmul_precision("high")

dtypes_to_try = [torch.float16]
try:
    _ = torch.empty(1, device="cuda", dtype=torch.bfloat16)
    dtypes_to_try.insert(0, torch.bfloat16)
except Exception:
    pass
dtypes_to_try.append(torch.float32)

for dt in dtypes_to_try:
    try:
        n = choose_problem_size(dt)
        tflops, secs, n = matmul_tflops(n, dt)
        kind = "TF32/FP32" if dt == torch.float32 else ("BF16" if dt == torch.bfloat16 else "FP16")
        print(f"{kind}: N={n}  time={secs:.3f}s  achieved={tflops:.2f} TFLOPS")
    except torch.cuda.OutOfMemoryError:
        try:
            n = max(1024, choose_problem_size(dt, mem_fraction=0.10, cap=8192))
            tflops, secs, n = matmul_tflops(n, dt)
            kind = "TF32/FP32" if dt == torch.float32 else ("BF16" if dt == torch.bfloat16 else "FP16")
            print(f"{kind}: N={n}  time={secs:.3f}s  achieved={tflops:.2f} TFLOPS  (reduced size)")
        except Exception as e:
            print(f"{dt}: benchmark skipped due to error: {repr(e)}")
    except Exception as e:
        print(f"{dt}: benchmark skipped due to error: {repr(e)}")

print_header("Done")
