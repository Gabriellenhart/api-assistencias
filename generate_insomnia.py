import os
import re
import json
import uuid

# Configuration
BASE_URL = "http://monitoramen1.vps.webdock.cloud"
API_DIR = r"c:\Users\PROJETOS-2\Arquivos\dev\projeto-sistema-assistencias\api_assistencias\api"
OUTPUT_FILE = "insomnia_collection.json"

# Prefix mapping from __init__.py
PREFIXES = {
    'auth': '/auth',
    'orcamentos': '/orcamentos',
    'chamados': '/chamados',
    'usuarios': '/usuarios',
    'clientes': '/clientes',
    'materiais': '/materiais',
    'servicos': '/servicos',
    'usinas': '/usinas',
    'logs': '/logs',
    'dashboard': '/dashboard-stats',
    'ordens_servico': '/ordens-servico',
    'configuracoes': '/config',
    'planejamento': '/planejamento',
    'updates': '/updates',
    'integracoes': '/integracoes',
    'lembretes': '/lembretes'
}

# Insomnia base structure
workspace_id = f"wrk_{uuid.uuid4().hex}"
insomnia_export = {
    "_type": "export",
    "__export_format": 4,
    "__export_date": "2024-05-22T00:00:00.000Z",
    "__export_source": "insomnia.desktop.app:v2023.5.0",
    "resources": [
        {
            "_id": workspace_id,
            "parentId": None,
            "modified": 1700000000000,
            "created": 1700000000000,
            "name": "Sistema Assistencias API",
            "description": "Auto-generated collection",
            "_type": "workspace"
        },
        {
            "_id": f"env_{uuid.uuid4().hex}",
            "parentId": workspace_id,
            "modified": 1700000000000,
            "created": 1700000000000,
            "name": "VPS Webdock",
            "data": {
                "base_url": BASE_URL,
                "access_token": ""
            },
            "_type": "environment"
        }
    ]
}

def scan_routes():
    # Walk through api directory
    for root, dirs, files in os.walk(API_DIR):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                module_name = file.replace('.py', '')
                file_path = os.path.join(root, file)
                
                # Determine prefix
                prefix = ""
                # Try to match module name to prefix map
                if module_name in PREFIXES:
                    prefix = PREFIXES[module_name]
                # Special case for auth
                if 'auth' in root:
                    prefix = '/auth'

                if not prefix and module_name != 'routes': # Skip random helper files
                     continue

                print(f"Scanning {module_name} (Prefix: {prefix})...")

                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Regex to find routes
                    # Pattern: @bp.route('/path', methods=['GET', 'POST'])
                    # OR @something.route('/path') (default GET)
                    
                    route_pattern = re.compile(r'@\w+\.route\(\s*[\'"]([^\'"]+)[\'"](?:,\s*methods=\[([^\].]+)\])?')
                    matches = route_pattern.findall(content)
                    
                    folder_id = None
                    if matches:
                        # Create folder for this module
                        folder_id = f"fld_{uuid.uuid4().hex}"
                        insomnia_export['resources'].append({
                            "_id": folder_id,
                            "parentId": workspace_id,
                            "modified": 1700000000000,
                            "created": 1700000000000,
                            "name": module_name.capitalize(),
                            "_type": "request_group"
                        })

                    for path, methods_str in matches:
                        if not methods_str:
                            methods = ['GET']
                        else:
                            methods = [m.strip(' "\'') for m in methods_str.split(',')]

                        for method in methods:
                            # Clean path
                            clean_path = path if path.startswith('/') else '/' + path
                            if clean_path == '/': clean_path = ''
                            
                            full_url = "{{ base_url }}" + prefix + clean_path

                            # Body generation (heuristic)
                            body = {}
                            if method in ['POST', 'PUT']:
                                body = {
                                    "mimeType": "application/json",
                                    "text": "{\n\t\"example\": \"value\"\n}"
                                }

                            # Auth header
                            headers = []
                            if 'login' not in clean_path:
                                headers.append({
                                    "name": "Authorization",
                                    "value": "Bearer {{ access_token }}"
                                })
                            
                            headers.append({"name": "Content-Type", "value": "application/json"})

                            insomnia_export['resources'].append({
                                "_id": f"req_{uuid.uuid4().hex}",
                                "parentId": folder_id,
                                "modified": 1700000000000,
                                "created": 1700000000000,
                                "url": full_url,
                                "name": f"{method} {clean_path or '/'}",
                                "description": f"Auto-generated for {module_name}",
                                "method": method,
                                "body": body,
                                "parameters": [],
                                "headers": headers,
                                "authentication": {},
                                "metaSortKey": -1700000000000,
                                "isPrivate": False,
                                "settingStoreCookies": True,
                                "settingSendCookies": True,
                                "settingDisableRenderRequestBody": False,
                                "settingEncodeUrl": True,
                                "settingRebuildPath": True,
                                "settingFollowRedirects": "global",
                                "_type": "request"
                            })

scan_routes()

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(insomnia_export, f, indent=4)

print(f"Generated {OUTPUT_FILE} with {len(insomnia_export['resources'])} resources.")
