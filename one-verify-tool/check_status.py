import httpx
import re
import sys
import argparse

SHEERID_API_URL = "https://services.sheerid.com/rest/v2"

def get_status(url):
    match = re.search(r"verificationId=([a-f0-9]+)", url, re.IGNORECASE)
    if not match:
        print("❌ 错误: 无效的验证 URL")
        return
    
    vid = match.group(1)
    print(f"\n🔍 Querying SheerID status for: {vid}...")
    headers = {"Accept": "application/json"}

    try:
        resp = httpx.get(f"{SHEERID_API_URL}/verification/{vid}", headers=headers, timeout=10)
        data = resp.json()
        step = data.get("currentStep")
        error_ids = data.get("errorIds", [])
        
        print("-" * 50)
        print(f"📍 当前状态 (currentStep): {step}")
        if error_ids:
            print(f"⚠️  错误标记 (errorIds): {error_ids}")
        
        if step == "pending":
            print("⏳ 状态解读: 正在人工审核中。请等待。")
        elif step == "docUpload":
            print("❌ 状态解读: 目前在文件上传阶段。")
            if error_ids:
                print("   🚫 之前的提交已被系统自动打回，请尝试换一个学校生成新的证明文件。")
        elif step == "success":
            print("✅ 状态解读: 认证已通过！")
        else:
            print(f"❓ 状态解读: 目前在 '{step}' 阶段。")
            
        print(f"\n📊 完整 API 响应 (用于分析原因):\n{data}")
        print("-" * 50)
            
    except Exception as e:
        print(f"❌ 网络错误: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args()
    get_status(args.url)
