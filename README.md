# server-setport

Python script สำหรับ setup domain บน Hestia/Vesta server — เพิ่ม web domain, set proxy template, เขียน nginx.conf_2

## Requirements

- Python 3.x
- nginx (ติดตั้งบน server)
- Hestia หรือ Vesta control panel

---

## ติดตั้งบน Server

### 1. Clone หรือ pull จาก Git

```bash
git clone <repo-url> /opt/server-setport
cd /opt/server-setport
```

หรือถ้า clone ไว้แล้ว:

```bash
cd /opt/server-setport && git pull
```

### 2. สร้างไฟล์ .env

```bash
cp .env.example .env
nano .env
```

กรอกค่าให้ครบ:

```env
SERVER_URL=https://YOUR_SERVER_IP:8083
SERVER_ADMIN_USER=admin
SERVER_PASSWORD=your_panel_password
```

---

## วิธีรัน

```bash
sh run.sh
```

หรือระบุ request file เอง:

```bash
sh run.sh my-request.json
```

---

## โครงสร้าง request.json

```json
{
  "server_type": "hestia",       // optional — default hestia, หรือ vesta
  "repo_path": {                 // map key → path จริงบน server
    "app":     "/home/www/fin_app/project",
    "sa":      "/home/www/fin_sa/project",
    "sell":    "/home/www/fin_sell/project",
    "assets":  "/home/www/fin_assets/project",
    "api":     "/home/www/fin_api/project",
    "apisa":   "/home/www/fin_apisa/project",
    "apisell": "/home/www/fin_apisell/project",
    "trans":   "/home/www/fin_trans/project"
  },
  "domains": [
    {
      "root": "domain.com",       // required — ใช้อ้างอิง subdomain เท่านั้น ไม่ได้ add เอง

      // "web" → React subdomains
      // script จะ: add domain + set template my_react_dupicate_page_template + เขียน root path ใน nginx.conf_2
      // root path lookup จาก repo_path ผ่าน KEY_MAP ตาม subdomain prefix
      //   domain.com       → repo_path["app"]
      //   w.domain.com     → repo_path["app"]
      //   w1.domain.com    → repo_path["app"]
      //   w2.domain.com    → repo_path["app"]
      //   se.domain.com    → repo_path["sell"]
      //   assets.domain.com → repo_path["assets"]
      //   sa.domain.com    → repo_path["sa"]
      "web": ["domain.com", "w.domain.com", "w1.domain.com", "assets.domain.com", "se.domain.com"],

      // key ใดก็ได้ + { domain, port } → API subdomain
      // script จะ: add domain + set template my_api_template + เขียน proxy_pass port ใน nginx.conf_2
      "api":     { "domain": "api.domain.com",     "port": 8081 },
      "apisell": { "domain": "apise.domain.com",   "port": 8082 },
      "apisa":   { "domain": "apisa.domain.com",   "port": 8083 },
      "trans":   { "domain": "trans.domain.com",   "port": 8084 },
      "noti":    { "domain": "noti.domain.com",    "port": 8085 }
    }
  ]
}
```

**`web`** — script จะ lookup `repo_path` ให้อัตโนมัติผ่าน `KEY_MAP` ตาม subdomain prefix เช่น `w` → `app`, `se` → `sell`, `assets` → `assets`

**API key ใดก็ได้** — ชื่อ key ไม่สำคัญ แค่ต้องมี `domain` และ `port`

---

## KEY_MAP (แก้ใน main.py)

mapping ระหว่าง web subdomain prefix กับ `repo_path` key:

```python
KEY_MAP = {
    "w": "app", "w1": "app", "w2": "app",
    "se": "sell",
    "assets": "assets",
    "sa": "sa",
    ...
}
```

ถ้า prefix เปลี่ยน เช่น `w` → `m` แก้ทั้ง `KEY_MAP` และ `web` list ใน request.json

---

## อัปเดต Script

```bash
cd /opt/server-setport
git pull
```

`.env` และ `request.json` ไม่ถูก track โดย git — ไม่หายเมื่อ pull
