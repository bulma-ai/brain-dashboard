#!/usr/bin/env python3
"""Bulma's Brain Dashboard - Real-time system monitoring."""

import json
import os
import subprocess
import psutil
import socket
from pathlib import Path
from flask import Flask, render_template, jsonify
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

def get_system_resources():
    """Get real-time system resource usage."""
    resources = {}
    
    try:
        # CPU usage
        resources['cpu_percent'] = psutil.cpu_percent(interval=0.5)
        resources['cpu_count'] = psutil.cpu_count()
        resources['cpu_freq'] = psutil.cpu_freq().current if psutil.cpu_freq() else 0
        
        # Memory usage
        mem = psutil.virtual_memory()
        resources['memory'] = {
            'total': mem.total / (1024**3),  # GB
            'available': mem.available / (1024**3),
            'used': mem.used / (1024**3),
            'percent': mem.percent
        }
        
        # Disk usage
        disk = psutil.disk_usage('/')
        resources['disk'] = {
            'total': disk.total / (1024**3),
            'used': disk.used / (1024**3),
            'free': disk.free / (1024**3),
            'percent': disk.percent
        }
        
        # Load average (Unix only)
        try:
            load1, load5, load15 = os.getloadavg()
            resources['load_avg'] = {'1min': load1, '5min': load5, '15min': load15}
        except:
            resources['load_avg'] = {'1min': 0, '5min': 0, '15min': 0}
            
    except Exception as e:
        resources['error'] = str(e)
    
    return resources

def get_open_ports():
    """Get all open ports and listening services."""
    ports = []
    
    try:
        # Get network connections
        connections = psutil.net_connections(kind='inet')
        
        for conn in connections:
            if conn.status == 'LISTEN':
                try:
                    port_info = {
                        'port': conn.laddr.port,
                        'address': conn.laddr.ip,
                        'protocol': 'TCP',
                        'status': conn.status,
                        'pid': conn.pid,
                        'process': 'Unknown'
                    }
                    
                    # Get process name
                    if conn.pid:
                        try:
                            proc = psutil.Process(conn.pid)
                            port_info['process'] = proc.name()
                            port_info['cmdline'] = ' '.join(proc.cmdline())[:50] if proc.cmdline() else ''
                        except:
                            pass
                    
                    ports.append(port_info)
                except:
                    pass
        
        # Sort by port number
        ports.sort(key=lambda x: x['port'])
        
    except Exception as e:
        ports.append({'error': str(e)})
    
    return ports

def get_running_services():
    """Get list of running services and ports."""
    services = []
    
    try:
        # Check OpenClaw Gateway
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'openclaw' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    services.append({
                        "name": "OpenClaw Gateway",
                        "pid": str(proc.info['pid']),
                        "port": "18789",
                        "status": "Running",
                        "type": "system"
                    })
                    break
            except:
                pass
        
        # Check Brain Dashboard (this app)
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                if 'brain-dashboard' in cmdline or 'app.py' in cmdline:
                    services.append({
                        "name": "Brain Dashboard",
                        "pid": str(proc.info['pid']),
                        "port": "5000",
                        "status": "Running",
                        "type": "app"
                    })
                    break
            except:
                pass
        
        # Check Ollama
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'ollama' in proc.info['name'].lower():
                    services.append({
                        "name": "Ollama",
                        "pid": str(proc.info['pid']),
                        "port": "11434",
                        "status": "Running",
                        "type": "ai"
                    })
                    break
            except:
                pass
        
        # Check common ports
        port_checks = {
            22: "SSH",
            80: "HTTP",
            443: "HTTPS",
            3000: "Node.js Dev",
            8080: "Web Server",
            5900: "VNC"
        }
        
        for conn in psutil.net_connections(kind='inet'):
            if conn.status == 'LISTEN' and conn.laddr.port in port_checks:
                service_name = port_checks[conn.laddr.port]
                # Check if not already added
                if not any(s['name'] == service_name for s in services):
                    services.append({
                        "name": service_name,
                        "pid": str(conn.pid) if conn.pid else "—",
                        "port": str(conn.laddr.port),
                        "status": "Running",
                        "type": "system"
                    })
        
    except Exception as e:
        services.append({"name": "Error", "error": str(e)})
    
    return services

