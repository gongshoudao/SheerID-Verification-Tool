import httpx
import sys

def check_ip():
    print("\n🔍 Checking IP Intelligence...")
    print("-" * 40)
    
    try:
        # 使用 ip-api.com 获取详细信息，包含机房/托管检测
        # fields=66846719 包含了 proxy, mobile, hosting 等高级检测
        url = "http://ip-api.com/json/?fields=66846719"
        
        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            data = resp.json()
            
        if data.get("status") != "success":
            print(f"❌ Error fetching IP info: {data.get('message')}")
            return

        ip = data.get("query")
        country = data.get("country")
        country_code = data.get("countryCode")
        isp = data.get("isp")
        org = data.get("org")
        as_name = data.get("as")
        is_hosting = data.get("hosting")  # 是否为机房/托管
        is_proxy = data.get("proxy")      # 是否为代理
        
        print(f"📍 Public IP: {ip}")
        print(f"🌍 Location: {country} ({country_code})")
        print(f"🏢 ISP: {isp}")
        print(f"🏢 Organization: {org}")
        print(f"🏢 AS: {as_name}")
        
        print("-" * 40)
        
        # 验证逻辑
        is_valid = True
        
        # 1. 国家检查
        if country_code != "US":
            print("❌ FAILED: Not a US IP!")
            is_valid = False
        else:
            print("✅ PASS: US IP detected.")
            
        # 2. 住宅/机房性质检查
        if is_hosting:
            print("❌ FAILED: This is a DATACENTER/HOSTING IP (机房/机房IP)!")
            print("   (SheerID strongly blocks datacenter IPs like AWS, Azure, Google, etc.)")
            is_valid = False
        else:
            # 简单判断是否符合常见住宅 ISP 关键词
            residential_keywords = ["Comcast", "AT&T", "Verizon", "Spectrum", "Cox", "Charter", "Frontier", "Optimum", "T-Mobile", "Lumen"]
            is_likely_residential = any(k.lower() in isp.lower() for k in residential_keywords)
            
            if is_likely_residential:
                print("✅ PASS: Likely a RESIDENTIAL IP (住宅IP).")
            else:
                print("⚠️  WARNING: Unknown ISP type. Could be a small local residential or a stealth proxy.")
                
        # 3. 代理检查
        if is_proxy:
            print("⚠️  WARNING: Proxy/VPN detected by IP-API database.")
        
        if is_valid:
            print("\n🌟 CONCLUSION: Your IP looks GOOD for SheerID verification.")
        else:
            print("\n🚨 CONCLUSION: Your IP is likely to be REJECTED by SheerID.")
            
    except Exception as e:
        print(f"❌ Network Error: {e}")

if __name__ == "__main__":
    check_ip()
