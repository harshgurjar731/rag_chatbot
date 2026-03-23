import os
import sys
import subprocess
import socket

# Disable Torch Dynamo globally to prevent segfaults on Windows
os.environ["TORCH_DYNAMO_DISABLE"] = "1"

def load_env():
    """Load environment variables from .env and then .env.local (as overrides)."""
    env_files = ['.env', '.env.local']
    for env_file in env_files:
        if not os.path.exists(env_file):
            if os.path.exists(os.path.join('..', env_file)):
                actual_file = os.path.join('..', env_file)
            else:
                print(f"Warning: {env_file} not found. Skipping.")
                continue
        else:
            actual_file = env_file

        print(f"Loading {env_file}...")
        with open(actual_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
    print("Environment variables loaded!")
    
    # Ensure DATA_DIRECTORY is absolute to prevent fragmentation across services
    data_dir = os.environ.get("DATA_DIRECTORY")
    if data_dir and not os.path.isabs(data_dir):
        # Resolve relative to the current working directory (project root)
        os.environ["DATA_DIRECTORY"] = os.path.abspath(data_dir)
        print(f"Resolved DATA_DIRECTORY to: {os.environ['DATA_DIRECTORY']}")

def kill_port(port, retries=5):
    """Kill any process listening on the given port, with retries."""
    import time
    for attempt in range(retries):
        try:
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True, text=True
            )
            killed = False
            for line in result.stdout.splitlines():
                if f':{port} ' in line and 'LISTENING' in line:
                    parts = line.strip().split()
                    pid = int(parts[-1])
                    print(f"  Killing process on port {port} (PID {pid})...")
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)],
                                   capture_output=True)
                    killed = True
            if killed:
                time.sleep(1.5)
            else:
                break  # No more processes on this port
        except Exception as e:
            print(f"  Warning: Could not kill process on port {port}: {e}")
            break

def is_port_in_use(port):
    """Check if a port is currently in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def main():
    if len(sys.argv) < 3:
        print("Usage: python launcher.py <working_directory> <script_name> [args...]")
        sys.exit(1)

    work_dir = sys.argv[1]
    script_name = sys.argv[2]
    args = sys.argv[3:]

    # Load environment variables
    load_env()

    # Check for --port in args and kill any existing process
    port = None
    for i, arg in enumerate(args):
        if arg in ('--port', '-p') and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except ValueError:
                pass

    if port and is_port_in_use(port):
        print(f"Port {port} is already in use. Freeing it...")
        kill_port(port)

    # Change to the working directory
    if os.path.exists(work_dir):
        print(f"Changing directory to: {work_dir}")
        os.chdir(work_dir)
    else:
        print(f"Error: Directory not found: {work_dir}")
        sys.exit(1)

    # Construct the command
    cmd = [sys.executable, script_name] + args
    print(f"Starting {script_name}...")
    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        print("\nService stopped.")
    except Exception as e:
        print(f"Error running service: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
