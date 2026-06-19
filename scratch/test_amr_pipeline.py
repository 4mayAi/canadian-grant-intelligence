import os
import subprocess
import sys

def main():
    print("======================================================================")
    print("Starting AMR & Biotech Simulation Intelligence PoC Pipeline (Dry Run)")
    print("======================================================================")
    
    # Define paths
    workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_path = os.path.join("configs", "amr_simulation.json")
    main_script = os.path.join("generic_engine", "main.py")
    
    # Check if config exists
    full_config_path = os.path.join(workspace_dir, config_path)
    if not os.path.exists(full_config_path):
        print(f"Error: Config file not found at {full_config_path}")
        sys.exit(1)
        
    # Check if main script exists
    full_main_script = os.path.join(workspace_dir, main_script)
    if not os.path.exists(full_main_script):
        print(f"Error: Main engine script not found at {full_main_script}")
        sys.exit(1)
        
    print(f"Workspace Directory: {workspace_dir}")
    print(f"Config File: {config_path}")
    print(f"Engine Entrypoint: {main_script}")
    print("\nRunning the generic engine in dry-run mode...")
    
    # Run the command
    cmd = [sys.executable, main_script, "--config", config_path, "--dry-run"]
    
    # Execute the process
    try:
        result = subprocess.run(
            cmd,
            cwd=workspace_dir,
            capture_output=False, # Output directly to console
            text=True,
            check=True
        )
        print("\n======================================================================")
        print("Pipeline Execution Completed Successfully!")
        print("Please check docs/data/amr-simulation/ for generated outputs:")
        print("  - amr_insights.json")
        print("  - amr_kpis.json")
        print("  - manifest.json")
        print("  - social_card.png")
        print("======================================================================")
    except subprocess.CalledProcessError as e:
        print("\n======================================================================")
        print("Pipeline Execution Failed!")
        print(f"Exit code: {e.returncode}")
        print("======================================================================")
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
