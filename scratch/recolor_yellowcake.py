import os
from PIL import Image

def recolor_image():
    input_path = r"C:\Users\masan\.gemini\antigravity\brain\c255250c-f7cb-4c05-acd4-95d3e5e056cf\mining_newsletter_logo_white_gravel_u3o8_1780640298448.png"
    output_path = r"C:\Users\masan\.gemini\antigravity\brain\c255250c-f7cb-4c05-acd4-95d3e5e056cf\mining_newsletter_logo_gravel_perfect_processed.png"
    
    if not os.path.exists(input_path):
        print(f"Input file not found: {input_path}")
        return
        
    img = Image.open(input_path).convert("RGBA")
    pixels = img.load()
    width, height = img.size
    
    recolored_count = 0
    
    # Restrict to top 70% of the image to ensure the gold 'mayAi' text at the bottom is completely untouched
    text_threshold_y = int(height * 0.7)
    
    for y in range(text_threshold_y):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            
            # Target yellow: high red, high green, low blue
            if r > 120 and g > 110 and b < 130 and r > b * 1.5 and g > b * 1.3:
                # Replace with dark green-black (calcined U3O8 / black oxide)
                # Keep some of the original brightness variation of the crystal facet
                brightness = (r + g + b) / 3.0
                factor = brightness / 255.0  # value between 0.0 and 1.0
                
                # Base dark green-black color
                new_r = int(10 + factor * 20)
                new_g = int(14 + factor * 25)
                new_b = int(10 + factor * 20)
                
                pixels[x, y] = (new_r, new_g, new_b, a)
                recolored_count += 1
                
    img.save(output_path)
    print(f"Successfully processed image. Recolored {recolored_count} yellow pixels (excluding bottom text region). Saved to {output_path}")

if __name__ == "__main__":
    recolor_image()
