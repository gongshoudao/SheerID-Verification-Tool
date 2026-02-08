"""
Google One (Gemini) Student Verification Tool
SheerID Student Verification for Google One AI Premium

⚠️  IMPORTANT NOTICE (Jan 2026):
Google has changed Gemini student verification to US-ONLY for new sign-ups.
Users from other countries may experience high failure rates.

Enhanced with:
- Success rate tracking per organization
- Weighted university selection (US schools prioritized)
- Retry with exponential backoff
- Rate limiting avoidance
- Anti-detection with Chrome TLS impersonation

Requirements:
- curl_cffi: pip install curl_cffi (CRITICAL for TLS spoofing)
- Residential proxy matching US location (STRONGLY recommended)

Author: ThanhNguyxn
"""

import os
import re
import sys
import json
import time
import random
import hashlib
from pathlib import Path
from io import BytesIO
from typing import Dict, Optional, Tuple
from functools import wraps

try:
    import httpx
except ImportError:
    print("❌ Error: httpx required. Install: pip install httpx")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("❌ Error: Pillow required. Install: pip install Pillow")
    sys.exit(1)

# Import anti-detection module
try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from anti_detect import (
        get_headers,
        get_fingerprint,
        get_random_user_agent,
        random_delay as anti_delay,
        create_session,
        get_matched_ua_for_impersonate,
        make_request,
        handle_fraud_rejection,
        should_retry_fraud,
    )

    HAS_ANTI_DETECT = True
    print("[INFO] Anti-detection module loaded")
except ImportError:
    HAS_ANTI_DETECT = False
    print("[WARN] anti_detect.py not found, using basic headers")
    print("[WARN] Detection risk is HIGH without anti_detect module!")


# ============ CONFIG ============
PROGRAM_ID = "67c8c14f5f17a83b745e3f82"
SHEERID_API_URL = "https://services.sheerid.com/rest/v2"
MIN_DELAY = 300
MAX_DELAY = 800


# ============ STATS TRACKING ============
class Stats:
    """Track success rates by organization"""

    def __init__(self):
        self.file = Path(__file__).parent / "stats.json"
        self.data = self._load()

    def _load(self) -> Dict:
        if self.file.exists():
            try:
                return json.loads(self.file.read_text())
            except:
                pass
        return {"total": 0, "success": 0, "failed": 0, "orgs": {}}

    def _save(self):
        self.file.write_text(json.dumps(self.data, indent=2))

    def record(self, org: str, success: bool):
        self.data["total"] += 1
        self.data["success" if success else "failed"] += 1

        if org not in self.data["orgs"]:
            self.data["orgs"][org] = {"success": 0, "failed": 0}
        self.data["orgs"][org]["success" if success else "failed"] += 1
        self._save()

    def get_rate(self, org: str = None) -> float:
        if org:
            o = self.data["orgs"].get(org, {})
            total = o.get("success", 0) + o.get("failed", 0)
            return o.get("success", 0) / total * 100 if total else 50
        return (
            self.data["success"] / self.data["total"] * 100 if self.data["total"] else 0
        )

    def print_stats(self):
        print(f"\n📊 Statistics:")
        print(
            f"   Total: {self.data['total']} | ✅ {self.data['success']} | ❌ {self.data['failed']}"
        )
        if self.data["total"]:
            print(f"   Success Rate: {self.get_rate():.1f}%")


stats = Stats()


# ============ UNIVERSITIES WITH WEIGHTS ============
# NOTE: As of Jan 2026, new Gemini student sign-ups are US-ONLY
# Other countries may work for existing users but new sign-ups restricted

