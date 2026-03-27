"""
Shell Relay Extension: Cross-Agent Shell Execution.
Allows one agent to request a terminal command on another agent's host.
"""
def relay_command(from_agent, to_agent, command):
    print(f"[ShellRelay] Relaying command '{command}' from {from_agent} to {to_agent}")
    # Logic to post a command to the target agent's bus
    return {"status": "relayed", "target": to_agent}
