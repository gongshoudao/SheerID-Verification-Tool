from PIL import Image
import numpy as np

def find_corners():
    img = Image.open("hand_template.png").convert("L")
    arr = np.array(img)
    
    # Threshold to find white card
    mask = arr > 240
    
    # Remove border noise
    mask[:20, :] = False
    mask[-20:, :] = False
    mask[:, :20] = False
    mask[:, -20:] = False
    
    coords = np.argwhere(mask)
    if coords.size == 0:
        print("No white found")
        return
        
    # Points are (y, x), convert to (x, y)
    pts = coords[:, ::-1]
    
    # Find 4 corners by maximizing/minimizing projections
    # This works well for a rotated rectangle
    tl = pts[np.argmin(pts[:,0] + pts[:,1])]
    br = pts[np.argmax(pts[:,0] + pts[:,1])]
    tr = pts[np.argmax(pts[:,0] - pts[:,1])]
    bl = pts[np.argmin(pts[:,0] - pts[:,1])]
    
    print(f"RES: {tuple(tl)}, {tuple(tr)}, {tuple(br)}, {tuple(bl)}")

if __name__ == "__main__":
    find_corners()