UNIVERSITIES = [
    # =========== USA - HIGH PRIORITY ===========
    # These have highest success rates for new sign-ups
    {
        "id": 2565,
        "name": "Pennsylvania State University-Main Campus",
        "domain": "psu.edu",
        "weight": 100,
    },
    {
        "id": 3499,
        "name": "University of California, Los Angeles",
        "domain": "ucla.edu",
        "weight": 98,
    },
    {
        "id": 3491,
        "name": "University of California, Berkeley",
        "domain": "berkeley.edu",
        "weight": 97,
    },
    {
        "id": 1953,
        "name": "Massachusetts Institute of Technology",
        "domain": "mit.edu",
        "weight": 95,
    },
    {"id": 3113, "name": "Stanford University", "domain": "stanford.edu", "weight": 95},
    {"id": 2285, "name": "New York University", "domain": "nyu.edu", "weight": 96},
    {"id": 1426, "name": "Harvard University", "domain": "harvard.edu", "weight": 92},
    {"id": 590759, "name": "Yale University", "domain": "yale.edu", "weight": 90},
    {
        "id": 2626,
        "name": "Princeton University",
        "domain": "princeton.edu",
        "weight": 90,
    },
    {"id": 698, "name": "Columbia University", "domain": "columbia.edu", "weight": 92},
    {
        "id": 3508,
        "name": "University of Chicago",
        "domain": "uchicago.edu",
        "weight": 88,
    },
    {"id": 943, "name": "Duke University", "domain": "duke.edu", "weight": 88},
    {"id": 751, "name": "Cornell University", "domain": "cornell.edu", "weight": 90},
    {
        "id": 2420,
        "name": "Northwestern University",
        "domain": "northwestern.edu",
        "weight": 88,
    },
    # More US Universities
    {"id": 3568, "name": "University of Michigan", "domain": "umich.edu", "weight": 95},
    {
        "id": 3686,
        "name": "University of Texas at Austin",
        "domain": "utexas.edu",
        "weight": 94,
    },
    {
        "id": 1217,
        "name": "Georgia Institute of Technology",
        "domain": "gatech.edu",
        "weight": 93,
    },
    {
        "id": 602,
        "name": "Carnegie Mellon University",
        "domain": "cmu.edu",
        "weight": 92,
    },
    {
        "id": 3477,
        "name": "University of California, San Diego",
        "domain": "ucsd.edu",
        "weight": 93,
    },
    {
        "id": 3600,
        "name": "University of North Carolina at Chapel Hill",
        "domain": "unc.edu",
        "weight": 90,
    },
    {
        "id": 3645,
        "name": "University of Southern California",
        "domain": "usc.edu",
        "weight": 91,
    },
    {
        "id": 3629,
        "name": "University of Pennsylvania",
        "domain": "upenn.edu",
        "weight": 90,
    },
    {
        "id": 1603,
        "name": "Indiana University Bloomington",
        "domain": "iu.edu",
        "weight": 88,
    },
    {"id": 2506, "name": "Ohio State University", "domain": "osu.edu", "weight": 90},
    {"id": 2700, "name": "Purdue University", "domain": "purdue.edu", "weight": 89},
    {"id": 3761, "name": "University of Washington", "domain": "uw.edu", "weight": 90},
    {
        "id": 3770,
        "name": "University of Wisconsin-Madison",
        "domain": "wisc.edu",
        "weight": 88,
    },
    {"id": 3562, "name": "University of Maryland", "domain": "umd.edu", "weight": 87},
    {"id": 519, "name": "Boston University", "domain": "bu.edu", "weight": 86},
    {"id": 378, "name": "Arizona State University", "domain": "asu.edu", "weight": 92},
    {"id": 3521, "name": "University of Florida", "domain": "ufl.edu", "weight": 90},
    {
        "id": 3535,
        "name": "University of Illinois at Urbana-Champaign",
        "domain": "illinois.edu",
        "weight": 91,
    },
    {
        "id": 3557,
        "name": "University of Minnesota Twin Cities",
        "domain": "umn.edu",
        "weight": 88,
    },
    {
        "id": 3483,
        "name": "University of California, Davis",
        "domain": "ucdavis.edu",
        "weight": 89,
    },
    {
        "id": 3487,
        "name": "University of California, Irvine",
        "domain": "uci.edu",
        "weight": 88,
    },
    {
        "id": 3502,
        "name": "University of California, Santa Barbara",
        "domain": "ucsb.edu",
        "weight": 87,
    },
    # Community Colleges (may have higher success)
    {"id": 2874, "name": "Santa Monica College", "domain": "smc.edu", "weight": 85},
    {
        "id": 2350,
        "name": "Northern Virginia Community College",
        "domain": "nvcc.edu",
        "weight": 84,
    },
    # =========== OTHER COUNTRIES (Lower priority - may not work for new sign-ups) ===========
    # Canada
    {
        "id": 328355,
        "name": "University of Toronto",
        "domain": "utoronto.ca",
        "weight": 40,
    },
    {
        "id": 328315,
        "name": "University of British Columbia",
        "domain": "ubc.ca",
        "weight": 38,
    },
    # UK
    {"id": 273409, "name": "University of Oxford", "domain": "ox.ac.uk", "weight": 35},
    {
        "id": 273378,
        "name": "University of Cambridge",
        "domain": "cam.ac.uk",
        "weight": 35,
    },
    # India (likely blocked for new sign-ups)
    {
        "id": 10007277,
        "name": "Indian Institute of Technology Delhi",
        "domain": "iitd.ac.in",
        "weight": 20,
    },
    {"id": 3819983, "name": "University of Mumbai", "domain": "mu.ac.in", "weight": 15},
    # Australia
    {
        "id": 345301,
        "name": "The University of Melbourne",
        "domain": "unimelb.edu.au",
        "weight": 30,
    },
    {
        "id": 345303,
        "name": "The University of Sydney",
        "domain": "sydney.edu.au",
        "weight": 28,
    },
]


def select_university(manual_name: str = None) -> Dict:
    """Weighted random selection based on success rates or manual selection"""
    if manual_name:
        mn = manual_name.lower()
        for uni in UNIVERSITIES:
            # 同时匹配校名和域名(例如 ucla.edu)
            if mn in uni["name"].lower() or mn in uni["domain"].lower():
                print(f"   🎯 Manually selected school: {uni['name']}")
                return {**uni, "idExtended": str(uni["id"])}
        print(f"   ⚠️  Manual school '{manual_name}' not found in list, falling back to random.")

    weights = []
    for uni in UNIVERSITIES:
        weight = uni["weight"] * (stats.get_rate(uni["name"]) / 50)
        weights.append(max(1, weight))

    total = sum(weights)
    r = random.uniform(0, total)

    cumulative = 0
    for uni, weight in zip(UNIVERSITIES, weights):
        cumulative += weight
        if r <= cumulative:
            return {**uni, "idExtended": str(uni["id"])}
    return {**UNIVERSITIES[0], "idExtended": str(UNIVERSITIES[0]["id"])}


