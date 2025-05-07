import torch
import os

print("="*50)
print("CUDA Check")
print("="*50)
print(f"CUDA Available: {torch.cuda.is_available()}")
print(f"CUDA Device Count: {torch.cuda.device_count()}")

if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        device = torch.cuda.get_device_properties(i)
        print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
        print(f"Memory Size: {device.total_memory / 1024 / 1024 / 1024:.2f} GB")
else:
    print("No GPU available")

print("\n" + "="*50)
print("FAISS Check")
print("="*50)
try:
    import faiss
    print("FAISS import successful")
    print(f"FAISS version: {faiss.__version__}")
    
    # Check if GPU support is available
    try:
        res = faiss.StandardGpuResources()
        print("FAISS GPU support: Yes")
    except Exception as e:
        print(f"FAISS GPU support: No (Error: {str(e)})")
        
except ImportError as e:
    print(f"FAISS import failed: {str(e)}")
    print("\nPossible solutions:")
    print("1. Try installing with conda: conda install -c conda-forge faiss-gpu")
    print("2. Or install CPU version: conda install -c conda-forge faiss-cpu")

print("\n" + "="*50)
print("Environment Info")
print("="*50)
print(f"Python path: {os.sys.executable}")
print(f"Working directory: {os.getcwd()}") 