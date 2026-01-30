
from PIL import Image, ImageDraw

def create_ai_icon():
    # Create a 256x256 transparent image
    size = (256, 256)
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw a "Brain" / Chip background circle (Dark Blue)
    draw.ellipse((20, 20, 236, 236), fill=(10, 25, 50), outline=(0, 255, 255), width=8)
    
    # Draw "Circuit" lines inside
    # Center circle
    draw.ellipse((80, 80, 176, 176), fill=(0, 100, 200), outline=(0, 255, 255), width=4)
    
    # Nodes
    nodes = [(128, 40), (210, 128), (128, 216), (46, 128), (80, 80), (176, 80), (176, 176), (80, 176)]
    for node in nodes:
        draw.ellipse((node[0]-10, node[1]-10, node[0]+10, node[1]+10), fill=(0, 255, 255))
        # Draw line to center
        draw.line((node[0], node[1], 128, 128), fill=(0, 200, 255), width=3)
        
    # Draw Center Core (White glowing)
    draw.ellipse((110, 110, 146, 146), fill=(255, 255, 255))
    
    # Save as ICO
    icon_path = r"c:\Users\USER\Desktop\AI_Bot_Icon.ico"
    # Also save in folder to be safe
    icon_backup = r"c:\Users\USER\.gemini\antigravity\scratch\whatsapp_server\ai_icon.ico"
    
    img.save(icon_path, format='ICO', sizes=[(256, 256)])
    img.save(icon_backup, format='ICO', sizes=[(256, 256)])
    print(f"Icon created at {icon_path}")

if __name__ == "__main__":
    create_ai_icon()
