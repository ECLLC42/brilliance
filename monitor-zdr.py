#!/usr/bin/env python3
"""
Zero Downtime Restart Monitor
Watches your app during deployments to verify ZDR is working.

Usage:
    python monitor-zdr.py https://your-app.herokuapp.com
"""

import sys
import time
import requests
import json
from datetime import datetime
from typing import Dict, Any

def colored(text: str, color: str) -> str:
    """Add color to terminal output."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'purple': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
        'reset': '\033[0m'
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"

def check_health(base_url: str) -> Dict[str, Any]:
    """Check app health and return status."""
    try:
        # Try detailed health first
        response = requests.get(f"{base_url}/health/detailed", timeout=5)
        if response.status_code == 200:
            return {
                "status": "healthy",
                "response_time": response.elapsed.total_seconds(),
                "data": response.json()
            }
        else:
            return {
                "status": "unhealthy",
                "response_time": response.elapsed.total_seconds(),
                "status_code": response.status_code
            }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "response_time": None,
            "error": str(e)
        }

def monitor_deployment(base_url: str, duration_minutes: int = 10):
    """Monitor app health during deployment."""
    print(f"🔍 Monitoring {base_url} for {duration_minutes} minutes...")
    print(f"{'Time':<10} {'Status':<10} {'Response':<10} {'PID':<8} {'Memory':<8} {'Notes'}")
    print("-" * 70)
    
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    last_pid = None
    downtime_start = None
    total_downtime = 0
    
    while time.time() < end_time:
        now = datetime.now().strftime("%H:%M:%S")
        health = check_health(base_url)
        
        if health["status"] == "healthy":
            data = health.get("data", {})
            current_pid = data.get("process_id", "unknown")
            memory = f"{data.get('memory_usage_mb', 0):.0f}MB"
            response_time = f"{health['response_time']*1000:.0f}ms"
            
            # Check if PID changed (indicates restart)
            notes = ""
            if last_pid and last_pid != current_pid:
                notes = colored("🔄 RESTART DETECTED", "yellow")
            elif not last_pid:
                notes = colored("✅ INITIAL", "green")
            
            # End downtime tracking
            if downtime_start:
                downtime_duration = time.time() - downtime_start
                total_downtime += downtime_duration
                notes += f" {colored(f'⬆️ RECOVERED (+{downtime_duration:.1f}s down)', 'green')}"
                downtime_start = None
            
            print(f"{now:<10} {colored('HEALTHY', 'green'):<15} {response_time:<10} {current_pid:<8} {memory:<8} {notes}")
            last_pid = current_pid
            
        elif health["status"] == "unhealthy":
            response_time = f"{health['response_time']*1000:.0f}ms" if health['response_time'] else "N/A"
            status_code = health.get("status_code", "N/A")
            
            if not downtime_start:
                downtime_start = time.time()
            
            print(f"{now:<10} {colored(f'UNHEALTHY', 'yellow'):<15} {response_time:<10} {'N/A':<8} {'N/A':<8} {colored(f'HTTP {status_code}', 'yellow')}")
            
        else:  # error
            error = health.get("error", "Unknown error")
            
            if not downtime_start:
                downtime_start = time.time()
                
            print(f"{now:<10} {colored('ERROR', 'red'):<15} {'N/A':<10} {'N/A':<8} {'N/A':<8} {colored(error[:30], 'red')}")
        
        time.sleep(2)
    
    # Final downtime calculation
    if downtime_start:
        total_downtime += time.time() - downtime_start
    
    print("\n" + "="*70)
    print(f"📊 Monitoring Summary:")
    print(f"   Duration: {duration_minutes} minutes")
    print(f"   Total Downtime: {colored(f'{total_downtime:.1f} seconds', 'yellow' if total_downtime > 5 else 'green')}")
    
    if total_downtime == 0:
        print(f"   Result: {colored('✅ ZERO DOWNTIME ACHIEVED!', 'green')}")
    elif total_downtime <= 5:
        print(f"   Result: {colored('🟡 MINIMAL DOWNTIME (acceptable)', 'yellow')}")
    else:
        print(f"   Result: {colored('🔴 SIGNIFICANT DOWNTIME (needs improvement)', 'red')}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python monitor-zdr.py https://your-app.herokuapp.com")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    
    try:
        monitor_deployment(base_url)
    except KeyboardInterrupt:
        print(f"\n{colored('🛑 Monitoring stopped by user', 'yellow')}")
    except Exception as e:
        print(f"\n{colored(f'❌ Error: {e}', 'red')}")
        sys.exit(1)
