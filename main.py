import json
import os
import re
import subprocess
import sys

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---- server credentials from env ----

SERVER = {
    "url":        os.environ.get("SERVER_URL", ""),
    "admin_user": os.environ.get("SERVER_ADMIN_USER", ""),
    "password":   os.environ.get("SERVER_PASSWORD", ""),
    "type":       os.environ.get("SERVER_TYPE", "hestia"),
}

# ---- helpers ----

def log_entry(step, ok, message):
    return {"step": step, "ok": ok, "message": message}

def is_vesta():
    return SERVER["type"].lower() == "vesta"

def hestia_cmd(cmd, params):
    url = f"{SERVER['url']}/api/v1"
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

# ---- hestia operations ----

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

# ---- key mapping (subdomain prefix / key → repo_path key) ----

KEY_MAP = {
    "w":      "app",
    "w1":     "app",
    "w2":     "app",
    "se":     "sell",
    "assets": "assets",
    "sa":     "sa",
    "api":    "api",
    "apisell":"apisell",
    "apisa":  "apisa",
    "trans":  "trans",
    "bank":   "trans",
}

# ---- nginx.conf_2 operations (local) ----

def nginx_conf2_path(domain):
    return f"/home/{SERVER['admin_user']}/conf/web/{domain}/nginx.conf_2"

def vesta_conf_path(domain):
    return f"/home/{SERVER['admin_user']}/conf/web/{domain}.nginx.conf"

def set_nginx_port(domain, port):
    step = f"nginx port {domain}"
    path = vesta_conf_path(domain) if is_vesta() else nginx_conf2_path(domain)
    content, err = local_read(path)
    if err and not content:
        new_content = f"proxy_pass http://127.0.0.1:{port};"
        write_err = local_write(path, new_content)
        if write_err:
            return log_entry(step, False, write_err)
        return log_entry(step, True, f"port → {port}")
    new_line = f"proxy_pass http://127.0.0.1:{port};"
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
    if not err and fs_path in existing:
        return log_entry(step, True, "ตั้งค่าไว้แล้ว")
    if not err and re.search(r"root\s+[^;]+;", existing):
        new_content = re.sub(r"root\s+[^;]+;", root_line, existing)
    elif not err and existing:
        new_content = existing.rstrip("\n") + "\n" + root_line
    else:
        new_content = root_line
    write_err = local_write(path, new_content)
    return log_entry(step, not write_err, "เขียนไฟล์สำเร็จ" if not write_err else write_err)

def resolve_repo_path(domain, root_domain, repo_path, key_map):
    if domain == root_domain:
        return ""
    prefix = domain.replace("." + root_domain, "").split(".")[0]
    key = key_map.get(prefix, "")
    return repo_path.get(key, "")

def ensure_base_nginx_conf2(root_domain, web_domains, repo_path=None, key_map=None):
    if repo_path is None:
        repo_path = {}
    if key_map is None:
        key_map = {}
    logs = []
    w_zone = "w." + root_domain

    # root domain → rewrite to w.
    step = f"ensure base nginx.conf_2 {root_domain}"
    path = nginx_conf2_path(root_domain)
    rewrite_line = f"rewrite ^/(.*)$ https://{w_zone}/$1 redirect;"
    existing, err = local_read(path)
    if not err and rewrite_line in existing:
        logs.append(log_entry(step, True, "ตั้งค่าไว้แล้ว"))
    else:
        new_content = (existing.rstrip("\n") + "\n" + rewrite_line) if (not err and existing) else rewrite_line
        write_err = local_write(path, new_content)
        logs.append(log_entry(step, not write_err, "เขียนไฟล์สำเร็จ" if not write_err else write_err))

    # other web subdomains → set root <path> or create empty
    for d in web_domains:
        if d == root_domain:
            continue
        step2 = f"ensure base nginx.conf_2 {d}"
        path2 = nginx_conf2_path(d)
        fs_path = resolve_repo_path(d, root_domain, repo_path, key_map)
        existing2, err2 = local_read(path2)

        if fs_path:
            root_line = f"root {fs_path};"
            if not err2 and fs_path in existing2:
                logs.append(log_entry(step2, True, "ตั้งค่าไว้แล้ว"))
                continue
            if not err2 and re.search(r"root\s+[^;]+;", existing2):
                new_content2 = re.sub(r"root\s+[^;]+;", root_line, existing2)
            elif not err2 and existing2:
                new_content2 = existing2.rstrip("\n") + "\n" + root_line
            else:
                new_content2 = root_line
        else:
            if not err2:
                logs.append(log_entry(step2, True, "ตั้งค่าไว้แล้ว"))
                continue
            new_content2 = ""

        write_err2 = local_write(path2, new_content2)
        logs.append(log_entry(step2, not write_err2, "เขียนไฟล์สำเร็จ" if not write_err2 else write_err2))

    return logs

def nginx_test_reload():
    step = "nginx test & reload"
    out, err = local_run("nginx -t 2>&1 && service nginx reload 2>&1")
    combined = out + err
    ok_signal = "syntax is ok" in combined.lower()
    if "failed" in combined.lower() or ("error" in combined.lower() and not ok_signal):
        return log_entry(step, False, combined)
    return log_entry(step, True, "reload สำเร็จ")

# ---- main ----

def process_domain(domain_obj, repo_path, key_map, logs):
    root_domain = domain_obj.get("root", "")

    # web list: add + react template, then ensure nginx.conf_2
    web_list = domain_obj.get("web", [])
    if isinstance(web_list, str):
        web_list = [web_list]
    for d in web_list:
        logs.append(add_web_domain(d))
        if logs[-1]["ok"] and not is_vesta():
            logs.append(set_proxy_template(d, "my_react_dupicate_page_template"))
    if not is_vesta() and web_list and root_domain:
        logs.extend(ensure_base_nginx_conf2(root_domain, web_list, repo_path, key_map))

    # other keys: API (dict with port) or react (string/list)
    skip_keys = {"root", "web"}
    for key, value in domain_obj.items():
        if key in skip_keys:
            continue
        if isinstance(value, dict) and "port" in value:
            d = value["domain"]
            port = value["port"]
            logs.append(add_web_domain(d))
            if logs[-1]["ok"] and not is_vesta():
                logs.append(set_proxy_template(d, "my_api_template"))
            logs.append(set_nginx_port(d, port))
        else:
            # react subdomain (string or list)
            domains_list = value if isinstance(value, list) else [value]
            rkey = key_map.get(key, key)
            fs_path = repo_path.get(rkey, "")
            for d in domains_list:
                logs.append(add_web_domain(d))
                if logs[-1]["ok"] and not is_vesta():
                    logs.append(set_proxy_template(d, "my_react_dupicate_page_template"))
                if fs_path and not is_vesta():
                    logs.append(set_nginx_conf2_root(d, fs_path))

def main():
    json_file = sys.argv[1] if len(sys.argv) > 1 else "request.json"
    if not os.path.exists(json_file):
        print(json.dumps({"ok": False, "error": f"{json_file} not found"}))
        sys.exit(1)

    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

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
