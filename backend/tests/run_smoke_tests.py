import subprocess
import time
import urllib.request
import urllib.error
import sys
import os

def main():
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    python_exe = os.path.join(backend_dir, "venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = "python"
        
    print(f"Starting FastAPI server with {python_exe}...")
    server_process = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app.main:app", "--port", "8000"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for the server to be ready
    ready = False
    for i in range(15):
        time.sleep(1)
        try:
            with urllib.request.urlopen("http://localhost:8000/health", timeout=2) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            pass
            
    if not ready:
        print("Error: FastAPI server failed to start on http://localhost:8000")
        server_process.kill()
        out, err = server_process.communicate()
        print("Server stdout:", out.decode())
        print("Server stderr:", err.decode())
        sys.exit(1)
        
    print("FastAPI server is ready. Running smoke tests...")
    
    # Run the smoke test script
    smoke_test_script = os.path.join(backend_dir, "tests", "smoke_test.py")
    test_result = subprocess.run([python_exe, smoke_test_script], cwd=backend_dir)
    
    print("Shutting down FastAPI server...")
    server_process.terminate()
    try:
        server_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server_process.kill()
        
    print("Done!")
    sys.exit(test_result.returncode)

if __name__ == "__main__":
    main()
