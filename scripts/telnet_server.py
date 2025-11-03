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
import time

PORT = 7300
HOST = '0.0.0.0'


# ANSI escape sequence pattern
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
def clean_callsign(callsign):
    """Remove trailing punctuation and clean callsign"""
    # Remove trailing semicolons, periods, colons, commas
    callsign = callsign.rstrip(';:.,')
    # Also remove any embedded semicolons (shouldn't be in callsigns)
    callsign = callsign.replace(';', '')
    return callsign


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
        return formatted
    
    # Format 2: Live spots - "DX de SPOTTER: freq spotted comment"
    match2 = re.match(r'^(DX de \S+:\s*)(\d+\.\d+)\s+([A-Z0-9/;:.,]+)(POTA.*)$', line, re.IGNORECASE)
    if match2:
        prefix = match2.group(1)
        freq = match2.group(2)
        callsign = clean_callsign(match2.group(3))  # Clean the callsign
        comment = match2.group(4)
        
        formatted = f"{prefix}{freq:>8s}  {callsign:13s} {comment}"
        return formatted
    
    return line

def process_output(data):
    """
    Parse ANSI - track columns within lines, split only on real newlines
    """
    text = data.decode('utf-8', errors='ignore')
    
    lines = []
    current_line = [' '] * 200
    col = 0
    
    i = 0
    while i < len(text):
        # ESC [ sequences
        if i < len(text) - 1 and text[i:i+2] == '\x1B[':
            j = i + 2
            seq = ''
            while j < len(text) and text[j] not in 'ABCDEFGHJKSTfmhlsu':
                seq += text[j]
                j += 1
            
            if j < len(text):
                cmd = text[j]
                
                # Cursor position: ESC[row;colH - ONLY use column, ignore row
                if cmd in 'Hf' and ';' in seq:
                    parts = seq.split(';')
                    if len(parts) >= 2:
                        try:
                            # Ignore row (parts[0]), only use column
                            new_col = int(parts[1]) - 1
                            if 0 <= new_col < 200:
                                col = new_col
                        except:
                            pass
            
            i = j + 1
            continue
        
        # ESC ( charset selection
        if i < len(text) - 1 and text[i:i+2] in ['\x1B(', '\x1B)', '\x1B=', '\x1B>']:
            i += 2
            if i < len(text):
                i += 1
            continue
        
        # Newline - save current line and start new one
        if text[i] == '\n':
            line_text = ''.join(current_line).rstrip()
            lines.append(line_text)
            current_line = [' '] * 200
            col = 0
            i += 1
            continue
        
        # Carriage return - go back to start of line
        if text[i] == '\r':
            col = 0
            i += 1
            continue
        
        # Regular character
        if col < 200:
            current_line[col] = text[i]
            col += 1
        i += 1
    
    # Add final line
    line_text = ''.join(current_line).rstrip()
    if line_text:
        lines.append(line_text)
    
    result = '\n'.join(lines)
    
    # Rest of cleanup code stays the same...
    
    # Clean up artifacts
    result = re.sub(r'\d+-\d+$', '', result, flags=re.MULTILINE)
    result = re.sub(r'24x80-[A-Z0-9@-]+', '', result)
    result = re.sub(r'<AI5KP>', '', result)  
    
    # Remove sh/dx command output (list format) - keep only live spots
    lines_filtered = []
    for line in result.split('\n'):
        # Keep only lines that start with "DX de" (live spots)
        # Skip sh/dx list format (starts with just frequency)
        stripped = line.strip()
        if not stripped:
            lines_filtered.append(line)  # Keep empty lines
        elif stripped.startswith('DX de '):
            lines_filtered.append(line)  # Keep live spots
        elif not re.match(r'^\s*\d+\.\d+\s+[A-Z0-9/]+', line):
            lines_filtered.append(line)  # Keep non-spot lines (prompts, etc.)
        # else: skip sh/dx list format lines
            
    result = '\n'.join(lines_filtered)


    def fix_dx_line(match):
        full_line = match.group(0)
        
        # More flexible parsing - handle variable spacing around colon
        # Pattern: "DX de SPOTTER:? SPACES? FREQ ..."
        dx_match = re.match(r'^DX de (\S+)\s*:\s*(\d+\.\d+)\s+(.+?)(\d{4}Z)\s*$', full_line)
        if not dx_match:
            return full_line
        
        spotter = dx_match.group(1)
        freq = dx_match.group(2)
        middle = dx_match.group(3).strip()
        time = dx_match.group(4)
        
        # Find where the country-park code starts
        country_match = re.search(r'([A-Z]{2}-\d+)', middle)
        if country_match:
            split_pos = country_match.start()
            callsign = middle[:split_pos].strip()
            comment = middle[split_pos:].strip()
        else:
            parts = middle.split(None, 1)
            callsign = parts[0] if parts else middle
            comment = parts[1] if len(parts) > 1 else ""
        
        # Rebuild with EXACT consistent format
        # Standard DX cluster format: "DX de CALL:  FREQ  CALLSIGN  COMMENT  TIME"
        formatted = f"DX de {spotter}:  {freq:>8s}  {callsign:13s} {comment:30s} {time}"
        return formatted

    # Apply to all DX lines
    result = re.sub(
        r'^DX de .+$',
        fix_dx_line,
        result,
        flags=re.MULTILINE
    )

    # At the very end of process_output, before return:

    # Ensure newlines after time stamps
    result = re.sub(r'(\d{4}Z)(?=DX de)', r'\1\n', result)

    # Add newlines after prompts
    result = re.sub(r'(dxspider >)(?=\S)', r'\1\n', result)

    # Add spacing after common transition points
    result = re.sub(r'(build \d+)([A-Z])', r'\1\n\2', result)
    result = re.sub(r'(ve7cc)([A-Z])', r'\1\n\2', result)
    result = re.sub(r'(Uptime:[^\n]+)([A-Z])', r'\1\n\2', result)

    # Clean up compressed login banner
    result = re.sub(r'(USA)([A-Zr])', r'\1\n\2', result)
    result = re.sub(r'(build \d+)(\w)', r'\1\n\2', result)

    # Remove trailing artifacts
    result = re.sub(r'-\d{4}\s*$', '', result, flags=re.MULTILINE)

    # Limit consecutive blank lines to 1
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result.encode('utf-8')


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

        # Flag to skip initial setup output
        setup_complete = False
        
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