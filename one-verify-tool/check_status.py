import httpx
import re
import sys
import argparse
from pathlib import Path

SHEERID_API_URL = "https://services.sheerid.com/rest/v2"

def get_status(url, proxy=None):
    # 解析 Verification ID
    match = re.search(r"verificationId=([a-f0-9]+)", url, re.IGNORECASE)
    if not match:
        print("❌ 错误: 无效的验证 URL，找不到 verificationId")
        return
    
    vid = match.group(1)
    print(f"\n🔍 Querying status for ID: {vid}...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    proxies = None
    if proxy:
        if not proxy.startswith("http"):
            proxy = f"http://{proxy}"
        proxies = {"http://": proxy, "https://": proxy}

    try:
        with httpx.Client(proxies=proxies, timeout=10) as client:
            resp = client.get(f"{SHEERID_API_URL}/verification/{vid}", headers=headers)
            
            if resp.status_code != 200:
                print(f"❌ API 请求失败 (HTTP {resp.status_code})")
                return

            data = resp.json()
            step = data.get("currentStep")
            created = data.get("created")
            
            print("-" * 50)
            print(f"📍 当前状态 (currentStep): {step}")
            
            if step == "pending":
                print("⏳ 状态解读: 正在人工审核/高级OCR处理中。请继续等待。")
            elif step == "success":
                print("✅ 状态解读: 认证已通过！你可以回浏览器完成订阅了。")
            elif step == "error" or step == "rejected":
                errors = data.get("errorIds", [])
                print(f"❌ 状态解读: 认证被拒绝。失败原因 IDs: {errors}")
            elif step == "collectStudentPersonalInfo":
                print("📝 状态解读: 尚未提交信息，或因为失败已被重置。")
            else:
                print(f"❓ 状态解读: 未知步骤 '{step}'，请根据浏览器显示为准。")
            
            print("-" * 50)
            
    except Exception as e:
        print(f"❌ 网络错误: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="完整的 SheerID 验证 URL")
    parser.add_argument("--proxy", help="使用的代理(可选)")
    args = parser.parse_args()
    
    get_status(args.url, args.proxy)
