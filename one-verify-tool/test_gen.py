from main import generate_transcript, generate_student_id
from pathlib import Path

def test_generation():
    print("🎨 Generating test documents...")
    
    # 测试数据
    first, last = "Paul", "Torres"
    school = "University of California, Los Angeles (UCLA)"
    dob = "2002-09-11"
    
    # 1. 生成成绩单
    print("📄 Generating Transcript...")
    transcript_data = generate_transcript(first, last, school, dob)
    Path("test_transcript.png").write_bytes(transcript_data)
    print("✅ Saved as test_transcript.png")
    
    # 2. 生成学生卡
    print("🪪 Generating Student ID...")
    id_card_data = generate_student_id(first, last, school)
    Path("test_id_card.png").write_bytes(id_card_data)
    print("✅ Saved as test_id_card.png")
    
    print("\n🚀 Done! Please check the .png files in your directory.")

if __name__ == "__main__":
    test_generation()