def get_installed_tools():
    """Get list of installed tools with versions."""
    tools = []
    
    tool_checks = [
        ("openclaw", "OpenClaw", "openclaw --version"),
        ("gh", "GitHub CLI", "gh --version"),
        ("git", "Git", "git --version"),
        ("python3", "Python 3", "python3 --version"),
        ("node", "Node.js", "node --version"),
        ("brew", "Homebrew", "brew --version"),
        ("docker", "Docker", "docker --version"),
        ("code", "VS Code", "code --version"),
    ]
    
    for cmd, name, version_cmd in tool_checks:
        try:
            result = subprocess.run(['which', cmd], capture_output=True, text=True)
            if result.returncode == 0:
                # Get version
                try:
                    ver_result = subprocess.run(version_cmd.split(), capture_output=True, text=True, timeout=2)
                    version = ver_result.stdout.strip().split('\n')[0][:40] if ver_result.stdout else "installed"
                    if ver_result.stderr and not version:
                        version = ver_result.stderr.strip().split('\n')[0][:40]
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
        "hostname": "Unknown",
        "mac_address": "Unknown"
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
    
    # Get MAC address
    try:
        for interface, addrs in psutil.net_if_addrs().items():
            if interface in ['en0', 'en1', 'eth0']:
                for addr in addrs:
                    if addr.family == psutil.AF_LINK:
                        info["mac_address"] = addr.address
                        break
    except:
        pass
    
    return info

def get_process_list():
    """Get top processes by CPU and memory."""
    processes = []
    
    try:
        # Initialize CPU percent for all processes
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc.cpu_percent()
            except:
                pass
        
        # Wait a bit for CPU measurements
        import time
        time.sleep(0.5)
        
        procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info', 'status']):
            try:
                pinfo = proc.info
                # Skip system processes and kernel tasks
                name = pinfo['name']
                if name in ['kernel_task', 'launchd', 'WindowServer', 'loginwindow']:
                    continue
                    
                cpu = pinfo['cpu_percent'] or 0
                memory = pinfo['memory_percent'] or 0
                memory_mb = (pinfo['memory_info'].rss / 1024 / 1024) if pinfo['memory_info'] else 0
                
                # Only include processes using significant resources
                if cpu > 0.1 or memory > 0.1 or memory_mb > 50:
                    procs.append({
                        'pid': pinfo['pid'],
                        'name': name[:20],
                        'cpu': round(cpu, 1),
                        'memory': round(memory, 1),
                        'memory_mb': round(memory_mb, 0),
                        'status': pinfo.get('status', 'Unknown')
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            except:
                pass
        
        # Sort by memory usage (highest first) and get top 15
        procs.sort(key=lambda x: (x['memory'], x['cpu']), reverse=True)
        processes = procs[:15]
        
    except Exception as e:
        processes = [{'error': str(e)}]
    
    return processes

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
    
    # System info
    system_info = {
        "workspace": str(WORKSPACE),
        "skills_count": len(skills),
        "git_user": os.popen("git config user.name").read().strip(),
        "github_user": "bulma-ai",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return render_template('dashboard.html',
                         identity=identity,
                         user=user,
                         soul=soul,
                         tools=tools,
                         skills=skills,
                         system=system_info)

@app.route('/api/system')
def api_system():
    """API endpoint for real-time system data."""
    return jsonify({
        "resources": get_system_resources(),
        "ports": get_open_ports(),
        "services": get_running_services(),
        "processes": get_process_list(),
        "network": get_network_info(),
        "tools": get_installed_tools(),
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route('/api/brain')
def api_brain():
    """API endpoint returning brain data as JSON."""
    data = {
        "identity": parse_markdown_sections(read_file(WORKSPACE / "IDENTITY.md")),
        "user": parse_markdown_sections(read_file(WORKSPACE / "USER.md")),
        "soul": parse_markdown_sections(read_file(WORKSPACE / "SOUL.md")),
        "tools": parse_markdown_sections(read_file(WORKSPACE / "TOOLS.md")),
        "timestamp": datetime.datetime.now().isoformat()
    }
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
