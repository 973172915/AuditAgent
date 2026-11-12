"""一键启动：FastAPI(8000) + Streamlit(8501)。"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    procs = []
    try:
        api = subprocess.Popen([
            sys.executable, "-m", "uvicorn", "app.api.main:app",
            "--host", "0.0.0.0", "--port", "8000",
        ], cwd=ROOT)
        procs.append(api)

        ui = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", "app/ui/streamlit_app.py",
            "--server.port", "8501", "--server.headless", "true",
        ], cwd=ROOT)
        procs.append(ui)

        print("API:  http://localhost:8000/docs")
        print("UI :  http://localhost:8501")
        print("Ctrl+C 停止")
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
