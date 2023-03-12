import json

from PIL import Image, ImageDraw

# Define image size and colors
IMAGE_SIZE = (500, 500)
COLORS2 = [(0, 255, 0), (0, 0, 255), ]

COLORS = [
  {"name": "Teal", "rgb": (0, 128, 128)},
  {"name": "Mustard", "rgb": (255, 219, 88)},
  {"name": "Dark Gray", "rgb": (64, 64, 64)},
  {"name": "Crimson", "rgb": (220, 20, 60)}
]


# Define the shapes to be generated
SHAPES = ['rectangle', 'square', 'circle']

# Generate images

datas = []

for shape in SHAPES:
    for i in range(len(COLORS)):
        for j in range(i, len(COLORS)):
            color_1, color_2 = COLORS[i], COLORS[j]
            color1 = color_1['rgb']
            color2 = color_2['rgb']

            color1_name = color_1['name']
            color2_name = color_2['name']

            # Create a new image
            img = Image.new('RGB', IMAGE_SIZE, (255, 255, 255))
            draw = ImageDraw.Draw(img)

            # Draw the shape with the chosen colors
            if shape == 'rectangle':
                x1, y1 = IMAGE_SIZE[0] // 4, IMAGE_SIZE[1] // 4
                width = IMAGE_SIZE[0] // 2
                height = IMAGE_SIZE[1] // 4
                x2, y2 = x1 + width, y1 + height
                draw.rectangle((x1, y1, x2, y2), fill=color1, outline=color2, width=10)
            elif shape == 'square':
                x, y = IMAGE_SIZE[0] // 4, IMAGE_SIZE[1] // 4
                size = IMAGE_SIZE[0] // 2
                draw.rectangle((x, y, x + size, y + size), fill=color1, outline=color2, width=10)
            elif shape == 'circle':
                x, y = IMAGE_SIZE[0] // 2, IMAGE_SIZE[1] // 2
                radius = IMAGE_SIZE[0] // 4
                draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color1, outline=color2, width=10)

            filename = f'{shape}-{color1_name}-{color2_name}.png'
            data = {
                "colors": [color1_name, color2_name],
                "shape": shape,
                "filename": filename
            }
            datas.append(data)
            # Save the image
            img.save(filename)

with open('image_tags.json', 'w') as f:
    json.dump(datas, f)

