from PIL import Image, ImageDraw, ImageFont
import os

# Create a directory for the images
output_dir = "../data/images"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Image settings
image_size = (500, 500)  # Width, height
background_color = (255, 255, 255)  # White background
font_color = (0, 0, 0)  # Black text

# Path to macOS system font 'Helvetica'
font_path = "/System/Library/Fonts/Helvetica.ttc"  # macOS default system font

# Function to find the maximum font size that fits within the image
def get_max_font_size(draw, text, image_size, max_font_size=400, font_path=None):
    font_size = 10
    font = None

    while font_size <= max_font_size:
        try:
            font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
            text_width, text_height = draw.textsize(text, font=font)
            if text_width > image_size[0] * 0.9 or text_height > image_size[1] * 0.9:
                break
            font_size += 1
        except OSError:
            print("Font resource not found. Using default font.")
            font = ImageFont.load_default()
            break

    return font

for i in range(1, 11):
    # Create a blank image with white background
    img = Image.new('RGB', image_size, background_color)
    draw = ImageDraw.Draw(img)

    # Get maximum font size that fits the image
    text = str(i)
    font = get_max_font_size(draw, text, image_size, max_font_size=400, font_path=font_path)

    # Calculate text size and position for center alignment
    text_width, text_height = draw.textsize(text, font=font)
    position = ((image_size[0] - text_width) // 2, (image_size[1] - text_height) // 2)

    # Add text to the image
    draw.text(position, text, font=font, fill=font_color)

    # Save the image
    img.save(os.path.join(output_dir, f'number_{i}.png'))

print(f"10 images generated in the '{output_dir}' folder.")
