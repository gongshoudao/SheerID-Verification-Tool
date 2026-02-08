import httpx
import re
import sys
import argparse

SHEERID_API_URL = "https://services.sheerid.com/rest/v2"

def get_status(url):
    # 解析 Verification ID
    match = re.search(r"verificationId=([a-f0-9]+)", url, re.IGNORECASE)
    if not match:
        print("❌ 错误: 无效的验证 URL，找不到 verificationId")
        return
    
    vid = match.group(1)
    print(f"\n🔍 Querying SheerID status for: {vid}...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    try:
        # 直接使用 httpx.get 简单快速
        resp = httpx.get(f"{SHEERID_API_URL}/verification/{vid}", headers=headers, timeout=10)
        
        if resp.status_code != 200:
            print(f"❌ API 请求失败 (HTTP {resp.status_code})")
            print(f"   原因: {resp.text}")
            return

        data = resp.json()
        step = data.get("currentStep")
        
        print("-" * 50)
        print(f"📍 当前状态 (currentStep): {step}")
        
        if step == "pending":
            print("⏳ 状态解读: 正在人工审核/高级OCR处理中。请继续等待 24h 内的结果。")
        elif step == "success":
            print("✅ 状态解读: 认证已通过！你可以回浏览器完成订阅了。")
        elif step == "error" or step == "rejected":
            errors = data.get("errorIds", [])
            print(f"❌ 状态解读: 认证被拒绝。失败原因: {errors}")
        elif step == "collectStudentPersonalInfo":
            print("📝 状态解读: 信息未提交。如果之前提交过，说明刚才的提交已被重置。")
        else:
            print(f"❓ 状态解读: 目前在 '{step}' 阶段，请检查浏览器页面。")
        
        print("-" * 50)
            
    except Exception as e:
        print(f"❌ 网络错误: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="SheerID 验证 URL")
    args = parser.parse_args()
    
    get_status(args.url)
