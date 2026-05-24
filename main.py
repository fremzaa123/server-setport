import json
import os
import re
import subprocess
import sys

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---- config ----

SERVER = {
    "url":        os.environ.get("SERVER_URL", ""),
    "admin_user": os.environ.get("SERVER_ADMIN_USER", ""),
    "password":   os.environ.get("SERVER_PASSWORD", ""),
    "type":       os.environ.get("SERVER_TYPE", "hestia"),
}

KEY_MAP = {
    "w":       "app",
    "w1":      "app",
    "w2":      "app",
    "se":      "sell",
    "assets":  "assets",
    "sa":      "sa",
    "api":     "api",
    "apisell": "apisell",
    "apisa":   "apisa",
    "trans":   "trans",
    "bank":    "trans",
}

# ---- helpers ----

def is_vesta():
    return SERVER["type"].lower() == "vesta"

def log_entry(step, ok, message):
    return {"step": step, "ok": ok, "message": message}

def local_run(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip()

def local_read(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read(), ""
    except Exception as e:
        return "", str(e)

def local_write(path, content):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return ""
    except Exception as e:
        return str(e)

# ---- hestia API ----

def hestia_cmd(cmd, params):
    url = f"{SERVER['url']}/api/"
    data = {
        "user":       SERVER["admin_user"],
        "password":   SERVER["password"],
        "returncode": "json",
        "cmd":        cmd,
        **{f"arg{i+1}": v for i, v in enumerate(params)},
    }
    try:
        r = requests.post(url, data=data, verify=False, timeout=30)
        r.raise_for_status()
        return r.text.strip()
    except Exception as e:
        return str(e)

def add_web_domain(domain):
    step = f"hestia add {domain}"
    result = hestia_cmd("v-add-web-domain", [SERVER["admin_user"], domain])
    if "already exists" in result.lower():
        return log_entry(step, True, "มีอยู่แล้ว")
    if "error" in result.lower():
        return log_entry(step, False, result)
    return log_entry(step, True, "สำเร็จ")

def set_proxy_template(domain, template="my_api_template"):
    step = f"hestia template {domain}"
    result = hestia_cmd("v-change-web-domain-proxy-tpl", [SERVER["admin_user"], domain, template, "no"])
    if "error" in result.lower():
        return log_entry(step, False, result)
    return log_entry(step, True, template)

# ---- nginx ----

def nginx_conf2_path(domain):
    return f"/home/{SERVER['admin_user']}/conf/web/{domain}/nginx.conf_2"

def vesta_conf_path(domain):
    return f"/home/{SERVER['admin_user']}/conf/web/{domain}.nginx.conf"

def nginx_test_reload():
    step = "nginx test & reload"
    out, err = local_run("nginx -t 2>&1 && sudo systemctl restart nginx 2>&1")
    combined = out + err
    ok_signal = "syntax is ok" in combined.lower()
    if "failed" in combined.lower() or ("error" in combined.lower() and not ok_signal):
        return log_entry(step, False, combined)
    return log_entry(step, True, "reload สำเร็จ")

def set_nginx_port(domain, port):
    step = f"nginx port {domain}"
    path = vesta_conf_path(domain) if is_vesta() else nginx_conf2_path(domain)
    content, err = local_read(path)
    new_line = f"proxy_pass http://127.0.0.1:{port};"
    if err and not content:
        write_err = local_write(path, new_line)
        if write_err:
            return log_entry(step, False, write_err)
        return log_entry(step, True, f"port → {port}")
    pattern = r"proxy_pass\s+http://127\.0\.0\.1:\d+;"
    new_content = re.sub(pattern, new_line, content)
    if new_content == content and new_line not in content:
        return log_entry(step, False, "ไม่พบ proxy_pass ในไฟล์")
    write_err = local_write(path, new_content)
    if write_err:
        return log_entry(step, False, write_err)
    return log_entry(step, True, f"port → {port}")

def set_nginx_conf2_root(domain, fs_path):
    step = f"nginx.conf_2 root {domain}"
    if not fs_path:
        return log_entry(step, False, "ไม่มี path")
    path = nginx_conf2_path(domain)
    root_line = f"root {fs_path};"
    existing, err = local_read(path)
    if not err and existing.strip() == root_line:
        return log_entry(step, True, "ตั้งค่าไว้แล้ว")
    new_content = root_line
    write_err = local_write(path, new_content)
    return log_entry(step, not write_err, "เขียนไฟล์สำเร็จ" if not write_err else write_err)

def resolve_repo_path(domain, root_domain, repo_path, key_map):
    if domain == root_domain:
        return repo_path.get("app", "")
    prefix = domain.replace("." + root_domain, "").split(".")[0]
    key = key_map.get(prefix, "")
    return repo_path.get(key, "")

def ensure_nginx_conf2_for_web(root_domain, web_domains, repo_path, key_map):
    logs = []
    for d in web_domains:
        step = f"ensure base nginx.conf_2 {d}"
        path = nginx_conf2_path(d)
        fs_path = resolve_repo_path(d, root_domain, repo_path, key_map)
        existing, err = local_read(path)
        if fs_path:
            root_line = f"root {fs_path};"
            if not err and existing.strip() == root_line:
                logs.append(log_entry(step, True, "ตั้งค่าไว้แล้ว"))
                continue
            new_content = root_line
        else:
            if not err:
                logs.append(log_entry(step, True, "ตั้งค่าไว้แล้ว"))
                continue
            new_content = ""
        write_err = local_write(path, new_content)
        logs.append(log_entry(step, not write_err, "เขียนไฟล์สำเร็จ" if not write_err else write_err))
    return logs

# ---- domain processing ----

def process_web_domains(web_list, root_domain, repo_path, key_map, logs):
    if isinstance(web_list, str):
        web_list = [web_list]
    for d in web_list:
        logs.append(add_web_domain(d))
        if logs[-1]["ok"] and not is_vesta():
            logs.append(set_proxy_template(d, "my_react_dupicate_page_template"))
    if not is_vesta() and web_list and root_domain:
        logs.extend(ensure_nginx_conf2_for_web(root_domain, web_list, repo_path, key_map))

def process_api_domain(value, logs):
    d, port = value["domain"], value["port"]
    logs.append(add_web_domain(d))
    if logs[-1]["ok"] and not is_vesta():
        logs.append(set_proxy_template(d, "my_api_template"))
    logs.append(set_nginx_port(d, port))

def process_react_domain(key, value, repo_path, key_map, logs):
    domains_list = value if isinstance(value, list) else [value]
    fs_path = repo_path.get(key_map.get(key, key), "")
    for d in domains_list:
        logs.append(add_web_domain(d))
        if logs[-1]["ok"] and not is_vesta():
            logs.append(set_proxy_template(d, "my_react_dupicate_page_template"))
        if fs_path and not is_vesta():
            logs.append(set_nginx_conf2_root(d, fs_path))

def process_domain(domain_obj, repo_path, key_map, logs):
    root_domain = domain_obj.get("root", "")
    process_web_domains(domain_obj.get("web", []), root_domain, repo_path, key_map, logs)
    skip_keys = {"root", "web"}
    for key, value in domain_obj.items():
        if key in skip_keys:
            continue
        if isinstance(value, dict) and "port" in value:
            process_api_domain(value, logs)
        else:
            process_react_domain(key, value, repo_path, key_map, logs)

# ---- main ----

def main():
    json_file = sys.argv[1] if len(sys.argv) > 1 else "request.json"
    if not os.path.exists(json_file):
        print(json.dumps({"ok": False, "error": f"{json_file} not found"}))
        sys.exit(1)

    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    if "server_type" in data:
        SERVER["type"] = data["server_type"]

    repo_path = data.get("repo_path", {})
    logs = []
    for domain_obj in data.get("domains", []):
        process_domain(domain_obj, repo_path, KEY_MAP, logs)
    logs.append(nginx_test_reload())

    all_ok = all(e["ok"] for e in logs)
    print(json.dumps({"ok": all_ok, "log": logs}, ensure_ascii=False, indent=2))
    if not all_ok:
        sys.exit(1)

if __name__ == "__main__":
    main()
