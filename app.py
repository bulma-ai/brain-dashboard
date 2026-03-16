#!/usr/bin/env python3
"""Bulma's Brain Dashboard - A simple view into my configuration."""

import json
import os
import subprocess
from pathlib import Path
from flask import Flask, render_template
import datetime

app = Flask(__name__)

WORKSPACE = Path("/Users/bulma/.openclaw/workspace")

def read_file(path):
    """Read a file if it exists, return None otherwise."""
    try:
        return path.read_text()
    except FileNotFoundError:
        return None

def parse_markdown_sections(content):
    """Simple markdown section parser."""
    if not content:
        return {}
    sections = {}
    current_section = "General"
    current_content = []
    
    for line in content.split('\n'):
        if line.startswith('# '):
            if current_content:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = line[2:].strip()
            current_content = []
        elif line.startswith('## '):
            if current_content:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = line[3:].strip()
            current_content = []
        else:
            current_content.append(line)
    
    if current_content:
        sections[current_section] = '\n'.join(current_content).strip()
    
    return sections

def get_running_services():
    """Get list of running services and ports."""
    services = []
    try:
        # Get OpenClaw processes
        result = subprocess.run(['pgrep', '-a', 'openclaw'], capture_output=True, text=True)
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                parts = line.split(maxsplit=1)
                if len(parts) >= 2:
                    pid, cmd = parts
                    services.append({
                        "name": cmd.split('/')[-1] if '/' in cmd else cmd,
                        "pid": pid,
                        "port": "18789" if "gateway" in cmd else "—",
                        "status": "Running"
                    })
        
        # Get Python/Flask processes
        result = subprocess.run(['pgrep', '-a', 'Python'], capture_output=True, text=True)
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                if 'app.py' in line:
                    parts = line.split(maxsplit=1)
                    if len(parts) >= 2:
                        pid, cmd = parts
                        services.append({
                            "name": "Brain Dashboard (Flask)",
                            "pid": pid,
                            "port": "5000",
                            "status": "Running"
                        })
    except:
        pass
    return services

def get_installed_tools():
    """Get list of installed tools."""
    tools = []
    
    # Check for common tools
    tool_checks = [
        ("openclaw", "OpenClaw Gateway"),
        ("gh", "GitHub CLI"),
        ("git", "Git"),
        ("python3", "Python 3"),
        ("node", "Node.js"),
        ("brew", "Homebrew"),
        ("docker", "Docker"),
        ("code", "VS Code"),
        ("cursor", "Cursor"),
    ]
    
    for cmd, name in tool_checks:
        try:
            result = subprocess.run(['which', cmd], capture_output=True, text=True)
            if result.returncode == 0:
                # Get version
                try:
                    ver_result = subprocess.run([cmd, '--version'], capture_output=True, text=True, timeout=2)
                    version = ver_result.stdout.strip().split('\n')[0][:30] if ver_result.stdout else "installed"
                except:
                    version = "installed"
                tools.append({"name": name, "command": cmd, "version": version, "status": "✅"})
            else:
                tools.append({"name": name, "command": cmd, "version": "—", "status": "❌"})
        except:
            tools.append({"name": name, "command": cmd, "version": "—", "status": "❌"})
    
    return tools

def get_network_info():
    """Get network information."""
    info = {
        "public_ip": "Unknown",
        "local_ip": "Unknown",
        "hostname": "Unknown"
    }
    
    try:
        # Get public IP
        result = subprocess.run(['curl', '-s', 'https://api.ipify.org'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            info["public_ip"] = result.stdout.strip()
    except:
        pass
    
    try:
        # Get local IP
        result = subprocess.run(['ipconfig', 'getifaddr', 'en0'], capture_output=True, text=True)
        if result.returncode == 0:
            info["local_ip"] = result.stdout.strip()
        else:
            result = subprocess.run(['ipconfig', 'getifaddr', 'en1'], capture_output=True, text=True)
            if result.returncode == 0:
                info["local_ip"] = result.stdout.strip()
    except:
        pass
    
    try:
        info["hostname"] = subprocess.run(['hostname'], capture_output=True, text=True).stdout.strip()
    except:
        pass
    
    return info

def get_openclaw_status():
    """Get OpenClaw status."""
    try:
        result = subprocess.run(['openclaw', 'status'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            status_info = {}
            for line in lines:
                if 'Gateway' in line and 'port' in line.lower():
                    status_info['gateway'] = 'Running'
                if 'Dashboard' in line:
                    status_info['dashboard'] = line.strip()
            return status_info
    except:
        pass
    return {"status": "Unknown"}

@app.route('/')
def dashboard():
    """Main dashboard showing Bulma's brain."""
    
    # Load identity
    identity_content = read_file(WORKSPACE / "IDENTITY.md")
    identity = parse_markdown_sections(identity_content) if identity_content else {}
    
    # Load user info
    user_content = read_file(WORKSPACE / "USER.md")
    user = parse_markdown_sections(user_content) if user_content else {}
    
    # Load soul
    soul_content = read_file(WORKSPACE / "SOUL.md")
    soul = parse_markdown_sections(soul_content) if soul_content else {}
    
    # Load tools
    tools_content = read_file(WORKSPACE / "TOOLS.md")
    tools = parse_markdown_sections(tools_content) if tools_content else {}
    
    # Get available skills
    skills_dir = Path("/opt/homebrew/lib/node_modules/openclaw/skills")
    skills = []
    if skills_dir.exists():
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    skill_content = skill_md.read_text()
                    name = skill_dir.name
                    desc = ""
                    for line in skill_content.split('\n')[:10]:
                        if line.strip() and not line.startswith('#'):
                            desc = line.strip()
                            break
                    skills.append({"name": name, "description": desc})
    
    # Get running services
    services = get_running_services()
    
    # Get installed tools
    installed_tools = get_installed_tools()
    
    # Get network info
    network = get_network_info()
    
    # Get OpenClaw status
    openclaw_status = get_openclaw_status()
    
    # System info
    system_info = {
        "workspace": str(WORKSPACE),
        "skills_count": len(skills),
        "git_user": os.popen("git config user.name").read().strip(),
        "github_user": "bulma-ai",
        "services": services,
        "installed_tools": installed_tools,
        "network": network,
        "openclaw": openclaw_status,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return render_template('dashboard.html',
                         identity=identity,
                         user=user,
                         soul=soul,
                         tools=tools,
                         skills=skills,
                         system=system_info)

@app.route('/api/brain')
def api_brain():
    """API endpoint returning brain data as JSON."""
    data = {
        "identity": parse_markdown_sections(read_file(WORKSPACE / "IDENTITY.md")),
        "user": parse_markdown_sections(read_file(WORKSPACE / "USER.md")),
        "soul": parse_markdown_sections(read_file(WORKSPACE / "SOUL.md")),
        "tools": parse_markdown_sections(read_file(WORKSPACE / "TOOLS.md")),
        "services": get_running_services(),
        "installed_tools": get_installed_tools(),
        "network": get_network_info(),
        "timestamp": datetime.datetime.now().isoformat()
    }
    return json.dumps(data, indent=2)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
