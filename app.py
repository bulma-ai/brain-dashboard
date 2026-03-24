#!/usr/bin/env python3
"""Bulma's Brain Dashboard - Real-time system monitoring."""

import json
import os
import subprocess
import psutil
import time
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
            'total': round(mem.total / (1024**3), 2),  # GB
            'available': round(mem.available / (1024**3), 2),
            'used': round(mem.used / (1024**3), 2),
            'percent': mem.percent
        }
        
        # Disk usage
        disk = psutil.disk_usage('/')
        resources['disk'] = {
            'total': round(disk.total / (1024**3), 2),
            'used': round(disk.used / (1024**3), 2),
            'free': round(disk.free / (1024**3), 2),
            'percent': disk.percent
        }
        
        # Load average (Unix only)
        try:
            load1, load5, load15 = os.getloadavg()
            resources['load_avg'] = {'1min': round(load1, 2), '5min': round(load5, 2), '15min': round(load15, 2)}
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
                        'address': conn.laddr.ip if hasattr(conn.laddr, 'ip') else '0.0.0.0',
                        'protocol': 'TCP',
                        'status': conn.status,
                        'pid': conn.pid if conn.pid else 0,
                        'process': 'Unknown'
                    }
                    
                    # Get process name
                    if conn.pid:
                        try:
                            proc = psutil.Process(conn.pid)
                            port_info['process'] = proc.name()
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
        # Check for specific services
        service_checks = [
            ('OpenClaw Gateway', 'openclaw', 18789),
            ('Ollama', 'ollama', 11434),
            ('Brain Dashboard', 'app.py', 5000),
            ('SSH', 'sshd', 22),
            ('HTTP Server', 'httpd', 80),
            ('HTTPS Server', 'https', 443),
        ]
        
        found_pids = set()
        
        # Check processes
        for service_name, process_keyword, default_port in service_checks:
            found = False
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_name = proc.info['name'].lower() if proc.info['name'] else ''
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    
                    if process_keyword.lower() in proc_name or process_keyword.lower() in cmdline.lower():
                        if proc.info['pid'] not in found_pids:
                            found_pids.add(proc.info['pid'])
                            services.append({
                                'name': service_name,
                                'pid': str(proc.info['pid']),
                                'port': str(default_port),
                                'status': 'Running',
                                'type': 'system'
                            })
                            found = True
                            break
                except:
                    pass
        
        # Also check from network connections
        for conn in psutil.net_connections(kind='inet'):
            if conn.status == 'LISTEN':
                port = conn.laddr.port
                # Skip if already found
                if not any(s['port'] == str(port) for s in services):
                    service_name = 'Unknown'
                    if port == 22:
                        service_name = 'SSH'
                    elif port == 80:
                        service_name = 'HTTP'
                    elif port == 443:
                        service_name = 'HTTPS'
                    elif port == 5000:
                        service_name = 'Brain Dashboard'
                    elif port == 18789:
                        service_name = 'OpenClaw Gateway'
                    elif port == 11434:
                        service_name = 'Ollama'
                    elif port == 5900:
                        service_name = 'VNC'
                    elif port == 3000:
                        service_name = 'Node.js Dev'
                    elif port == 8080:
                        service_name = 'Web Server'
                    else:
                        service_name = f'Service ({port})'
                    
                    services.append({
                        'name': service_name,
                        'pid': str(conn.pid) if conn.pid else '—',
                        'port': str(port),
                        'status': 'Running',
                        'type': 'system'
                    })
        
        # Sort by port
        services.sort(key=lambda x: int(x['port']) if x['port'].isdigit() else 99999)
        
    except Exception as e:
        services.append({'name': 'Error', 'pid': '—', 'port': '—', 'status': str(e), 'type': 'error'})
    
    return services

def get_installed_tools():
    """Get list of installed tools with versions."""
    tools = []
    
    tool_checks = [
        ('openclaw', 'OpenClaw', ['openclaw', '--version']),
        ('gh', 'GitHub CLI', ['gh', '--version']),
        ('git', 'Git', ['git', '--version']),
        ('python3', 'Python 3', ['python3', '--version']),
        ('node', 'Node.js', ['node', '--version']),
        ('brew', 'Homebrew', ['brew', '--version']),
        ('docker', 'Docker', ['docker', '--version']),
        ('code', 'VS Code', ['code', '--version']),
    ]
    
    for cmd, name, version_cmd in tool_checks:
        try:
            result = subprocess.run(['which', cmd], capture_output=True, text=True)
            if result.returncode == 0:
                # Get version
                try:
                    ver_result = subprocess.run(version_cmd, capture_output=True, text=True, timeout=2)
                    version = ver_result.stdout.strip().split('\n')[0][:40] if ver_result.stdout else 'installed'
                    if not version and ver_result.stderr:
                        version = ver_result.stderr.strip().split('\n')[0][:40]
                except:
                    version = 'installed'
                tools.append({'name': name, 'command': cmd, 'version': version, 'status': '✅'})
            else:
                tools.append({'name': name, 'command': cmd, 'version': '—', 'status': '❌'})
        except:
            tools.append({'name': name, 'command': cmd, 'version': '—', 'status': '❌'})
    
    return tools

