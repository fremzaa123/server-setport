# server-setport

Python script สำหรับ setup domain บน Hestia server — เพิ่ม web domain, set proxy template, เขียน nginx.conf_2

## Requirements

- Python 3.7+
- nginx (ติดตั้งบน server)
- Hestia control panel

---

## การติดตั้ง (ทำครั้งเดียว)

### 1. โหลดโปรเจ็กต์ลง server

```bash
git clone <repo-url> /home/fin/server-setport
```

### 2. ติดตั้ง Python modules

```bash
bash /home/fin/server-setport/ins-module.sh
```

สร้าง `.venv` และ install dependencies ให้พร้อม

### 3. สร้างไฟล์ .env

```env
HESTIA_URL='https://YOUR_SERVER_IP:8083'
HESTIA_ADMIN_USER='admin'
HESTIA_PASSWORD='your_panel_password'
```

---

## วิธีรัน

ตัวกลางยิงคำสั่ง:

```bash
bash /home/fin/server-setport/nginx-setport.sh --nginx /path/to/project.jsonc
```

`--nginx` required — ถ้าไม่ส่งมาจะ error ออกเลย

ระบุ env file อื่น (optional):

```bash
bash /home/fin/server-setport/nginx-setport.sh --nginx /path/to/project.jsonc --env /path/to/.env
```

---

## โครงสร้าง project.jsonc

รองรับ 2 format:

### Format 1 — Project format

```json
{
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
    "app":    "/home/www/fin_app/project",
    "sa":     "/home/www/fin_sa/project",
    "sell":   "/home/www/fin_sell/project",
    "assets": "/home/www/fin_assets/project",
    "api":    "/home/www/fin_api/project",
    "apisa":  "/home/www/fin_apisa/project",
    "trans":  "/home/www/fin_trans/project"
  },
  "callback_url_init_nginx": "http://localhost:8000/api/v1/project/init/nginx/1"
}
```

### Format 2 — Domains array format

```json
{
  "repo_path": { ... },
  "domains": [
    {
      "root": "domain.com",
      "web":  ["domain.com", "w.domain.com", "assets.domain.com"],
      "api":  { "domain": "api.domain.com", "port": 8081 },
      "trans":{ "domain": "trans.domain.com", "port": 8082 }
    }
  ]
}
```

---

## Callback

ถ้ามี `callback_url_init_nginx` ในไฟล์ — script จะ POST result กลับหลังเสร็จ:

```json
// success
{ "success": true, "reason": "" }

// fail
{ "success": false, "reason": "hestia add api.domain.com: 404 Not Found | ..." }
```

---

## KEY_MAP

mapping subdomain prefix → `repo_path` key:

```
w, w1, w2  → app
se         → sell
assets     → assets
sa         → sa
api        → api
apisa      → apisa
apisell    → apisell
trans      → trans
bank       → trans
```

---

## อัปเดต Script

```bash
cd /home/fin/server-setport && git pull
bash ins-module.sh
```