# ============ UTILITIES ============
FIRST_NAMES = [
    "James",
    "John",
    "Robert",
    "Michael",
    "William",
    "David",
    "Richard",
    "Joseph",
    "Thomas",
    "Christopher",
    "Charles",
    "Daniel",
    "Matthew",
    "Anthony",
    "Mark",
    "Donald",
    "Steven",
    "Andrew",
    "Paul",
    "Joshua",
    "Kenneth",
    "Kevin",
    "Brian",
    "George",
    "Timothy",
    "Ronald",
    "Edward",
    "Jason",
    "Jeffrey",
    "Ryan",
    "Mary",
    "Patricia",
    "Jennifer",
    "Linda",
    "Barbara",
    "Elizabeth",
    "Susan",
    "Jessica",
    "Sarah",
    "Karen",
    "Lisa",
    "Nancy",
    "Betty",
    "Margaret",
    "Sandra",
    "Ashley",
    "Kimberly",
    "Emily",
    "Donna",
    "Michelle",
    "Dorothy",
    "Carol",
    "Amanda",
    "Melissa",
    "Deborah",
    "Stephanie",
    "Rebecca",
    "Sharon",
    "Laura",
    "Emma",
    "Olivia",
    "Ava",
    "Isabella",
    "Sophia",
    "Mia",
    "Charlotte",
    "Amelia",
]
LAST_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Hernandez",
    "Lopez",
    "Gonzalez",
    "Wilson",
    "Anderson",
    "Thomas",
    "Taylor",
    "Moore",
    "Jackson",
    "Martin",
    "Lee",
    "Perez",
    "Thompson",
    "White",
    "Harris",
    "Sanchez",
    "Clark",
    "Ramirez",
    "Lewis",
    "Robinson",
    "Walker",
    "Young",
    "Allen",
    "King",
    "Wright",
    "Scott",
    "Torres",
    "Nguyen",
    "Hill",
    "Flores",
    "Green",
    "Adams",
    "Nelson",
    "Baker",
    "Hall",
    "Rivera",
    "Campbell",
    "Mitchell",
    "Carter",
    "Roberts",
    "Turner",
    "Phillips",
    "Evans",
    "Parker",
    "Edwards",
]


def random_delay():
    time.sleep(random.randint(MIN_DELAY, MAX_DELAY) / 1000)


def generate_fingerprint() -> str:
    """Generate realistic browser fingerprint to avoid fraud detection"""
    # Realistic screen resolutions
    resolutions = [
        "1920x1080",
        "1366x768",
        "1536x864",
        "1440x900",
        "1280x720",
        "2560x1440",
    ]
    # Common timezones
    timezones = [-8, -7, -6, -5, -4, 0, 1, 2, 3, 5.5, 8, 9, 10]
    # Common languages
    languages = ["en-US", "en-GB", "en-CA", "en-AU", "es-ES", "fr-FR", "de-DE", "pt-BR"]
    # Common platforms
    platforms = ["Win32", "MacIntel", "Linux x86_64"]
    # Browser vendors
    vendors = ["Google Inc.", "Apple Computer, Inc.", ""]

    components = [
        str(int(time.time() * 1000)),
        str(random.random()),
        random.choice(resolutions),
        str(random.choice(timezones)),
        random.choice(languages),
        random.choice(platforms),
        random.choice(vendors),
        str(random.randint(1, 16)),  # hardware concurrency (CPU cores)
        str(random.randint(2, 32)),  # device memory GB
        str(random.randint(0, 1)),  # touch support
    ]
    return hashlib.md5("|".join(components).encode()).hexdigest()


def generate_name() -> Tuple[str, str]:
    return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)


def generate_email(first: str, last: str, domain: str) -> str:
    patterns = [
        f"{first[0].lower()}{last.lower()}{random.randint(100, 999)}",
        f"{first.lower()}.{last.lower()}{random.randint(10, 99)}",
        f"{last.lower()}{first[0].lower()}{random.randint(100, 999)}",
    ]
    return f"{random.choice(patterns)}@{domain}"


def generate_birth_date() -> str:
    year = random.randint(2000, 2006)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"

def post_process_image(img: Image.Image) -> Image.Image:
    """Add noise and slight rotation to make document look real"""
    from PIL import ImageFilter, ImageEnhance
    import numpy as np
    
    # 1. Slight rotation to simulate scanning/photo
    angle = random.uniform(-0.5, 0.5)
    img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(255,255,255))
    
    # 2. Add subtle grain/noise
    try:
        import numpy as np
        img_array = np.array(img).astype(np.float32)
        noise = np.random.normal(0, 3, img_array.shape) # subtle noise
        noisy_img = np.clip(img_array + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(noisy_img)
    except ImportError:
        # Fallback if numpy is not installed: skip noise
        pass
    
    # 3. Subtle blur and contrast adjustment
    img = img.filter(ImageFilter.GaussianBlur(radius=0.3))
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(random.uniform(0.95, 1.05))
    
    return img

def get_fonts(sizes=[32, 24, 16], font_type="sans"):
    """Enhanced font selection: Mac & Linux support, Serif & Sans-Serif"""
    # 针对印章建议使用 serif (衬线体)
    if font_type == "serif":
        font_paths = [
            "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/Library/Fonts/Georgia.ttf",
            "times.ttf"
        ]
        bold_paths = [
            "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
            "timesbd.ttf"
        ]
    else:
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/Library/Fonts/Arial.ttf",
            "arial.ttf"
        ]
        bold_paths = [
            "/System/Library/Fonts/Helvetica-Bold.ttc",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "arialbd.ttf"
        ]
    
    res = []
    for s in sizes:
        f = None
        for p in font_paths:
            try:
                f = ImageFont.truetype(p, s)
                break
            except: continue
        res.append(f if f else ImageFont.load_default())
        
    f_bold = None
    for p in bold_paths:
        try:
            f_bold = ImageFont.truetype(p, sizes[-1])
            break
        except: continue
    res.append(f_bold if f_bold else ImageFont.load_default())
    
    return res # [f1, f2, f3, ..., f_bold]

