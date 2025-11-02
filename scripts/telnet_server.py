#!/usr/bin/env python3
"""
Simple Telnet Server for DXSpider
Listens on port 7300 and proxies to console.pl
Reformats output for logging software compatibility
"""

import socket
import subprocess
import threading
import sys
import pty
import os
import select
import re

PORT = 7300
HOST = '0.0.0.0'


# ANSI escape sequence pattern
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
def clean_callsign(callsign):
    """Remove trailing punctuation from callsigns"""
    # Remove trailing semicolons, periods, colons, commas
    return callsign.rstrip(';:.,')

def reformat_dx_line(line):
    """
    Reformat DX spot lines - only process clear DX spots to avoid breaking login
    """
    original_line = line
    
    # Only process lines that clearly look like DX spots
    if not re.search(r'\d+\.\d+\s+[A-Z0-9/]+', line):
        return line
    
    # Format 1: sh/dx output - "freq callsignDATE time comment"
    match = re.match(r'^(\s*)(\d+\.\d+)\s+([A-Z0-9/;:.,]+)(\d{1,2}-\w+-\d{4}\s+\d{4}Z.*)$', line)
    if match:
        indent = match.group(1)
        freq = match.group(2)
        callsign = clean_callsign(match.group(3))  # Clean the callsign
        date_and_comment = match.group(4)
        
        formatted = f"{indent}{freq:>8s}  {callsign:13s} {date_and_comment}"
        logger.debug(f"Reformatted sh/dx: '{original_line}' -> '{formatted}'")
        return formatted
    
    # Format 2: Live spots - "DX de SPOTTER: freq spotted comment"
    match2 = re.match(r'^(DX de \S+:\s*)(\d+\.\d+)\s+([A-Z0-9/;:.,]+)(POTA.*)$', line, re.IGNORECASE)
    if match2:
        prefix = match2.group(1)
        freq = match2.group(2)
        callsign = clean_callsign(match2.group(3))  # Clean the callsign
        comment = match2.group(4)
        
        formatted = f"{prefix}{freq:>8s}  {callsign:13s} {comment}"
        logger.debug(f"Reformatted live spot: '{original_line}' -> '{formatted}'")
        return formatted
    
    return line

def process_output(data):
    """
    Remove ANSI codes and reformat DX spots - conservative approach
    """
    text = data.decode('utf-8', errors='ignore')
    
    # Remove all ANSI sequences
    clean_text = ANSI_ESCAPE.sub('', text)
    
    # Remove other control characters except newline, tab, carriage return
    clean_text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', clean_text)
    
    # Process line by line
    lines = clean_text.split('\n')
    reformatted_lines = []
    
    for line in lines:
        # Only reformat if line contains clear DX spot indicators
        if (re.search(r'\d+\.\d+\s+[A-Z0-9/]+.*POTA', line) or 
            re.search(r'\d+\.\d+\s+[A-Z0-9/]+\d{1,2}-\w+-\d{4}', line)):
            reformatted = reformat_dx_line(line)
            reformatted_lines.append(reformatted)
        else:
            reformatted_lines.append(line)
    
    return '\n'.join(reformatted_lines).encode('utf-8')

def handle_client(client_socket, client_address):
    """Handle individual client connection"""
    print(f"[TELNET] Connection from {client_address}", flush=True)
    
    master_fd = None
    proc = None
    stop_threads = threading.Event()
    
    try:
        # Send login prompt with error handling
        try:
            client_socket.send(b"login: ")
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            print(f"[TELNET] Client disconnected before login prompt: {e}", flush=True)
            return
        
        # Read callsign with timeout
        client_socket.settimeout(30)
        callsign = b""
        try:
            while len(callsign) < 20:
                char = client_socket.recv(1)
                if not char or char in (b'\n', b'\r'):
                    break
                callsign += char
        except socket.timeout:
            print(f"[TELNET] Login timeout from {client_address}", flush=True)
            try:
                client_socket.send(b"Login timeout\r\n")
            except:
                pass
            return
        except (BrokenPipeError, ConnectionResetError, OSError):
            print(f"[TELNET] Client disconnected during login", flush=True)
            return
        
        callsign = callsign.decode('ascii', errors='ignore').strip().upper()
        
        if not callsign:
            print(f"[TELNET] No callsign provided from {client_address}", flush=True)
            try:
                client_socket.send(b"No callsign provided\r\n")
            except:
                pass
            return
        
        print(f"[TELNET] User {callsign} logging in", flush=True)
        
        # Remove timeout for ongoing session
        client_socket.settimeout(None)
        
        # Start console.pl with PTY
        master_fd, slave_fd = pty.openpty()
        
        # Set up environment with TERM variable
        env = os.environ.copy()
        env['TERM'] = 'vt100'
        
        proc = subprocess.Popen(
            ['/spider/perl/console.pl', callsign],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd='/spider/perl',
            env=env,
            close_fds=True
        )
        
        os.close(slave_fd)  # Close slave in parent
        
        print(f"[TELNET] console.pl started for {callsign}", flush=True)
        
        # Thread to read from console and send to client
        def read_from_console():
            try:
                while not stop_threads.is_set():
                    # Use select to check if data is available
                    r, _, _ = select.select([master_fd], [], [], 0.1)
                    if r:
                        try:
                            data = os.read(master_fd, 4096)
                            if not data:
                                break
                            
                            # Process and clean the data
                            clean_data = process_output(data)
                            
                            if clean_data:
                                client_socket.send(clean_data)
                                    
                        except OSError:
                            break
                        except (BrokenPipeError, ConnectionResetError):
                            print(f"[TELNET] Client {callsign} disconnected (send failed)", flush=True)
                            break
            except Exception as e:
                print(f"[TELNET] Console read error for {callsign}: {e}", flush=True)
            finally:
                stop_threads.set()
        
        reader = threading.Thread(target=read_from_console, daemon=True)
        reader.start()
        
        # Read from client and send to console
        try:
            while not stop_threads.is_set():
                data = client_socket.recv(1024)
                if not data:
                    print(f"[TELNET] Client {callsign} closed connection", flush=True)
                    break
                os.write(master_fd, data)
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            print(f"[TELNET] Connection error for {callsign}: {e}", flush=True)
        except Exception as e:
            print(f"[TELNET] Unexpected error for {callsign}: {e}", flush=True)
        
    except Exception as e:
        print(f"[TELNET] Error handling client: {e}", flush=True)
    finally:
        stop_threads.set()
        
        # Clean up PTY
        if master_fd:
            try:
                os.close(master_fd)
            except:
                pass
        
        # Clean up process
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except:
                try:
                    proc.kill()
                except:
                    pass
        
        # Clean up socket
        try:
            client_socket.shutdown(socket.SHUT_RDWR)
        except:
            pass
        try:
            client_socket.close()
        except:
            pass
        
        print(f"[TELNET] Connection from {client_address} closed", flush=True)

def main():
    """Main telnet server loop"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    
    print(f"[TELNET] Server listening on {HOST}:{PORT}", flush=True)
    
    while True:
        try:
            client_socket, client_address = server.accept()
            thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address),
                daemon=True
            )
            thread.start()
        except KeyboardInterrupt:
            print("\n[TELNET] Shutting down...", flush=True)
            break
        except Exception as e:
            print(f"[TELNET] Server error: {e}", flush=True)
    
    server.close()

if __name__ == "__main__":
    main()