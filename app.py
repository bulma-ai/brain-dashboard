#!/usr/bin/env python3
"""Bulma's Brain Dashboard - A simple view into my configuration."""

import json
import os
from pathlib import Path
from flask import Flask, render_template

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
                    # Extract name from first line
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
        "github_user": "bulma-ai"
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
    }
    return json.dumps(data, indent=2)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
