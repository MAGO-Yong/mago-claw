import argparse
import requests
import json
import sys

def run_analysis(analysis_type, service, start_time, end_time):
    # Mapping of analysis type to corresponding API endpoint
    endpoints = {
        "problem": "/api/diagnosis/service/analysis/problem",
        "service": "/api/diagnosis/service/analysis/service"
    }
    
    if analysis_type not in endpoints:
        print(f"Error: Unsupported analysis type '{analysis_type}'. Supported: {list(endpoints.keys())}", file=sys.stderr)
        sys.exit(1)
        
    url = f"https://xray-ai.devops.xiaohongshu.com{endpoints[analysis_type]}"
    headers = {
        "User-Agent": "Apipost client Runtime/+https://www.apipost.cn/",
        "Content-Type": "application/json"
    }
    data = {
        "service": service,
        "startTime": start_time,
        "endTime": end_time
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        # Return full JSON output for processing
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except requests.exceptions.RequestException as e:
        print(f"Error calling {analysis_type} API: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Xray Service Analysis Utility")
    parser.add_argument("--type", choices=["problem", "service"], default="problem", help="Analysis type: problem or service")
    parser.add_argument("--service", required=True, help="Service name")
    parser.add_argument("--startTime", required=True, help="Start time (YYYY-MM-DD HH:mm:ss)")
    parser.add_argument("--endTime", required=True, help="End time (YYYY-MM-DD HH:mm:ss)")
    
    args = parser.parse_args()
    run_analysis(args.type, args.service, args.startTime, args.endTime)