def get_network_info():
    """Get network information."""
    import socket
    
    info = {
        'public_ip': 'Unknown',
        'local_ip': 'Unknown',
        'hostname': 'Unknown',
        'mac_address': 'Unknown'
    }
    
    # Get local IP using socket (most reliable method)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        info['local_ip'] = s.getsockname()[0]
        s.close()
    except:
        pass
    
    # Fallback to ipconfig if socket fails
    if info['local_ip'] == 'Unknown':
        try:
            result = subprocess.run(['ipconfig', 'getifaddr', 'en0'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                info['local_ip'] = result.stdout.strip()
            else:
                result = subprocess.run(['ipconfig', 'getifaddr', 'en1'], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    info['local_ip'] = result.stdout.strip()
        except:
            pass
    
    try:
        # Get public IP
        result = subprocess.run(['curl', '-s', 'https://api.ipify.org'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            info['public_ip'] = result.stdout.strip()
    except:
        pass
    
    try:
        info['hostname'] = subprocess.run(['hostname'], capture_output=True, text=True).stdout.strip()
    except:
        pass
    
    # Get MAC address
    try:
        for interface, addrs in psutil.net_if_addrs().items():
            if interface in ['en0', 'en1', 'eth0']:
                for addr in addrs:
                    if addr.family == psutil.AF_LINK:
                        info['mac_address'] = addr.address
                        break
    except:
        pass
    
    return info

def get_process_list():
    """Get top processes by CPU and memory."""
    processes = []
    
    try:
        # Initialize CPU percent
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc.cpu_percent(interval=0.01)
            except:
                pass
        
        time.sleep(0.3)
        
        procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info', 'status']):
            try:
                pinfo = proc.info
                name = pinfo['name']
                
                # Skip kernel tasks
                if name in ['kernel_task', 'launchd', 'WindowServer', 'loginwindow', 'swapins']:
                    continue
                    
                cpu = pinfo['cpu_percent'] or 0
                memory = pinfo['memory_percent'] or 0
                memory_mb = (pinfo['memory_info'].rss / 1024 / 1024) if pinfo['memory_info'] else 0
                
                procs.append({
                    'pid': pinfo['pid'],
                    'name': name[:20],
                    'cpu': round(cpu, 1),
                    'memory': round(memory, 1),
                    'memory_mb': round(memory_mb, 0),
                    'status': pinfo.get('status', 'Unknown')
                })
            except:
                pass
        
        # Sort by memory and get top 15
        procs.sort(key=lambda x: (x['memory'], x['cpu']), reverse=True)
        processes = procs[:15]
        
    except Exception as e:
        processes = [{'error': str(e)}]
    
    return processes

@app.route('/')
def dashboard():
    """Main dashboard showing Bulma's brain."""
    
    # Load identity
    identity_content = read_file(WORKSPACE / 'IDENTITY.md')
    identity = parse_markdown_sections(identity_content) if identity_content else {}
    
    # Load user info
    user_content = read_file(WORKSPACE / 'USER.md')
    user = parse_markdown_sections(user_content) if user_content else {}
    
    # Load soul
    soul_content = read_file(WORKSPACE / 'SOUL.md')
    soul = parse_markdown_sections(soul_content) if soul_content else {}
    
    # Load tools
    tools_content = read_file(WORKSPACE / 'TOOLS.md')
    tools = parse_markdown_sections(tools_content) if tools_content else {}
    
    # Get available skills
    skills_dir = Path('/opt/homebrew/lib/node_modules/openclaw/skills')
    skills = []
    if skills_dir.exists():
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / 'SKILL.md'
                if skill_md.exists():
                    skill_content = skill_md.read_text()
                    name = skill_dir.name
                    desc = ''
                    for line in skill_content.split('\n')[:10]:
                        if line.strip() and not line.startswith('#'):
                            desc = line.strip()
                            break
                    skills.append({'name': name, 'description': desc})
    
    # System info
    system_info = {
        'workspace': str(WORKSPACE),
        'skills_count': len(skills),
        'git_user': os.popen('git config user.name').read().strip(),
        'github_user': 'bulma-ai',
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
        'resources': get_system_resources(),
        'ports': get_open_ports(),
        'services': get_running_services(),
        'processes': get_process_list(),
        'network': get_network_info(),
        'tools': get_installed_tools(),
        'timestamp': datetime.datetime.now().isoformat()
    })

@app.route('/api/brain')
def api_brain():
    """API endpoint returning brain data as JSON."""
    data = {
        'identity': parse_markdown_sections(read_file(WORKSPACE / 'IDENTITY.md')),
        'user': parse_markdown_sections(read_file(WORKSPACE / 'USER.md')),
        'soul': parse_markdown_sections(read_file(WORKSPACE / 'SOUL.md')),
        'tools': parse_markdown_sections(read_file(WORKSPACE / 'TOOLS.md')),
        'timestamp': datetime.datetime.now().isoformat()
    }
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
