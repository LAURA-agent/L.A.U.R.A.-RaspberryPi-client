#!/usr/bin/env python3
"""
VOSK Server Health Check
Tests if VOSK WebSocket server is ready and responsive
"""

import asyncio
import websockets
import json
import time
import sys


async def check_vosk_server(server_url="ws://localhost:8765", timeout=30):
    """
    Check if VOSK server is ready and responsive
    
    Returns:
        (bool, str): (is_ready, status_message)
    """
    try:
        # Connect to server
        websocket = await asyncio.wait_for(
            websockets.connect(server_url, ping_interval=None),
            timeout=5.0
        )
        
        # Wait for connection response
        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        data = json.loads(response)
        
        if data.get('type') == 'connection' and data.get('status') == 'connected':
            session_id = data.get('session_id')
            
            # Test with a status command
            status_cmd = {'type': 'status'}
            await websocket.send(json.dumps(status_cmd))
            
            # Wait for status response
            status_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            status_data = json.loads(status_response)
            
            if status_data.get('type') == 'status':
                model_path = status_data.get('model_path', 'unknown')
                sample_rate = status_data.get('sample_rate', 0)
                
                await websocket.close()
                
                return True, f"VOSK server ready - Model: {model_path}, Rate: {sample_rate}Hz"
            else:
                await websocket.close()
                return False, f"Server responded but status check failed: {status_data}"
                
        else:
            await websocket.close()
            return False, f"Unexpected connection response: {data}"
            
    except asyncio.TimeoutError:
        return False, "Timeout connecting to VOSK server"
    except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError):
        return False, "VOSK server connection closed (server may be starting up)"
    except OSError as e:
        if "Connection refused" in str(e):
            return False, "VOSK server not running (connection refused)"
        else:
            return False, f"Connection error: {e}"
    except websockets.exceptions.InvalidURI:
        return False, f"Invalid server URL: {server_url}"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON response from server: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


async def wait_for_vosk_ready(server_url="ws://localhost:8765", max_wait=60, check_interval=2):
    """
    Wait for VOSK server to become ready
    
    Args:
        server_url: WebSocket URL of VOSK server
        max_wait: Maximum seconds to wait
        check_interval: Seconds between checks
        
    Returns:
        bool: True if server became ready, False if timeout
    """
    start_time = time.time()
    
    print(f"🔍 Waiting for VOSK server at {server_url}...")
    
    while time.time() - start_time < max_wait:
        is_ready, message = await check_vosk_server(server_url)
        
        if is_ready:
            print(f"✅ {message}")
            return True
        else:
            elapsed = int(time.time() - start_time)
            print(f"⏳ [{elapsed}s] {message}")
            
        await asyncio.sleep(check_interval)
    
    print(f"❌ Timeout waiting for VOSK server after {max_wait} seconds")
    return False


async def main():
    """Main entry point for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Check VOSK WebSocket Server Health")
    parser.add_argument('--url', default='ws://localhost:8765', help='Server URL')
    parser.add_argument('--wait', type=int, default=0, help='Wait up to N seconds for server to be ready')
    parser.add_argument('--interval', type=int, default=2, help='Check interval when waiting')
    
    args = parser.parse_args()
    
    if args.wait > 0:
        # Wait for server to become ready
        ready = await wait_for_vosk_ready(args.url, args.wait, args.interval)
        sys.exit(0 if ready else 1)
    else:
        # Single health check
        is_ready, message = await check_vosk_server(args.url)
        print(f"{'✅' if is_ready else '❌'} {message}")
        sys.exit(0 if is_ready else 1)


if __name__ == "__main__":
    asyncio.run(main())