#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Deploy anti-drone to Pi")
    parser.add_argument("--host", default="192.168.1.118")
    parser.add_argument("--user", default="pitan")
    parser.add_argument("--password", default="1234")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    
    try:
        import paramiko
    except ImportError:
        print("paramiko is required. Install it using pip install paramiko")
        sys.exit(1)

    print(f"Deploying to {args.host} as {args.user}...")
    if args.dry_run:
        print("Dry run complete.")
        return

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(args.host, username=args.user, password=args.password)
        sftp = ssh.open_sftp()
        
        # Helper to upload directory
        def upload_dir(local_path, remote_path):
            try:
                sftp.mkdir(remote_path)
            except IOError:
                pass
            for item in os.listdir(local_path):
                l_path = os.path.join(local_path, item)
                r_path = f"{remote_path}/{item}"
                if os.path.isfile(l_path):
                    print(f"Uploading {l_path} to {r_path}")
                    sftp.put(l_path, r_path)
                elif os.path.isdir(l_path):
                    upload_dir(l_path, r_path)

        remote_base = f"/home/{args.user}/anti_drone_deploy"
        try:
            sftp.mkdir(remote_base)
        except IOError:
            pass

        # Upload src/anti_drone
        local_src = os.path.join(os.path.dirname(__file__), '..', 'src', 'anti_drone')
        remote_src = f"{remote_base}/src/anti_drone"
        try:
            sftp.mkdir(f"{remote_base}/src")
        except IOError:
            pass
        upload_dir(local_src, remote_src)

        # Upload scripts
        for script in ['anti_drone_pi_servo_tracking.py', 'run_tracking.sh']:
            local_script = os.path.join(os.path.dirname(__file__), script)
            if os.path.exists(local_script):
                print(f"Uploading {script}...")
                sftp.put(local_script, f"{remote_base}/{script}")
                sftp.chmod(f"{remote_base}/{script}", 0o755)

        # Upload requirements
        local_reqs = os.path.join(os.path.dirname(__file__), '..', 'requirements-pi.txt')
        if os.path.exists(local_reqs):
            print(f"Uploading requirements-pi.txt...")
            sftp.put(local_reqs, f"{remote_base}/requirements-pi.txt")

        # Upload artifacts
        local_artifacts = os.path.join(os.path.dirname(__file__), '..', 'artifacts', 'deploy')
        if os.path.exists(local_artifacts):
            remote_artifacts = f"{remote_base}/artifacts/deploy"
            try:
                sftp.mkdir(f"{remote_base}/artifacts")
                sftp.mkdir(remote_artifacts)
            except IOError:
                pass
            upload_dir(local_artifacts, remote_artifacts)

        # Create venv and install
        print("Setting up virtual environment and installing dependencies...")
        stdin, stdout, stderr = ssh.exec_command(f"cd {remote_base} && python3 -m venv venv && ./venv/bin/pip install -r requirements-pi.txt")
        print(stdout.read().decode())
        print(stderr.read().decode())

        if args.run:
            print("Starting tracking...")
            stdin, stdout, stderr = ssh.exec_command(f"cd {remote_base} && ./run_tracking.sh")
            print(stdout.read().decode())
            print(stderr.read().decode())
            
    except Exception as e:
        print(f"Deployment failed: {e}")
    finally:
        ssh.close()

if __name__ == '__main__':
    main()