def draw_circular_text(draw, center, radius, text, font, color, start_angle):
    """Helper to draw text along a circular path"""
    from math import sin, cos, radians
    cx, cy = center
    # Calculate angular spacing for characters
    # Very rough estimate of total angle based on text length
    angle_step = 160 / max(1, len(text)) 
    
    for i, char in enumerate(text):
        angle = start_angle + (i * angle_step)
        # Position on circle
        x = cx + radius * cos(radians(angle))
        y = cy + radius * sin(radians(angle))
        
        # Create a small temp image for the character to rotate it
        char_img = Image.new("RGBA", (int(font.size * 2), int(font.size * 2)), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_img)
        char_draw.text((font.size, font.size), char, fill=color, font=font, anchor="mm")
        
        # Rotation should be perpendicular to the radius
        rotated_char = char_img.rotate(-angle - 90, expand=False, resample=Image.BICUBIC)
        
        # Paste onto main image
        char_bbox = (int(x - font.size), int(y - font.size))
        draw._image.paste(rotated_char, char_bbox, rotated_char)


# ============ DOCUMENT GENERATOR ============
# ============ DOCUMENT GENERATOR ============
def generate_transcript(first: str, last: str, school: str, dob: str) -> bytes:
    """Generate fake academic transcript (higher success rate)"""
    w, h = 850, 1100
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Try to get real fonts
    # 优先寻找衬线体(Serif/Times)用于正式文档
    font_header, font_title, font_text, font_sm, font_bold = get_fonts([32, 24, 16, 12], "serif")

    # 1. Header
    draw.text(
        (w // 2, 50), school.upper(), fill=(0, 0, 0), font=font_header, anchor="mm"
    )
    draw.text(
        (w // 2, 90),
        "OFFICIAL ACADEMIC TRANSCRIPT",
        fill=(50, 50, 50),
        font=font_title,
        anchor="mm",
    )
    draw.line([(50, 110), (w - 50, 110)], fill=(0, 0, 0), width=2)

    # 2. Student Info
    y = 150
    draw.text((50, y), f"Student Name: {first} {last}", fill=(0, 0, 0), font=font_bold)
    draw.text(
        (w - 300, y),
        f"Student ID: {random.randint(10000000, 99999999)}",
        fill=(0, 0, 0),
        font=font_text,
    )
    y += 30
    draw.text((50, y), f"Date of Birth: {dob}", fill=(0, 0, 0), font=font_text)
    draw.text(
        (w - 300, y),
        f"Date Issued: {time.strftime('%Y-%m-%d')}",
        fill=(0, 0, 0),
        font=font_text,
    )
    y += 40

    # 3. Current Enrollment Status
    draw.rectangle([(50, y), (w - 50, y + 40)], fill=(240, 240, 240))
    draw.text(
        (w // 2, y + 20),
        "CURRENT STATUS: ENROLLED (SPRING 2025)",
        fill=(0, 100, 0),
        font=font_bold,
        anchor="mm",
    )
    y += 70

    # 4. Courses
    courses = [
        ("CS 101", "Intro to Computer Science", "4.0", "A"),
        ("MATH 201", "Calculus I", "3.0", "A-"),
        ("ENG 102", "Academic Writing", "3.0", "B+"),
        ("PHYS 150", "Physics for Engineers", "4.0", "A"),
        ("HIST 110", "World History", "3.0", "A"),
    ]

    # Table Header
    draw.text((50, y), "Course Code", font=font_bold, fill=(0, 0, 0))
    draw.text((200, y), "Course Title", font=font_bold, fill=(0, 0, 0))
    draw.text((600, y), "Credits", font=font_bold, fill=(0, 0, 0))
    draw.text((700, y), "Grade", font=font_bold, fill=(0, 0, 0))
    y += 20
    draw.line([(50, y), (w - 50, y)], fill=(0, 0, 0), width=1)
    y += 20

    for code, title, cred, grade in courses:
        draw.text((50, y), code, font=font_text, fill=(0, 0, 0))
        draw.text((200, y), title, font=font_text, fill=(0, 0, 0))
        draw.text((600, y), cred, font=font_text, fill=(0, 0, 0))
        draw.text((700, y), grade, font=font_text, fill=(0, 0, 0))
        y += 30

    y += 20
    draw.line([(50, y), (w - 50, y)], fill=(0, 0, 0), width=1)
    y += 30

    # 5. Summary
    draw.text((50, y), "Cumulative GPA: 3.85", font=font_bold, fill=(0, 0, 0))
    draw.text((w - 300, y), "Academic Standing: Good", font=font_bold, fill=(0, 0, 0))

    # 7. ADD WATERMARK (Diagonal text)
    watermark_text = school.upper()
    temp_img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    temp_draw = ImageDraw.Draw(temp_img)
    # Draw faint diagonal text
    for i in range(0, h, 200):
        for j in range(-200, w, 300):
            temp_draw.text((j, i), watermark_text, fill=(200, 200, 200, 30), font=font_text)
    temp_img = temp_img.rotate(30, expand=False)
    img.paste(temp_img, (0, 0), temp_img)

    # 8. ADD UNIVERSITY SEAL (Registrar Style - circular text)
    seal_color = (30, 60, 130, 220) # Deeper Navy
    r = 75
    cx, cy = w - 160, h - 200
    
    # Fonts for seal (Serif!)
    s_f_md, s_f_sm, s_f_bold = get_fonts([14, 10, 16], "serif")[1:]

    # Draw circles
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=seal_color, width=2)
    draw.ellipse([cx-r+5, cy-r+5, cx+r-5, cy+r-5], outline=seal_color, width=1)
    
    # Top curved text (OFFICE OF THE REGISTRAR)
    draw_circular_text(draw, (cx, cy), r - 15, "OFFICE OF THE REGISTRAR", s_f_bold, seal_color, 195)
    
    # Bottom curved text (AUTHENTICATED)
    draw_circular_text(draw, (cx, cy), r - 15, f"VERIFIED {time.strftime('%Y')}", s_f_sm, seal_color, 25)

    # Center text
    draw.text((cx, cy-5), "OFFICIAL", fill=seal_color, font=s_f_md, anchor="mm")
    draw.text((cx, cy+15), "TRANSCRIPT", fill=seal_color, font=s_f_md, anchor="mm")

    # 6. Watermark / Footer
    draw.text(
        (w // 2, h - 50),
        "This document is electronically generated and valid without signature.",
        fill=(100, 100, 100),
        font=font_text,
        anchor="mm",
    )

    buf = BytesIO()
    img = post_process_image(img)
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_student_id(first: str, last: str, school: str) -> bytes:
    """Generate high-quality direct student ID scan with real user photo"""
    w, h = 650, 400
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # 1. Background Pattern
    for i in range(0, h, 10):
        draw.line([(0, i), (w, i + 30)], fill=(240, 245, 255), width=1)
    
    font_lg, font_md, font_sm, _, font_bold = get_fonts([28, 18, 12, 20])
    
    # 2. Header
    header_color = (25, 50, 100)
    draw.rectangle([(0, 0), (w, 80)], fill=header_color)
    draw.text((30, 40), school.upper(), fill=(255, 220, 100), font=font_bold, anchor="lm")
    
    # 3. Photo Area
    photo_box = (40, 110, 170, 275) # (x1, y1, x2, y2)
    # Attempt to load a real photo
    photo_pasted = False
    try:
        # Determine gender based on name (very simple heuristic) or random
        # In a real tool, we might want to store this in persona
        gender = random.choice(["male", "female"])
        photo_dir = Path(__file__).parent / "photos" / gender
        if photo_dir.exists():
            photos = list(photo_dir.glob("*.png"))
            if photos:
                user_photo = Image.open(random.choice(photos)).convert("RGBA")
                # Scale photo to fit box
                box_w = photo_box[2] - photo_box[0]
                box_h = photo_box[3] - photo_box[1]
                user_photo.thumbnail((box_w, box_h), Image.LANCZOS)
                # Center it in the box
                offset_x = photo_box[0] + (box_w - user_photo.width) // 2
                offset_y = photo_box[1] + (box_h - user_photo.height) // 2
                img.paste(user_photo, (offset_x, offset_y), user_photo)
                photo_pasted = True
    except Exception as e:
        print(f"   ⚠️  Failed to load photo: {e}")

    if not photo_pasted:
        # Fallback to silhouette if no photo available
        draw.rectangle([photo_box[0], photo_box[1], photo_box[2], photo_box[3]], 
                      outline=(150, 150, 150), width=1, fill=(235, 235, 235))
        draw.ellipse([(80, 130), (130, 180)], fill=(180, 180, 180))
        draw.chord([(60, 180), (150, 260)], start=180, end=0, fill=(180, 180, 180))
    
    # 4. Info Section
    x_i = 200
    draw.text((x_i, 115), f"{first.upper()} {last.upper()}", fill=(0, 0, 0), font=font_lg)
    y_s = 175
    student_id = str(random.randint(20000000, 29999999))
    for label, val in [("STUDENT ID:", student_id), 
                       ("ROLE:", "STUDENT (UNDERGRAD)"),
                       ("VAL THROUGH:", f"05/31/{int(time.strftime('%Y')) + 2}")]:
        draw.text((x_i, y_s), label, fill=(120, 120, 120), font=font_sm)
        draw.text((x_i + 110, y_s), val, fill=(0, 0, 0), font=font_md)
        y_s += 40

    # 5. Barcode (Much more common on real US IDs than a signature)
    bar_x, bar_y = 200, 310
    draw.rectangle([bar_x, bar_y, w-40, bar_y+40], fill=(255,255,255))
    # Draw simple barcode pattern
    for i in range(bar_x, w-60, 4):
        if random.random() > 0.3:
            w_b = random.choice([1, 2, 3])
            draw.rectangle([i, bar_y, i+w_b, bar_y+30], fill=(0,0,0))
    draw.text((w/2 + 80, bar_y + 35), f"*{student_id}*", fill=(50, 50, 50), font=font_sm, anchor="mm")

    # 6. Security Hologram
    h_p = (560, 120)
    for i in range(12):
        draw.regular_polygon((h_p, 30), n_sides=6, rotation=i*15, outline=(200, 210, 255))
    draw.text(h_p, "VERIFIED", fill=(100, 100, 250), font=font_sm, anchor="mm")

    # Post-process for realism (Noise, Slight blur)
    img = img.convert("RGB")
    img = post_process_image(img)
    
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

    # Apply Post-processing for realism
    final_img = post_process_image(final_img)
    
    buf = BytesIO()
    final_img.save(buf, format="PNG")
    return buf.getvalue()

def find_coeffs(pa, pb):
    """
    Calculate coefficients for perspective transformation.
    Maps pa[i] to pb[i].
    For PIL transform, pa should be target corners, pb should be source corners.
    """
    try:
        import numpy as np
        matrix = []
        for p1, p2 in zip(pa, pb):
            matrix.append([p1[0], p1[1], 1, 0, 0, 0, -p2[0]*p1[0], -p2[0]*p1[1]])
            matrix.append([0, 0, 0, p1[0], p1[1], 1, -p2[1]*p1[0], -p2[1]*p1[1]])
        A = np.array(matrix, dtype=float)
        B = np.array(pb).reshape(8)
        res = np.linalg.solve(A, B)
        return res
    except ImportError:
        # Fallback to identity if numpy not found
        return [1, 0, 0, 0, 1, 0, 0, 0]
    except Exception as e:
        print(f"   ⚠️  Matrix solve failed: {e}")
        return [1, 0, 0, 0, 1, 0, 0, 0]


# ============ VERIFIER ============
class GeminiVerifier:
    """Gemini Student Verification with enhanced features"""

    def __init__(self, url: str, proxy: str = None):
        self.url = url
        self.vid = self._parse_id(url)
        self.fingerprint = generate_fingerprint()

        # Use enhanced anti-detection session
        if HAS_ANTI_DETECT:
            self.client, self.lib_name, self.impersonate_target = create_session(proxy)
            print(
                f"[INFO] Session created using {self.lib_name} (Impersonating: {self.impersonate_target})"
            )
        else:
            proxy_url = None
            if proxy:
                if not proxy.startswith("http"):
                    proxy = f"http://{proxy}"
                proxy_url = proxy
            self.client = httpx.Client(timeout=30, proxy=proxy_url)
            self.lib_name = "httpx"

        self.org = None

    def __del__(self):
        if hasattr(self, "client"):
            self.client.close()

    @staticmethod
    def _parse_id(url: str) -> Optional[str]:
        match = re.search(r"verificationId=([a-f0-9]+)", url, re.IGNORECASE)
        return match.group(1) if match else None

    def _request(
        self, method: str, endpoint: str, body: Dict = None
    ) -> Tuple[Dict, int]:
        random_delay()
        url = f"{SHEERID_API_URL}{endpoint}"
        
        # Verbose Logging
        print(f"\n      🌐 Request: {method} {url}")
        if body:
            print(f"      📦 Body: {json.dumps(body, indent=2, ensure_ascii=False)}")
            
        try:
            # Use anti-detect headers if available
            headers = (
                get_headers(for_sheerid=True)
                if HAS_ANTI_DETECT
                else {"Content-Type": "application/json"}
            )
            resp = self.client.request(
                method, url, json=body, headers=headers
            )
            
            try:
                parsed = resp.json() if resp.text else {}
            except Exception:
                parsed = {"_text": resp.text}
            
            # Verbose Logging 
            print(f"      📥 Response: {resp.status_code}")
            if parsed:
                print(f"      📄 Content: {json.dumps(parsed, indent=2, ensure_ascii=False)}")
                
            return parsed, resp.status_code
        except Exception as e:
            print(f"      ❌ Request Error: {e}")
            raise Exception(f"Request failed: {e}")

    def _upload_s3(self, url: str, data: bytes) -> bool:
        # Different session implementations accept different kw names
        # Try several variants to maximize compatibility (curl_cffi, httpx, requests)
        attempts = []
        # First try: common httpx signature
        attempts.append(
            lambda: self.client.put(
                url, content=data, headers={"Content-Type": "image/png"}, timeout=60
            )
        )
        # Second try: requests-like signature
        attempts.append(
            lambda: self.client.put(
                url, data=data, headers={"Content-Type": "image/png"}, timeout=60
            )
        )
        # Third try: generic request method
        attempts.append(
            lambda: self.client.request(
                "PUT", url, data=data, headers={"Content-Type": "image/png"}, timeout=60
            )
        )

        last_exc = None
        for fn in attempts:
            try:
                resp = fn()
                if hasattr(resp, "status_code"):
                    if 200 <= resp.status_code < 300:
                        return True
                    try:
                        body = resp.json()
                    except Exception:
                        body = getattr(resp, "text", str(resp))
                    print(f"     ❗ S3 upload failed: HTTP {resp.status_code} | {body}")
                    return False
                else:
                    # If resp is not a requests-like object, treat success if truthy
                    if resp:
                        return True
                    return False
            except TypeError as e:
                last_exc = e
                continue
            except Exception as e:
                last_exc = e
                continue

        print(f"     ❗ S3 upload failed after attempts. Last error: {last_exc}")
        return False

    def check_link(self) -> Dict:
        """Check if verification link is valid"""
        if not self.vid:
            return {"valid": False, "error": "Invalid URL"}

        data, status = self._request("GET", f"/verification/{self.vid}")
        if status != 200:
            return {"valid": False, "error": f"HTTP {status}"}

        step = data.get("currentStep", "")
        # Accept multiple valid steps - handle re-upload after rejection
        valid_steps = ["collectStudentPersonalInfo", "docUpload", "sso"]
        if step in valid_steps:
            return {"valid": True, "step": step}
        elif step == "success":
            return {"valid": False, "error": "Already verified"}
        elif step == "pending":
            return {"valid": False, "error": "Already pending review"}
        return {"valid": False, "error": f"Invalid step: {step}"}

    def verify(self, **kwargs) -> Dict:
        """Run full verification"""
        if not self.vid:
            return {"success": False, "error": "Invalid verification URL"}

        try:
            # Check current step first
            check_data, check_status = self._request("GET", f"/verification/{self.vid}")
            current_step = (
                check_data.get("currentStep", "") if check_status == 200 else ""
            )

            # Generate info
            first, last = generate_name()
            self.org = select_university(kwargs.get("manual_school"))
            email = generate_email(first, last, self.org["domain"])
            dob = generate_birth_date()

            print(f"\n   🎓 Student: {first} {last}")
            print(f"   📧 Email: {email}")
            print(f"   🏫 School: {self.org['name']}")
            print(f"   🎂 DOB: {dob}")
            print(f"   🔑 ID: {self.vid[:20]}...")
            print(f"   📍 Starting step: {current_step}")

            # Step 1: Generate document
            doc_type = "transcript" if random.random() < 0.7 else "id_card"
            if doc_type == "transcript":
                print("\n   ▶ Step 1/3: Generating academic transcript...")
                doc = generate_transcript(first, last, self.org["name"], dob)
                filename = "transcript.png"
            else:
                print("\n   ▶ Step 1/3: Generating student ID...")
                doc = generate_student_id(first, last, self.org["name"])
                filename = "student_card.png"
            print(f"     📄 Size: {len(doc) / 1024:.1f} KB")

            # Step 2: Submit info (skip if already past this step)
            if current_step == "collectStudentPersonalInfo":
                print("   ▶ Step 2/3: Submitting student info...")
                body = {
                    "firstName": first,
                    "lastName": last,
                    "birthDate": dob,
                    "email": email,
                    "phoneNumber": "",
                    "organization": {
                        "id": self.org["id"],
                        "idExtended": self.org["idExtended"],
                        "name": self.org["name"],
                    },
                    "deviceFingerprintHash": self.fingerprint,
                    "locale": "en-US",
                    "metadata": {
                        "marketConsentValue": False,
                        "verificationId": self.vid,
                        "refererUrl": f"https://services.sheerid.com/verify/{PROGRAM_ID}/?verificationId={self.vid}",
                        "flags": '{"collect-info-step-email-first":"default","doc-upload-considerations":"default","doc-upload-may24":"default","doc-upload-redesign-use-legacy-message-keys":false,"docUpload-assertion-checklist":"default","font-size":"default","include-cvec-field-france-student":"not-labeled-optional"}',
                        "submissionOptIn": "By submitting the personal information above, I acknowledge that my personal information is being collected under the privacy policy of the business from which I am seeking a discount",
                    },
                }

                data, status = self._request(
                    "POST",
                    f"/verification/{self.vid}/step/collectStudentPersonalInfo",
                    body,
                )

                if status != 200:
                    stats.record(self.org["name"], False)
                    print(f"     ❗ Submit failed: HTTP {status}")
                    print(f"     ❗ Response body: {data}")
                    return {
                        "success": False,
                        "error": f"Submit failed: {status} - {data}",
                    }

                if data.get("currentStep") == "error":
                    error_ids = data.get("errorIds", [])
                    # Check for fraud rejection
                    if "fraudRulesReject" in str(error_ids):
                        if HAS_ANTI_DETECT:
                            handle_fraud_rejection(
                                retry_count=0,
                                error_payload=data,
                                message=f"University: {self.org['name']}",
                            )
                    stats.record(self.org["name"], False)
                    return {
                        "success": False,
                        "error": f"Error: {error_ids}",
                        "is_fraud_reject": "fraudRulesReject" in str(error_ids),
                    }

                print(f"     📍 Current step: {data.get('currentStep')}")
                current_step = data.get("currentStep", "")
            elif current_step in ["docUpload", "sso"]:
                print("   ▶ Step 2/3: Skipping (already past info submission)...")
            else:
                print(
                    f"   ▶ Step 2/3: Unknown step '{current_step}', attempting to continue..."
                )

            # Step 3: Skip SSO if needed (PastKing logic)
            if current_step in ["sso", "collectStudentPersonalInfo"]:
                print("   ▶ Step 3/4: Skipping SSO...")
                self._request("DELETE", f"/verification/{self.vid}/step/sso")

            # Step 4: Upload document
            print("   ▶ Step 4/5: Uploading document...")
            upload_body = {
                "files": [
                    {
                        "fileName": filename,
                        "mimeType": "image/png",
                        "fileSize": len(doc),
                    }
                ]
            }
            data, status = self._request(
                "POST", f"/verification/{self.vid}/step/docUpload", upload_body
            )

            if not data.get("documents"):
                stats.record(self.org["name"], False)
                return {"success": False, "error": "No upload URL"}

            upload_url = data["documents"][0].get("uploadUrl")
            if not self._upload_s3(upload_url, doc):
                stats.record(self.org["name"], False)
                return {"success": False, "error": "Upload failed"}

            print("     ✅ Document uploaded!")

            # Step 5: Complete document upload (PastKing logic)
            print("   ▶ Step 5/5: Completing upload...")
            data, status = self._request(
                "POST", f"/verification/{self.vid}/step/completeDocUpload"
            )
            final_step = data.get("currentStep", "unknown")
            print(f"     📍 Final step: {final_step}")

            if final_step == "success":
                stats.record(self.org["name"], True)
                return {
                    "success": True,
                    "message": "Verified instantly! No review needed.",
                    "student": f"{first} {last}",
                    "email": email,
                    "school": self.org["name"],
                    "redirectUrl": data.get("redirectUrl"),
                }
            elif final_step == "pending":
                return {
                    "success": False,
                    "pending": True,
                    "message": "Document submitted for review. Wait 24-48h for result.",
                    "student": f"{first} {last}",
                    "email": email,
                    "school": self.org["name"],
                }
            elif final_step in ["rejected", "error"]:
                stats.record(self.org["name"], False)
                error_ids = data.get("errorIds", [])
                return {
                    "success": False,
                    "error": f"Rejected: {error_ids}"
                    if error_ids
                    else "Document rejected",
                }
            else:
                return {
                    "success": False,
                    "pending": True,
                    "message": f"Unknown status: {final_step}. Check manually.",
                    "student": f"{first} {last}",
                    "email": email,
                    "school": self.org["name"],
                }

        except Exception as e:
            if self.org:
                stats.record(self.org["name"], False)
            return {"success": False, "error": str(e)}


# ============ MAIN ============
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Google One (Gemini) Student Verification Tool"
    )
    parser.add_argument("url", nargs="?", help="Verification URL")
    parser.add_argument(
        "--proxy", help="Proxy server (host:port or http://user:pass@host:port)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force run even with warnings"
    )
    parser.add_argument(
        "--school", help="Manually specify school name (partial match)"
    )
    args = parser.parse_args()

    print()
    print("╔" + "═" * 56 + "╗")
    print("║" + " 🤖 Google One (Gemini) Verification Tool".center(56) + "║")
    print("║" + " SheerID Student Discount".center(56) + "║")
    print("╚" + "═" * 56 + "╝")
    print()

    # ⚠️ US-ONLY WARNING
    print("   " + "⚠" * 20)
    print("   ⚠️  IMPORTANT WARNING (Jan 2026):")
    print("   ⚠️  Gemini student verification is now US-ONLY!")
    print("   ⚠️  ")
    print("   ⚠️  Requirements for success:")
    print("   ⚠️  1. US residential proxy (datacenter IPs blocked)")
    print("   ⚠️  2. curl_cffi installed (pip install curl_cffi)")
    print("   ⚠️  3. US university selection")
    print("   ⚠️  ")
    print("   ⚠️  Non-US users: Consider using perplexity-verify-tool")
    print("   ⚠️  or spotify-verify-tool instead.")
    print("   " + "⚠" * 20)
    print()

    if not args.force:
        confirm = input("   Continue anyway? (y/N): ").strip().lower()
        if confirm != "y":
            print("\n   Aborted. Use --force to skip this warning.")
            return

    # Get URL
    if args.url:
        url = args.url
    else:
        url = input("\n   Enter verification URL: ").strip()

    if not url or "sheerid.com" not in url:
        print("\n   ❌ Invalid URL. Must contain sheerid.com")
        return

    # Show proxy info
    if args.proxy:
        print(f"   🔒 Using proxy: {args.proxy}")
    else:
        print("   ⚠️  No proxy specified! Using direct connection.")
        print("   ⚠️  This may result in verification failure.")

    print("\n   ⏳ Processing...")

    verifier = GeminiVerifier(url, proxy=args.proxy)

    # Check link first
    check = verifier.check_link()
    if not check.get("valid"):
        print(f"\n   ❌ Link Error: {check.get('error')}")
        return

    result = verifier.verify(manual_school=args.school)

    print()
    print("─" * 58)
    if result.get("success"):
        print("   🎉 VERIFIED INSTANTLY!")
        print(f"   👤 {result.get('student')}")
        print(f"   📧 {result.get('email')}")
        print(f"   🏫 {result.get('school')}")
        print()
        print("   ✅ No review needed - verified via authoritative database!")
    elif result.get("pending"):
        print("   ⏳ SUBMITTED FOR REVIEW")
        print(f"   👤 {result.get('student')}")
        print(f"   📧 {result.get('email')}")
        print(f"   🏫 {result.get('school')}")
        print()
        print("   ⚠️  Document uploaded, waiting for review (24-48h)")
        print("   ⚠️  This is NOT a guaranteed success!")
    else:
        print(f"   ❌ FAILED: {result.get('error')}")
    print("─" * 58)

    stats.print_stats()


if __name__ == "__main__":
    main()
