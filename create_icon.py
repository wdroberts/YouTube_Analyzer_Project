"""
Create custom icon for YouTube Analyzer
Generates a simple but professional-looking icon
"""
try:
    from PIL import Image, ImageDraw, ImageFont
    import os
    
    # Create 256x256 icon (Windows standard)
    size = 256
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background circle (gradient effect with red/pink for YouTube theme)
    for i in range(100, 0, -1):
        alpha = int(255 * (i / 100))
        color = (255, 50, 50, alpha)  # Red/YouTube color
        radius = int(size * 0.45 * (i / 100))
        center = size // 2
        draw.ellipse(
            [center - radius, center - radius, center + radius, center + radius],
            fill=color
        )
    
    # Play button triangle (white)
    center = size // 2
    triangle_size = size // 3
    points = [
        (center - triangle_size//3, center - triangle_size//2),
        (center - triangle_size//3, center + triangle_size//2),
        (center + triangle_size//2, center)
    ]
    draw.polygon(points, fill=(255, 255, 255, 255))
    
    # Add small chart/analytics icon in corner
    chart_size = size // 4
    chart_x = size - chart_size - 20
    chart_y = size - chart_size - 20
    
    # Mini bar chart
    bar_width = chart_size // 5
    for i, height in enumerate([0.4, 0.7, 0.5, 0.9, 0.6]):
        x = chart_x + i * bar_width
        bar_height = int(chart_size * height)
        y = chart_y + chart_size - bar_height
        draw.rectangle(
            [x, y, x + bar_width - 2, chart_y + chart_size],
            fill=(100, 200, 255, 255)
        )
    
    # Save as ICO (multiple sizes for Windows)
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    icon_images = [img.resize(s, Image.Resampling.LANCZOS) for s in icon_sizes]
    
    img.save('icon.ico', format='ICO', sizes=icon_sizes)
    print("[OK] Icon created successfully: icon.ico")
    print(f"   Sizes: {', '.join(f'{s[0]}x{s[1]}' for s in icon_sizes)}")
    
except ImportError:
    print("[WARNING] Pillow not installed. Installing...")
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    print("[OK] Pillow installed. Run this script again to create the icon.")
except Exception as e:
    print(f"[ERROR] Error creating icon: {e}")
    print("\nYou can:")
    print("1. Use a custom icon from: https://icon-icons.com/")
    print("2. Or continue with default Python icon")

