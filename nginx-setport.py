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
    "url":        os.environ.get("HESTIA_URL", ""),
    "admin_user": os.environ.get("HESTIA_ADMIN_USER", ""),
    "password":   os.environ.get("HESTIA_PASSWORD", ""),
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

def section(name):
    return log_entry(f"=== {name} ===", True, "")

def local_run(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

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
    except requests.exceptions.Timeout:
        return "error: request timeout"
    except requests.exceptions.ConnectionError as e:
        return f"error: connection failed — {e}"
    except Exception as e:
        return f"error: {e}"

def add_web_domain(domain):
    step = f"hestia add {domain}"
    result = hestia_cmd("v-add-web-domain", [SERVER["admin_user"], domain])
    r = result.lower()
    if "exists" in r:
        return log_entry(step, True, "มีอยู่แล้ว")
    if "error" in r:
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

def nginx_precheck():
    out, err, rc = local_run("nginx -t 2>&1")
    combined = out + err
    if rc == 0:
        return None, []
    domains = re.findall(r"/conf/web/([^/]+)/", combined)
    return combined, list(dict.fromkeys(domains))

def nginx_test_reload():
    step = "nginx test & reload"
    out, err, rc = local_run("nginx -t 2>&1")
    if rc != 0:
        return log_entry(step, False, f"nginx -t failed: {(out + err).strip()}")
    _, err2, rc2 = local_run("sudo systemctl reload nginx")
    if rc2 != 0:
        return log_entry(step, False, f"reload failed: {err2.strip()}")
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
    pattern = r"proxy_pass\s+http://(127\.0\.0\.1|localhost):\d+;"
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
    write_err = local_write(path, root_line)
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
        fs_path = resolve_repo_path(d, root_domain, repo_path, key_map)
        existing, err = local_read(nginx_conf2_path(d))
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
        write_err = local_write(nginx_conf2_path(d), new_content)
        logs.append(log_entry(step, not write_err, "เขียนไฟล์สำเร็จ" if not write_err else write_err))
    return logs

# ---- domain processing ----

def process_web_domains(web_list, root_domain, repo_path, key_map, hestia_logs, nginx_logs):
    if isinstance(web_list, str):
        web_list = [web_list]
    ok_domains = []
    for d in web_list:
        hestia_logs.append(add_web_domain(d))
        if not hestia_logs[-1]["ok"]:
            continue
        if not is_vesta():
            hestia_logs.append(set_proxy_template(d, "my_react_dupicate_page_template"))
            if not hestia_logs[-1]["ok"]:
                continue
        ok_domains.append(d)
    if not is_vesta() and ok_domains and root_domain:
        nginx_logs.extend(ensure_nginx_conf2_for_web(root_domain, ok_domains, repo_path, key_map))

def process_api_domain(value, hestia_logs, nginx_logs):
    d, port = value["domain"], value["port"]
    hestia_logs.append(add_web_domain(d))
    if not hestia_logs[-1]["ok"]:
        return
    if not is_vesta():
        hestia_logs.append(set_proxy_template(d, "my_api_template"))
        if not hestia_logs[-1]["ok"]:
            return
    nginx_logs.append(set_nginx_port(d, port))

def process_react_domain(key, value, repo_path, key_map, hestia_logs, nginx_logs):
    domains_list = value if isinstance(value, list) else [value]
    fs_path = repo_path.get(key_map.get(key, key), "")
    for d in domains_list:
        hestia_logs.append(add_web_domain(d))
        if not hestia_logs[-1]["ok"]:
            continue
        if not is_vesta():
            hestia_logs.append(set_proxy_template(d, "my_react_dupicate_page_template"))
            if not hestia_logs[-1]["ok"]:
                continue
        if fs_path and not is_vesta():
            nginx_logs.append(set_nginx_conf2_root(d, fs_path))

def process_domain(domain_obj, repo_path, key_map, hestia_logs, nginx_logs):
    root_domain = domain_obj.get("root", "")
    process_web_domains(domain_obj.get("web", []), root_domain, repo_path, key_map, hestia_logs, nginx_logs)
    skip_keys = {"root", "web"}
    for key, value in domain_obj.items():
        if key in skip_keys:
            continue
        if isinstance(value, dict) and "port" in value:
            process_api_domain(value, hestia_logs, nginx_logs)
        else:
            process_react_domain(key, value, repo_path, key_map, hestia_logs, nginx_logs)

# ---- format parser ----

def parse_project_format(data):
    domain = data.get("domain", {})
    port = data.get("port", {})
    base = domain.get("base", "")

    api_keys = {"api", "apisa", "noti", "trans", "apisell"}
    react_keys = {"sa", "sell", "assets"}

    web_list = [base] + domain.get("web", []) if base else domain.get("web", [])
    domain_obj = {"root": base, "web": web_list}

    for key in api_keys:
        domains_list = domain.get(key, [])
        p = port.get(key)
        if domains_list and p:
            domain_obj[key] = {"domain": domains_list[0], "port": p}

    for key in react_keys:
        domains_list = domain.get(key, [])
        if domains_list:
            domain_obj[key] = domains_list[0] if len(domains_list) == 1 else domains_list

    return [domain_obj]

# ---- main ----

def main():
    json_file = sys.argv[1] if len(sys.argv) > 1 else "project.jsonc"
    if not os.path.exists(json_file):
        print(json.dumps({"ok": False, "error": f"{json_file} not found"}))
        sys.exit(1)

    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    if "server_type" in data:
        SERVER["type"] = data["server_type"]

    repo_path = data.get("repo_path", {})

    if "domain" in data and "domains" not in data:
        domains = parse_project_format(data)
    else:
        domains = data.get("domains", [])

    pre_err, broken_domains = nginx_precheck()
    if pre_err:
        reason = f"nginx broken before start — fix first: {pre_err}"
        if broken_domains:
            reason += f" | broken domains: {', '.join(broken_domains)}"
        print(json.dumps({"ok": False, "error": reason}))
        callback_url = data.get("callback_url_init_nginx")
        if callback_url:
            try:
                requests.post(callback_url, json={"success": False, "reason": reason}, timeout=10)
            except Exception:
                pass
        sys.exit(1)

    hestia_logs = []
    nginx_logs = []

    for domain_obj in domains:
        process_domain(domain_obj, repo_path, KEY_MAP, hestia_logs, nginx_logs)

    reload_log = nginx_test_reload()

    logs = (
        [section("hestia")] + hestia_logs +
        [section("nginx conf")] + nginx_logs +
        [section("nginx reload"), reload_log]
    )

    all_ok = all(e["ok"] for e in logs)
    print(json.dumps({"ok": all_ok, "log": logs}, ensure_ascii=False, indent=2))

    callback_url = data.get("callback_url_init_nginx")
    if callback_url:
        failed = [e for e in logs if not e["ok"]]
        reason = " | ".join(f"{e['step']}: {e['message']}" for e in failed) if failed else ""
        payload = {"success": all_ok, "reason": reason}
        try:
            requests.post(callback_url, json=payload, timeout=10)
        except Exception:
            pass

    if not all_ok:
        sys.exit(1)

if __name__ == "__main__":
    main()
