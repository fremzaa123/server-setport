import os
import re

# ============================================================
#  ตั้งค่าตรงนี้
# ============================================================

ADMIN_USER = "admin"

# ── Case 1: root domain + subdomains ──────────────────────
# แต่ละ root จะถูก expand ด้วย SUBDOMAINS → ชี้ path เดียวกันทั้ง group

SUBDOMAINS = [""]

ROOT_DOMAINS = {
    
}

# ── Case 2: prefix domains ─────────────────────────────────
# domain จริง = prefix + brand_domain
# path จริง   = base_path/db_sub

# dash-style: pp-brand.mypiax.com / se-brand.mypiax.com
PREFIX_DASH = {
    "pp-": "/home/www/fin_sa",
    "se-": "/home/www/fin_sell",
    "my-": "/home/www/fin_sa",
}
BRAND_DASH = {
    "sebet.yum.bet":   "sebet_db_2",
    "ufalaosport.saugo.top":   "sebet_db_3",
    "ufalaos365.saugo.top":   "sebet_db_8",
    "ufalaos711.saugo.top":    "sebet_db_9",
    "ufalaos789.saugo.top": "sebet_db_10",
    "goodbett.saugo.top":  "sebet_db_11",
    "ufalaos777.saugo.top": "sebet_db_12",
    "ufaviplaos77.saugo.top": "sebet_db_13",
}

# dot-style: pp.brand.com / se.brand.com
PREFIX_DOT = {
    "pp.": "/home/www/fin_sa",
    "se.": "/home/www/fin_sell",
}
BRAND_DOT = {
    "heng36.pw": "sebet_db_4",
    "pablo666.com":  "sebet_db_7",
    "ufarc888.bet":      "sebet_db_16",
}

# ============================================================

def expand_root_domains(root_domains, subdomains):
    """Case 1: (domain, old_match, new_root)"""
    result = []
    for root, path in root_domains.items():
        for sub in subdomains:
            domain = root if sub == "" else f"{sub}.{root}"
            result.append((domain, root, path))
    return result


def expand_prefix_domains(prefix_base, brand_domains):
    """Case 2: (domain, old_match=None, new_root)"""
    result = []
    for prefix, base_path in prefix_base.items():
        for brand_domain, db_sub in brand_domains.items():
            domain = f"{prefix}{brand_domain}"
            path = f"{base_path}/{db_sub}"
            result.append((domain, None, path))
    return result


def fix_conf2(domain, old_match, new_root):
    path = f"/home/{ADMIN_USER}/conf/web/{domain}/nginx.conf_2"
    root_line = f"root {new_root};"

    conf_dir = os.path.dirname(path)
    if not os.path.exists(conf_dir):
        print(f"[SKIP]  {domain} — domain ไม่มีบน server")
        return

    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(root_line)
        print(f"[ADD]   {domain} → {root_line}")
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.strip():
        with open(path, "w", encoding="utf-8") as f:
            f.write(root_line)
        print(f"[ADD]   {domain} → {root_line}")
        return

    new_content = re.sub(r"root\s+[^;]+;", root_line, content)

    if new_content == content:
        if root_line in content:
            print(f"[SKIP]  {domain} — ตั้งค่าไว้แล้ว")
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(root_line)
            print(f"[ADD]   {domain} → {root_line}")
        return

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"[OK]    {domain} → root {new_root};")


def main():
    print("-" * 50)

    # Case 1
    case1 = expand_root_domains(ROOT_DOMAINS, SUBDOMAINS)
    for root, path in ROOT_DOMAINS.items():
        group = [(d, om, nr) for d, om, nr in case1 if om == root]
        print(f"\n[ROOT] {root} → {path} ({len(group)} domains)")
        for domain, old_match, new_root in group:
            fix_conf2(domain, old_match, new_root)

    # Case 2
    case2 = expand_prefix_domains(PREFIX_DASH, BRAND_DASH) + expand_prefix_domains(PREFIX_DOT, BRAND_DOT)
    if case2:
        print(f"\n[PREFIX] {len(case2)} domains")
        for domain, old_match, new_root in case2:
            fix_conf2(domain, old_match, new_root)

    print("-" * 50)
    #print("เสร็จแล้ว — รัน: sudo nginx -t && sudo systemctl reload nginx")


if __name__ == "__main__":
    main()
