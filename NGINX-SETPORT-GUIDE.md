# server-setport — คู่มือการใช้งาน

Python script สำหรับ setup domain อัตโนมัติบน Hestia Control Panel:
เพิ่ม web domain → set proxy template → เขียน nginx.conf_2 → restart nginx

---

## โครงสร้างโปรเจ็กต์

```
server-setport/
├── nginx-setport.py       ← script หลัก (CLI)
├── nginx-setport.sh       ← shell wrapper (ใช้งานจริง)
├── ins-module.sh          ← ติดตั้ง Python dependencies
├── requirements.txt       ← Python packages
└── project.jsonc          ← ตัวอย่าง config file
```

---

## ไฟล์ที่ต้องอัพขึ้น Server

```
nginx-setport.py
nginx-setport.sh
ins-module.sh
requirements.txt
```

> ไม่ต้องอัพ `project.jsonc` — ฝั่ง caller ส่งมาเอง

---

## ติดตั้ง (ทำครั้งเดียว)

### 1. วาง project ลง server

```bash
git clone <repo-url> /home/fin/server-setport
```

หรืออัพไฟล์ขึ้นตรงที่ `/home/fin/server-setport/`

### 2. ติดตั้ง Python modules

```bash
bash /home/fin/server-setport/ins-module.sh
```

สร้าง `.venv` และ install `requests` ให้พร้อม

### 3. สร้างไฟล์ .env

path: `/home/www/manager/fin-source/env/.env.<db_name>`

```env
HESTIA_URL=https://YOUR_SERVER_IP:8083
HESTIA_ADMIN_USER=admin
HESTIA_PASSWORD=your_panel_password
```

---

## การใช้งาน

### รันผ่าน shell wrapper

```bash
bash /home/fin/server-setport/nginx-setport.sh --nginx /path/to/project.jsonc
```

shell wrapper จะ:
1. ตรวจสอบ python3, nginx, conf dir
2. derive env file จาก `db_name` ใน JSON → `/home/www/manager/fin-source/env/.env.<db_name>`
3. โหลด env vars
4. รัน `nginx-setport.py`

ระบุ env file เองแทน auto-derive:

```bash
bash /home/fin/server-setport/nginx-setport.sh \
  --nginx /path/to/project.jsonc \
  --env /path/to/.env
```

### Output

```json
{
  "ok": true,
  "log": [
    { "step": "=== hestia ===", "ok": true, "message": "" },
    { "step": "hestia add domain.com", "ok": true, "message": "สำเร็จ" },
    { "step": "hestia template domain.com", "ok": true, "message": "my_react_dupicate_page_template" },
    { "step": "=== nginx conf ===", "ok": true, "message": "" },
    { "step": "ensure base nginx.conf_2 domain.com", "ok": true, "message": "เขียนไฟล์สำเร็จ" },
    { "step": "=== nginx restart ===", "ok": true, "message": "" },
    { "step": "nginx test & restart", "ok": true, "message": "restart สำเร็จ" }
  ]
}
```

---

## โครงสร้าง project.jsonc

```json
{
  "db_name": "staging_db_33",
  "domain": {
    "base":    "domain.com",
    "web":     ["w.domain.com", "w1.domain.com", "w2.domain.com"],
    "assets":  ["assets.domain.com"],
    "sa":      ["sa.domain.com"],
    "sell":    ["sell.domain.com"],
    "api":     ["api.domain.com"],
    "apisa":   ["apisa.domain.com"],
    "apisell": ["apisell.domain.com"],
    "noti":    ["noti.domain.com"],
    "trans":   ["trans.domain.com"]
  },
  "port": {
    "api":     8081,
    "apisa":   8082,
    "apisell": 8083,
    "noti":    8084,
    "trans":   8085
  },
  "repo_path": {
    "app":    "/home/www/fin_app/staging_db_33",
    "sa":     "/home/www/fin_sa/staging_db_33",
    "sell":   "/home/www/fin_sell/staging_db_33",
    "assets": "/home/www/fin_assets/staging_db_33",
    "api":    "/home/www/fin_api/staging_db_33",
    "apisa":  "/home/www/fin_apisa/staging_db_33",
    "trans":  "/home/www/fin_trans/staging_db_33"
  },
  "callback_url_init_nginx": "http://localhost:9000/callback"
}
```

---

## Field อธิบาย

| Field | Required | Description |
|-------|----------|-------------|
| `db_name` | ใช่ (CLI) | ใช้ derive env file path |
| `domain.base` | ไม่ | root domain หลัก |
| `domain.web` | ไม่ | subdomain ที่ใช้ react template |
| `domain.api/apisa/trans/...` | ไม่ | API domains |
| `port.api/apisa/...` | ถ้ามี api domain | port ที่ proxy ไป |
| `repo_path` | ไม่ | path ของ built files สำหรับเขียน nginx.conf_2 |
| `callback_url_init_nginx` | ไม่ | URL ที่จะ POST result กลับหลังเสร็จ |
| `server_type` | ไม่ | `hestia` (default) หรือ `vesta` |

---

## Subdomain → Template mapping

| Subdomain prefix | Hestia template |
|-----------------|-----------------|
| `w`, `w1`, `w2` | `my_react_dupicate_page_template` |
| `se`, `sa`, `sell` | `my_react_dupicate_page_template` |
| `assets` | `my_assets_template` |
| `api`, `apisa`, `trans`, `apisell`, `noti` | `my_api_template` |

---

## Subdomain → repo_path key mapping

| Subdomain prefix | repo_path key |
|-----------------|---------------|
| `w`, `w1`, `w2` | `app` |
| `se` | `sell` |
| `assets` | `assets` |
| `sa` | `sa` |
| `api` | `api` |
| `apisa` | `apisa` |
| `apisell` | `apisell` |
| `trans`, `bank` | `trans` |

---

## โฟลวการทำงาน

```
project.jsonc
     │
     ▼
nginx-setport.sh
  ├─ ตรวจสอบ python3, nginx, conf dir
  ├─ โหลด .env (auto-derive จาก db_name)
  └─ รัน nginx-setport.py
          │
          ▼
     nginx_precheck()
     ├─ nginx -t → ถ้า fail → หยุด + callback error
          │
          ▼
     สำหรับทุก domain:
     ├─ add_web_domain() → Hestia API
     ├─ set_proxy_template() → Hestia API
     └─ เขียน nginx.conf_2
          │
          ▼
     nginx -t → pass → systemctl restart nginx
          │
          ▼
     print JSON result + callback_url (ถ้ามี)
```

---

## Safety

- **nginx pre-check** — รัน `nginx -t` ก่อนเริ่มทุกครั้ง ถ้า fail หยุดทันที
- **guard** — เขียน nginx.conf_2 เฉพาะเมื่อ add domain + set template สำเร็จ
- **idempotent** — domain มีอยู่แล้วจะข้ามและทำขั้นต่อไป รันซ้ำได้
- **restart ปลอดภัย** — ผ่าน `nginx -t` ก่อนทุกครั้ง ไม่ restart ถ้า config ผิด

---

## Callback

ถ้ามี `callback_url_init_nginx` — script จะ POST result กลับหลังเสร็จ:

```json
{ "success": true, "reason": "" }
```

```json
{ "success": false, "reason": "hestia add api.domain.com: error ... | ..." }
```

---

## อัพเดท script

```bash
cd /home/fin/server-setport && git pull
bash ins-module.sh
```
