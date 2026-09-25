# Scope 25R — Network recovery

Initial Scope 25 access was blocked with an incomplete ARP neighbor for `192.168.1.118`. On resume, the project host was on `192.168.1.47/24` via `enp3s0`; the Pi neighbor was present and reachable. Ping and TCP/22 succeeded, and SSH access restored the existing Pi path. No network configuration change, scanner installation, Tailscale setup, or Internet scan was performed.
