#!/usr/bin/env python3
"""
POTA to DXSpider Bridge
Fetches POTA spots from the POTA API and forwards them to a DXSpider cluster
"""

import requests
import time
import socket
import os
import sys
from datetime import datetime

# Configuration from environment variables
POTA_API = "https://api.pota.app/spot/activator"
CLUSTER_HOST = os.getenv("CLUSTER_HOST", "localhost")
CLUSTER_PORT = int(os.getenv("CLUSTER_PORT", "7300"))
YOUR_CALLSIGN = os.getenv("CALLSIGN", "POTA-GW")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
MIN_FREQUENCY = float(os.getenv("MIN_FREQ", "1.8"))
MAX_FREQUENCY = float(os.getenv("MAX_FREQ", "54.0"))

seen_spots = set()
MAX_SEEN_SPOTS = 1000

def log(message):
    """Print timestamped log message"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)

def connect_to_cluster(max_retries=5, retry_delay=5):
    """Connect to the DXSpider cluster with retries"""
    for attempt in range(max_retries):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((CLUSTER_HOST, CLUSTER_PORT))
            time.sleep(1)
            
            # Read login prompt
            sock.recv(1024)
            
            # Send callsign
            sock.send(f"{YOUR_CALLSIGN}\n".encode())
            time.sleep(1)
            sock.recv(1024)
            
            log(f"Connected to DXSpider cluster at {CLUSTER_HOST}:{CLUSTER_PORT}")
            return sock
            
        except Exception as e:
            log(f"Connection attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise Exception(f"Failed to connect after {max_retries} attempts")

def send_spot(sock, callsign, frequency, comment):
    """Send a DX spot to the cluster"""
    try:
        spot_cmd = f"dx {frequency} {callsign} {comment}\n"
        sock.send(spot_cmd.encode())
        return True
    except Exception as e:
        log(f"Error sending spot: {e}")
        return False

def fetch_pota_spots():
    """Fetch current POTA spots from API"""
    try:
        response = requests.get(POTA_API, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log(f"Error fetching POTA spots: {e}")
        return []

def process_spots(sock):
    """Fetch and process POTA spots"""
    spots = fetch_pota_spots()
    new_spots = 0
    
    for spot in spots:
        spot_id = spot.get('spotId')
        if spot_id in seen_spots:
            continue
        
        activator = spot.get('activator', '').strip()
        frequency = spot.get('frequency', '').strip()
        reference = spot.get('reference', '').strip()
        location = spot.get('locationDesc', '').strip()
        
        if not activator or not frequency or not reference:
            continue
        
        # Validate frequency range
        try:
            freq_mhz = float(frequency)
            if freq_mhz < MIN_FREQUENCY or freq_mhz > MAX_FREQUENCY:
                continue
        except ValueError:
            continue
        
        # Format comment (keep short for cluster compatibility)
        comment = f"POTA {reference}"
        if location:
            comment += f" {location[:20]}"
        
        # Send to cluster
        if send_spot(sock, activator, frequency, comment):
            seen_spots.add(spot_id)
            new_spots += 1
            log(f"Spotted: {activator} on {frequency} MHz - {comment}")
        else:
            # Connection failed
            return None
    
    # Prevent memory growth
    if len(seen_spots) > MAX_SEEN_SPOTS:
        seen_spots.clear()
        log("Cleared spot cache to prevent memory growth")
    
    if new_spots > 0:
        log(f"Posted {new_spots} new POTA spots")
    
    return sock

def main():
    """Main loop"""
    log("=" * 60)
    log("POTA to DXSpider Bridge Starting")
    log("=" * 60)
    log(f"Callsign: {YOUR_CALLSIGN}")
    log(f"Cluster: {CLUSTER_HOST}:{CLUSTER_PORT}")
    log(f"Check interval: {CHECK_INTERVAL} seconds")
    log(f"Frequency range: {MIN_FREQUENCY}-{MAX_FREQUENCY} MHz")
    log("=" * 60)
    
    sock = None
    
    while True:
        try:
            # Connect or reconnect if needed
            if sock is None:
                sock = connect_to_cluster()
            
            # Process spots
            sock = process_spots(sock)
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            log("Shutting down on user request...")
            break
        except Exception as e:
            log(f"Error in main loop: {e}")
            sock = None
            time.sleep(CHECK_INTERVAL)
    
    log("Bridge stopped")
    sys.exit(0)

if __name__ == "__main__":
    main()