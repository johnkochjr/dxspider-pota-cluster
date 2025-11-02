#!/usr/bin/env python3
"""
POTA to DXSpider Bridge - Command Version
Sends spots via DXSpider console commands
"""

import requests
import time
import os
import socket
from datetime import datetime

# Configuration
POTA_API = "https://api.pota.app/spot/activator"
DXSPIDER_HOST = "localhost"
DXSPIDER_PORT = 7300
CALLSIGN = os.getenv("CALLSIGN", "POTA")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
MIN_FREQUENCY = float(os.getenv("MIN_FREQ", "1.8"))
MAX_FREQUENCY = float(os.getenv("MAX_FREQ", "54.0"))

seen_spots = set()
MAX_SEEN_SPOTS = 1000

def log(message):
    """Print timestamped log message"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)

def fetch_pota_spots():
    """Fetch current POTA spots from API"""
    try:
        response = requests.get(POTA_API, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log(f"Error fetching POTA spots: {e}")
        return []

class DXSpiderConnection:
    """Manages connection to DXSpider"""
    
    def __init__(self, host, port, callsign):
        self.host = host
        self.port = port
        self.callsign = callsign
        self.sock = None
        self.connected = False
    
    def connect(self):
        """Connect to DXSpider"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.host, self.port))
            
            # Wait for login prompt
            data = self.sock.recv(1024)
            if b"login:" in data:
                # Send callsign
                self.sock.send(f"{self.callsign}\n".encode())
                time.sleep(1)
                
                # Read welcome messages
                self.sock.recv(8192)
                
                # Disable ANSI/fancy output
                self.sock.send(b"unset/page\n")
                time.sleep(0.5)
                self.sock.recv(4096)
                
                self.sock.send(b"set/nobeep\n")
                time.sleep(0.5)
                self.sock.recv(4096)
                
                # This is the key one - disable paging/formatting
                self.sock.send(b"unset/ansi\n")
                time.sleep(0.5)
                self.sock.recv(4096)
                
                self.connected = True
                log(f"Connected to DXSpider as {self.callsign}")
                return True
        except Exception as e:
            log(f"Error connecting to DXSpider: {e}")
            self.connected = False
            return False
    
    def send_spot(self, freq, callsign, comment):
        """Send a DX spot"""
        if not self.connected:
            if not self.connect():
                return False
        
        try:
            # Format: dx <freq> <call> <comment>
            # Frequency should be formatted cleanly
            freq_mhz = f"{freq:.4f}"
            
            # Build command with explicit spacing - tab or multiple spaces
            cmd = f"dx {freq_mhz} {callsign} {comment}\r\n"
            
            self.sock.send(cmd.encode())
            time.sleep(0.2)
            
            return True
        except Exception as e:
            log(f"Error sending spot: {e}")
            self.connected = False
            return False
    
    def close(self):
        """Close connection"""
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.connected = False

def process_spots(dx_conn):
    """Fetch and process POTA spots"""
    spots_data = fetch_pota_spots()
    new_spots = 0
    
    for spot in spots_data:
        spot_id = spot.get('spotId')
        if spot_id in seen_spots:
            continue
        
        activator = spot.get('activator', '').strip()
        frequency = spot.get('frequency', '').strip()
        reference = spot.get('reference', '').strip()
        location = spot.get('locationDesc', '').strip()
        
        if not activator or not frequency or not reference:
            continue
        
        # Convert frequency from kHz to MHz
        try:
            freq_khz = float(frequency)
            freq_mhz = freq_khz / 1000
            if freq_mhz < MIN_FREQUENCY or freq_mhz > MAX_FREQUENCY:
                continue
        except ValueError:
            continue
        
        # Format comment
        comment = f"POTA {reference}"
        if location:
            comment += f" {location[:20]}"
        
        # Send spot to DXSpider
        if dx_conn.send_spot(freq_mhz, activator, comment):
            seen_spots.add(spot_id)
            new_spots += 1
            log(f"Spotted: {activator} on {freq_mhz} MHz - {comment}")
    
    if new_spots > 0:
        log(f"Added {new_spots} POTA spots")
    
    # Prevent memory growth
    if len(seen_spots) > MAX_SEEN_SPOTS:
        seen_spots.clear()
        log("Cleared spot cache")

def main():
    """Main loop"""
    log("=" * 60)
    log("POTA to DXSpider Bridge Starting")
    log("=" * 60)
    log(f"Bot callsign: {CALLSIGN}-2")
    log(f"DXSpider: {DXSPIDER_HOST}:{DXSPIDER_PORT}")
    log(f"Check interval: {CHECK_INTERVAL} seconds")
    log(f"Frequency range: {MIN_FREQUENCY}-{MAX_FREQUENCY} MHz")
    log("=" * 60)
    
    # Create connection with -2 suffix (the sysop user we created)
    dx_conn = DXSpiderConnection(DXSPIDER_HOST, DXSPIDER_PORT, f"{CALLSIGN}-2")
    
    while True:
        try:
            process_spots(dx_conn)
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            log("Shutting down...")
            break
        except Exception as e:
            log(f"Error in main loop: {e}")
            dx_conn.close()
            time.sleep(CHECK_INTERVAL)
    
    dx_conn.close()
    log("Bridge stopped")

if __name__ == "__main__":
    main()