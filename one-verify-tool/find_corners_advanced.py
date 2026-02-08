from PIL import Image
import numpy as np

def find_card():
    # Open the template
    img = Image.open("hand_template.png").convert("L")
    data = np.array(img)
    
    # 1. Threshold to find the brightest part (the white card)
    # The card is usually very white (240-255)
    binary = (data > 235).astype(np.uint8) * 255
    
    # 2. To avoid noise from the background (like the window), 
    # we'll look for the largest contiguous white area.
    from scipy.ndimage import label
    labeled_array, num_features = label(binary)
    
    if num_features == 0:
        print("No white found")
        return
        
    # Find the largest component
    feature_sizes = np.bincount(labeled_array.ravel())
    # Ignore background (0)
    feature_sizes[0] = 0
    largest_feature = feature_sizes.argmax()
    
    # Create mask of just the card
    card_mask = (labeled_array == largest_feature)
    coords = np.argwhere(card_mask)
    
    # Coordinates are (y, x)
    y_min, x_min = coords.min(axis=0)
    y_max, x_max = coords.max(axis=0)
    
    # Find the 4 corners of this specific mask
    pts = coords[:, ::-1] # (x, y)
    
    tl = pts[np.argmin(pts[:,0] + pts[:,1])]
    br = pts[np.argmax(pts[:,0] + pts[:,1])]
    tr = pts[np.argmax(pts[:,0] - pts[:,1])]
    bl = pts[np.argmin(pts[:,0] - pts[:,1])]
    
    print(f"AUTO_COORDS: TL={tuple(tl)}, TR={tuple(tr)}, BR={tuple(br)}, BL={tuple(bl)}")

if __name__ == "__main__":
    try:
        find_card()
    except Exception as e:
        print(f"Error: {e}")
