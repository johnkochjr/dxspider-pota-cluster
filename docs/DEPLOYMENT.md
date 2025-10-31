# Deployment Guide for ASUSTor NAS

## Prerequisites

- ASUSTor NAS with Docker support
- SSH access to your NAS
- Git installed on your NAS (or download ZIP from GitHub)

## Method 1: Using SSH (Recommended)

### 1. Connect to your NAS
```bash
ssh admin@YOUR_NAS_IP
```

### 2. Clone the repository
```bash
cd /volume1/docker  # or your preferred docker directory
git clone https://github.com/YOUR_USERNAME/dxspider-pota-cluster.git
cd dxspider-pota-cluster
```

### 3. Configure the environment
```bash
cp .env.example .env
nano .env
```

Update all values with your information.

### 4. Deploy
```bash
docker-compose up -d
```

### 5. Check logs
```bash
docker-compose logs -f
```

### 6. Test connection

From another computer:
```bash
telnet YOUR_NAS_IP 7300
```

## Method 2: Using ASUSTor Portal

### 1. Download from GitHub

Download the repository as a ZIP file from GitHub and extract it.

### 2. Upload to NAS

Use File Explorer to upload the entire folder to your NAS.

### 3. Create .env file

Using the text editor in ADM, copy `.env.example` to `.env` and edit with your info.

### 4. Access Terminal

Open ADM terminal or SSH into your NAS.

### 5. Navigate and deploy
```bash
cd /path/to/dxspider-pota-cluster
docker-compose up -d
```

## Maintenance Commands

### View logs
```bash
docker-compose logs -f
```

### Restart cluster
```bash
docker-compose restart
```

### Stop cluster
```bash
docker-compose down
```

### Update from GitHub
```bash
git pull
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Backup data
```bash
docker run --rm -v dxspider-pota-cluster_spider-data:/data -v $(pwd):/backup alpine tar czf /backup/spider-backup.tar.gz /data
```

## Troubleshooting

### Can't connect to port 7300

Check firewall on NAS:
- Add rule to allow port 7300
- Test: `telnet localhost 7300` from NAS terminal

### POTA spots not appearing

Check logs:
```bash
docker-compose logs pota_bridge
```

Verify POTA API is accessible:
```bash
curl https://api.pota.app/spot/activator
```

### Container won't start

Check Docker logs:
```bash
docker logs dxspider-pota
```

Rebuild container:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Port Forwarding (Optional)

To make your cluster accessible from the internet:

1. Forward port 7300 on your router to your NAS IP
2. Use a dynamic DNS service if you don't have a static IP
3. Consider security implications of exposing services

## Updates

To update the cluster software:
```bash
cd /path/to/dxspider-pota-cluster
git pull
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```