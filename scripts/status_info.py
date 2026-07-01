#!/usr/bin/env python3
"""
CIVERS Service Status Inspector

Queries Docker Compose to list all running containers, their status,
their active CONFIG_ENVIRONMENT, and their KAFKA_BOOTSTRAP_SERVERS.
"""

import subprocess
import json
import sys

# ANSI Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def get_running_containers() -> list[dict]:
    """Retrieve list of project containers using docker compose ps."""
    try:
        res = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            capture_output=True,
            text=True,
            check=True
        )
        stdout = res.stdout.strip()
        if not stdout:
            return []
            
        try:
            # Try parsing as a single JSON structure
            parsed = json.loads(stdout)
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict)]
            elif isinstance(parsed, dict):
                return [parsed]
            return []
        except json.JSONDecodeError:
            # Fallback: Try parsing as JSON lines
            containers = []
            for line in stdout.split("\n"):
                if line.strip():
                    try:
                        parsed = json.loads(line)
                        if isinstance(parsed, dict):
                            containers.append(parsed)
                        elif isinstance(parsed, list):
                            containers.extend([x for x in parsed if isinstance(x, dict)])
                    except json.JSONDecodeError:
                        pass
            return containers
    except Exception as e:
        print(f"{Colors.FAIL}❌ Failed to query docker compose: {e}{Colors.ENDC}")
        return []


def inspect_container_env(container_name: str) -> dict[str, str]:
    """Inspect container to extract CONFIG_ENVIRONMENT and KAFKA_BOOTSTRAP_SERVERS."""
    result = {
        "CONFIG_ENVIRONMENT": "N/A",
        "KAFKA_BOOTSTRAP_SERVERS": "N/A"
    }
    try:
        res = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(res.stdout)
        if not data:
            return result
            
        env_list = data[0].get("Config", {}).get("Env", [])
        for env in env_list:
            if "=" in env:
                k, v = env.split("=", 1)
                if k in result:
                    result[k] = v
    except Exception:
        pass
    return result


def main():
    print(f"\n{Colors.BOLD}{Colors.HEADER}========================================================================={Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}                  CIVERS CONTAINER SERVICES INVENTORY                    {Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}========================================================================={Colors.ENDC}\n")

    raw_containers = get_running_containers()
    # Filter out invalid or empty items to prevent attribute errors
    containers = [
        c for c in raw_containers 
        if isinstance(c, dict) and (c.get("Name") or c.get("name") or c.get("Service") or c.get("service"))
    ]

    if not containers:
        print("   ℹ️  No containers are currently running for this project.")
        print(f"      Run {Colors.CYAN}make dev{Colors.ENDC} to spin up the stack.\n")
        sys.exit(0)

    # Table Header
    print(f" {Colors.BOLD}{'Service':<20} | {'Container Name':<28} | {'Status':<10} | {'Config Env':<12} | {'Kafka Bootstrap'}{Colors.ENDC}")
    print(f" {'-'*20}-+-{'-'*28}-+-{'-'*10}-+-{'-'*12}-+-{'-'*25}")

    for item in containers:
        # Handle field names differing across compose versions (e.g. Service/Service, Name/Names)
        service = item.get("Service") or item.get("service") or "unknown"
        name = item.get("Name") or item.get("name") or "unknown"
        state = item.get("State") or item.get("state") or "unknown"

        # Check env variables of the container
        env = inspect_container_env(name)
        config_env = env["CONFIG_ENVIRONMENT"]
        kafka_bootstrap = env["KAFKA_BOOTSTRAP_SERVERS"]

        # Color-code status
        state_color = Colors.GREEN if state in ["running", "up"] else Colors.WARNING
        if "exit" in state or "fail" in state:
            state_color = Colors.FAIL

        # Format print row
        print(f" {Colors.BLUE}{service:<20}{Colors.ENDC} | "
              f"{name:<28} | "
              f"{state_color}{state:<10}{Colors.ENDC} | "
              f"{Colors.CYAN}{config_env:<12}{Colors.ENDC} | "
              f"{Colors.BOLD}{kafka_bootstrap}{Colors.ENDC}")

    print(f"\n{Colors.BOLD}{Colors.HEADER}========================================================================={Colors.ENDC}\n")


if __name__ == "__main__":
    main()
