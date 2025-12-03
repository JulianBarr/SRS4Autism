import matplotlib.pyplot as plt
import matplotlib.image as mpimg

# Load the image
img = mpimg.imread('frontend/public/marios-world-map.png')
fig, ax = plt.subplots(figsize=(12, 7))
ax.imshow(img)

print("Click on the CENTER of each island to get coordinates...")

def on_click(event):
    if event.xdata is not None and event.ydata is not None:
        # Get pixel coordinates
        x, y = int(event.xdata), int(event.ydata)
        
        # Calculate percentage for responsive CSS (assuming 1920x1080)
        img_height, img_width = img.shape[:2]
        x_pct = round((x / img_width) * 100, 1)
        y_pct = round((y / img_height) * 100, 1)

        print(f"📍 Clicked at: Pixel({x}, {y}) | CSS({x_pct}%, {y_pct}%)")

# Connect the click event
cid = fig.canvas.mpl_connect('button_press_event', on_click)

plt.title("Click center of islands to get coordinates")
plt.show()
