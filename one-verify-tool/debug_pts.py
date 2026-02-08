from PIL import Image, ImageDraw

def check_pts():
    try:
        img = Image.open("hand_template.png").convert("RGB")
    except:
        print("Template not found")
        return
    draw = ImageDraw.Draw(img)
    
    # Points from the 'worse' version
    pts = [(172, 238), (464, 144), (526, 342), (235, 467)]
    
    colors = [(255,0,0), (0,255,0), (0,0,255), (255,255,0)] # R=TL, G=TR, B=BR, Y=BL
    for p, c in zip(pts, colors):
        draw.ellipse([p[0]-8, p[1]-8, p[0]+8, p[1]+8], fill=c, outline=(255,255,255))
        
    img.save("debug_alignment.png")
    print("Saved debug_alignment.png. Check locations of Red(TL), Green(TR), Blue(BR), Yellow(BL)")

if __name__ == "__main__":
    check_pts()
