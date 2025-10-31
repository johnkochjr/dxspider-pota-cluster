# DXSpider POTA Cluster

A DX Cluster node running DXSpider with integrated POTA (Parks on the Air) spot feed.

## Features

- Full DXSpider cluster node
- Automatic POTA spot integration from pota.app API
- Dockerized for easy deployment
- Configurable frequency ranges and update intervals

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Your amateur radio callsign

### Installation

1. Clone this repository:
```bash
git clone https://github.com/YOUR_USERNAME/dxspider-pota-cluster.git
cd dxspider-pota-cluster
```

2. Copy and edit the environment file:
```bash
cp .env.example .env
nano .env
```

3. Edit `.env` with your information (see Configuration section)

4. Start the cluster:
```bash
docker-compose up -d
```

5. Connect to your cluster:
```bash
telnet localhost 7300
```

## Configuration

Edit the `.env` file with your details:

- `CALLSIGN`: Your amateur radio callsign
- `OPERATOR_NAME`: Your name
- `QTH`: Your location
- `EMAIL`: Your email address
- `LATITUDE`: Your latitude (format: +40.7128)
- `LONGITUDE`: Your longitude (format: -74.0060)
- `GRID`: Your maidenhead grid square
- `CHECK_INTERVAL`: How often to check POTA API (seconds, default 60)
- `MIN_FREQ`: Minimum frequency to spot (MHz, default 1.8)
- `MAX_FREQ`: Maximum frequency to spot (MHz, default 54.0)

## Deployment

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed deployment instructions on ASUSTor NAS.

## Usage

### Connecting to the Cluster

From any telnet client:
```bash
telnet YOUR_NAS_IP 7300
```

Enter your callsign when prompted.

### Monitoring Logs
```bash
docker-compose logs -f
```

### Stopping the Cluster
```bash
docker-compose down
```

## License

MIT License - Feel free to modify and use.

## Credits

- DXSpider cluster software
- POTA API (pota.app)