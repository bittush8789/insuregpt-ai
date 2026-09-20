# AWS EC2 Deployment Guide — InsureGPT

Ye guide aapko **InsureGPT** ko AWS EC2 (Ubuntu 22.04 / 24.04 LTS) par step-by-step deploy karne ka complete aur aasan process batati hai.

---

## 📋 Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [Step 1: AWS EC2 Instance Launch Karein](#step-1-aws-ec2-instance-launch-karein)
3. [Step 2: EC2 Instance se Connect Karein](#step-2-ec2-instance-se-connect-karein)
4. [Step 3: Server Packages & Docker Install Karein](#step-3-server-packages--docker-install-karein)
5. [Step 4: Project Code Clone ya Transfer Karein](#step-4-project-code-clone-ya-transfer-karein)
6. [Step 5: Production .env File Configure Karein](#step-5-production-env-file-configure-karein)
7. [Step 6: Method A — Docker Compose se Run Karein (Recommended)](#step-6-method-a--docker-compose-se-run-karein-recommended)
8. [Step 7: Method B — Native Systemd Service & Uvicorn](#step-7-method-b--native-systemd-service--uvicorn)
9. [Step 8: Nginx Reverse Proxy & SSL Setup (Domain & Port 80/443)](#step-8-nginx-reverse-proxy--ssl-setup-domain--port-80443)
10. [Step 9: Testing & Health Verification](#step-9-testing--health-verification)
11. [Troubleshooting & FAQs](#troubleshooting--faqs)

---

## 1. Prerequisites

Aapke paas ready hona chahiye:
- Active **AWS Account**.
- **SSH Key Pair** (`.pem` file) instance login ke liye.
- API Keys:
  - `GROQ_API_KEY` (Groq Console se)
  - `PINECONE_API_KEY` (Pinecone Console se)
  - `TAVILY_API_KEY` (Tavily Console se - optional)

---

## Step 1: AWS EC2 Instance Launch Karein

1. **AWS Management Console** open karein aur **EC2** service par jayein.
2. **Launch Instance** par click karein:
   - **Name**: `insuregpt-production`
   - **OS Image (AMI)**: **Ubuntu Server 24.04 LTS** (ya 22.04 LTS) — 64-bit (x86_64).
   - **Instance Type**: 
     - *Recommended*: **`t3.medium`** (2 vCPU, 4 GB RAM) — MySQL + FastAPI + Vector embeddings smoothly run karne ke liye.
     - *Minimum*: **`t3.small`** (2 vCPU, 2 GB RAM).
   - **Key Pair**: Apna existing key pair select karein ya new create karke download karein (`insuregpt-key.pem`).
3. **Network & Security Group Settings**:
   - **Allow SSH traffic** from: `My IP` (port 22).
   - **Allow HTTP traffic** from the internet (port 80).
   - **Allow HTTPS traffic** from the internet (port 443).
   - **Custom TCP Rule** add karein:
     - **Port**: `8000`
     - **Source**: `0.0.0.0/0` (Anywhere) — Direct application test karne ke liye.
4. **Storage (Volume)**:
   - General Purpose SSD (`gp3`): **20 GB** ya **30 GB**.
5. **Launch Instance** par click karein.

---

## Step 2: EC2 Instance se Connect Karein

Apne local terminal (PowerShell ya Bash) mein jayein jahan aapki `.pem` key saved hai:

```bash
# File permissions set karein (Linux/Mac)
chmod 400 insuregpt-key.pem

# SSH login command
ssh -i "insuregpt-key.pem" ubuntu@<YOUR-EC2-PUBLIC-IP>
```
*(Windows PowerShell mein directly `ssh -i "insuregpt-key.pem" ubuntu@<YOUR-EC2-PUBLIC-IP>` chalayein).*

---

## Step 3: Server Packages & Docker Install Karein

EC2 server par packages update karein aur Docker + Git install karein:

```bash
# 1. System update
sudo apt update && sudo apt upgrade -y

# 2. Git & essential utilities
sudo apt install -y git curl wget unzip htop

# 3. Install Docker & Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 4. Ubuntu user ko docker group mein add karein
sudo usermod -aG docker $USER

# 5. Docker Compose plugin install karein
sudo apt install -y docker-compose-plugin

# 6. Group changes reload karne ke liye
newgrp docker

# 7. Check versions
docker --version
docker compose version
```

---

## Step 4: Project Code Clone ya Transfer Karein

### Option 1: Git Repository se Clone Karein (Recommended)
```bash
cd /home/ubuntu
git clone <YOUR-GITHUB-REPO-URL> insuregpt
cd insuregpt
```

### Option 2: Local Machine se SCP ke through transfer karein (Agar private repo hai)
Local terminal se:
```bash
scp -i "insuregpt-key.pem" -r D:\INSUREGPT ubuntu@<YOUR-EC2-PUBLIC-IP>:/home/ubuntu/insuregpt
```

---

## Step 5: Production .env File Configure Karein

Project folder ke andar jayein aur `.env` file create karein:

```bash
cd /home/ubuntu/insuregpt
nano .env
```

Niche diya gaya configuration paste karein (Apni actual API keys add karein):

```ini
# Server Settings
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=production
LOG_LEVEL=INFO

# MySQL Database (Docker Compose service name 'mysql' use hoga)
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=insuregpt
MYSQL_USER=root
MYSQL_PASSWORD=SecurePassword123!

# Pinecone Vector Database
PINECONE_API_KEY=your_actual_pinecone_api_key_here
PINECONE_INDEX_NAME=insuregpt-index
PINECONE_NAMESPACE=default

# LLM Service (Groq)
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_actual_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
OUTPUT_FORMAT=bullet
EMBEDDING_MODEL=text-embedding-3-small
RERANKER_MODEL=BAAI/bge-reranker-base

# Web Search (Tavily)
TAVILY_API_KEY=tvly-your_actual_tavily_key_here
WEB_SEARCH_ENABLED=False
```

> **Save karne ke liye**: Press `Ctrl + O` then `Enter`, aur exit ke liye `Ctrl + X`.

---

## Step 6: Method A — Docker Compose se Run Karein (Recommended)

Docker Compose se aapka FastAPI backend aur MySQL 8.4 container dono automatic start ho jayenge:

```bash
cd /home/ubuntu/insuregpt

# 1. Build and Start Containers in Detached (-d) Mode
docker compose up --build -d

# 2. Verify containers running status
docker compose ps

# 3. Real-time application logs check karein
docker compose logs -f app
```

Aapka application live ho gaya hai:
👉 **`http://<YOUR-EC2-PUBLIC-IP>:8000`**

---

## Step 7: Method B — Native Systemd Service & Uvicorn

Agar aap Docker nahi use karna chahte aur direct Python se run karna chahte hain:

```bash
# 1. Python 3.11/3.12 & venv install karein
sudo apt install -y python3-pip python3-venv

# 2. Virtual environment create aur activate karein
cd /home/ubuntu/insuregpt
python3 -m venv .venv
source .venv/bin/activate

# 3. Dependencies install karein
pip install --upgrade pip
pip install -r requirements.txt
```

### Systemd Background Service Create Karein:
```bash
sudo nano /etc/systemd/system/insuregpt.service
```

Paste karein:
```ini
[Unit]
Description=InsureGPT FastAPI Application
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/insuregpt
EnvironmentFile=/home/ubuntu/insuregpt/.env
ExecStart=/home/ubuntu/insuregpt/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Service ko start aur enable karein:
```bash
sudo systemctl daemon-reload
sudo systemctl start insuregpt
sudo systemctl enable insuregpt
sudo systemctl status insuregpt
```

---

## Step 8: Nginx Reverse Proxy & SSL Setup (Port 80/443)

Production ke liye port 8000 ke bajaye standard port 80 (HTTP) aur port 443 (HTTPS) use karne ke liye Nginx reverse proxy setup karein:

```bash
# 1. Nginx install karein
sudo apt install -y nginx

# 2. Nginx configuration create karein
sudo nano /etc/nginx/sites-available/insuregpt
```

Configuration paste karein (SSE streaming support ke sath):
```nginx
server {
    listen 80;
    server_name <YOUR-DOMAIN-NAME-OR-EC2-PUBLIC-IP>;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        
        # Critical for SSE (Server-Sent Events) live token streaming
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding on;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Nginx site enable karein aur reload karein:
```bash
sudo ln -s /etc/nginx/sites-available/insuregpt /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### Free SSL Certificate (HTTPS) lagayein:
Agar aapke paas domain name point kiya hua hai:
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## Step 9: Testing & Health Verification

EC2 terminal se ya browser se check karein:

```bash
# 1. Health check endpoint
curl -s http://localhost:8000/api/health | jq .

# 2. Expected output:
# {
#   "status": "ok",
#   "app": "InsureGPT",
#   "version": "1.0.0",
#   "environment": "production",
#   "database": "healthy"
# }
```

Browser mein open karein:
- **Web UI**: `http://<YOUR-EC2-PUBLIC-IP>`
- **API Swagger Docs**: `http://<YOUR-EC2-PUBLIC-IP>/docs`

---

## Troubleshooting & FAQs

### 1. Browser mein page load nahi ho raha (Connection Timed Out)
- **Solution**: AWS EC2 Console mein jayein -> Instance select karein -> **Security** tab -> **Security Groups** par click karein -> **Edit inbound rules** -> Ensure karein ki **Custom TCP Port 8000**, **HTTP (80)**, aur **HTTPS (443)** allow hain (`0.0.0.0/0`).

### 2. SSE Chat response stream nahi ho raha / chunk cut ho raha hai
- **Solution**: Agar Nginx use kar rahe hain toh ensure karein ki Nginx block mein `proxy_buffering off;` set hai, kyunki Nginx default mein stream ko buffer karta hai.

### 3. Docker MySQL container restart loop mein hai
- **Solution**: Check logs using `docker compose logs mysql`. Make sure port 3306 par koi dusra local MySQL pehle se bind na ho (`sudo netstat -tulpn | grep 3306`).

### 4. Application restart kaise karein changes ke baad?
- Docker: `docker compose down && docker compose up -d --build`
- Systemd: `sudo systemctl restart insuregpt`
