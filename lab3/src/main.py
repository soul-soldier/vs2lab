import subprocess
import sys
import time
import os
import threading

# ANSI color codes for readable output
COLORS = {
    'M1': '\033[94m', # Blue
    'M2': '\033[96m', # Cyan
    'M3': '\033[92m', # Green
    'R1': '\033[93m', # Yellow
    'R2': '\033[95m', # Magenta
    'RESET': '\033[0m'
}

def stream_output(process, prefix, color):
    """
    Reads stdout from a subprocess line-by-line and prints it 
    to the main console with a colored prefix.
    """
    for line in iter(process.stdout.readline, b''):
        try:
            # Decode bytes to string and strip trailing whitespace
            msg = line.decode('utf-8').rstrip()
            if msg:
                print(f"{color}[{prefix}] {msg}{COLORS['RESET']}")
        except ValueError:
            break

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    processes = []
    
    print("--- Initializing MapReduce Cluster ---")

    # Helper to launch a process and start a thread to monitor its output
    def launch_node(script_name, label, args=[], color_key='RESET'):
        cmd = [sys.executable, "-u", os.path.join(base_dir, script_name)] + args
        # We pipe stdout so we can intercept and tag it. 
        # We use "-u" for unbuffered python output to see prints immediately.
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        
        # Start a thread to read the output continuously
        t = threading.Thread(target=stream_output, args=(p, label, COLORS[color_key]))
        t.daemon = True # Thread dies if main dies
        t.start()
        
        processes.append(p)
        print(f"Started {label}")

    try:
        # 1. Start Reducers (Listeners)
        # They take an ID argument ("1" or "2")
        launch_node("reducer.py", "Reducer 1", ["1"], 'R1')
        launch_node("reducer.py", "Reducer 2", ["2"], 'R2')

        time.sleep(0.5) # Allow bind

        # 2. Start Mappers (Workers)
        # Mappers don't take arguments in your current code, 
        # but we track them logically here as 1, 2, 3
        launch_node("mapper.py", "Mapper 1", [], 'M1')
        launch_node("mapper.py", "Mapper 2", [], 'M2')
        launch_node("mapper.py", "Mapper 3", [], 'M3')

        time.sleep(0.5) # Allow connect

        # 3. Start Splitter (The Driver)
        # We run this in the foreground (no piping) so you can hit Enter.
        print("--------------------------------------")
        print("[System] Launching Splitter (Foreground)...")
        print("[System] Please interact with the Splitter prompt below:")
        print("--------------------------------------")
        
        # MODIFICATION: Add "text.txt" to the splitter_cmd list
        splitter_cmd = [sys.executable, "-u", os.path.join(base_dir, "splitter.py"), "text.txt"]
        subprocess.run(splitter_cmd)

    except KeyboardInterrupt:
        print("\n[System] Interrupted by user.")

    finally:
        print("\n--- Shutting down Cluster processes ---")
        for p in processes:
            p.terminate()
        print("[System] Done.")

if __name__ == "__main__":
    main()