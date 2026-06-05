import os
from PIL import Image

def rgb_to_hsv(r, g, b):
    r_n = r / 255.0
    g_n = g / 255.0
    b_n = b / 255.0
    
    mx = max(r_n, g_n, b_n)
    mn = min(r_n, g_n, b_n)
    df = mx - mn
    
    if mx == mn:
        h = 0
    elif mx == r_n:
        h = (60 * ((g_n - b_n) / df) + 360) % 360
    elif mx == g_n:
        h = (60 * ((b_n - r_n) / df) + 120) % 360
    elif mx == b_n:
        h = (60 * ((r_n - g_n) / df) + 240) % 360
        
    if mx == 0:
        s = 0
    else:
        s = (df / mx) * 255.0
        
    v = mx * 255.0
    return h, s, v

def hsv_to_rgb(h, s, v):
    h = h / 360.0
    s = s / 255.0
    v = v / 255.0
    
    if s == 0.0:
        r = g = b = v
    else:
        h_i = int(h * 6)
        f = (h * 6) - h_i
        p = v * (1.0 - s)
        q = v * (1.0 - s * f)
        t = v * (1.0 - s * (1.0 - f))
        
        if h_i == 0:
            r, g, b = v, t, p
        elif h_i == 1:
            r, g, b = q, v, p
        elif h_i == 2:
            r, g, b = p, v, t
        elif h_i == 3:
            r, g, b = p, q, v
        elif h_i == 4:
            r, g, b = t, p, v
        elif h_i == 5:
            r, g, b = v, p, q
            
    return int(r * 255), int(g * 255), int(b * 255)

def recolor_image_hsv():
    input_path = r"C:\Users\masan\.gemini\antigravity\brain\c255250c-f7cb-4c05-acd4-95d3e5e056cf\mining_newsletter_logo_white_gravel_u3o8_1780640298448.png"
    output_path = r"C:\Users\masan\.gemini\antigravity\brain\c255250c-f7cb-4c05-acd4-95d3e5e056cf\mining_newsletter_logo_gravel_perfect_processed.png"
    
    if not os.path.exists(input_path):
        print(f"Input file not found: {input_path}")
        return
        
    img = Image.open(input_path).convert("RGBA")
    pixels = img.load()
    width, height = img.size
    
    recolored_count = 0
    text_threshold_y = int(height * 0.7)
    
    for y in range(text_threshold_y):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            
            # Convert to HSV
            h, s, v = rgb_to_hsv(r, g, b)
            
            # Target yellow shades of the U3O8 crystals:
            # Yellow is typically between 35 and 65 degrees Hue, S > 60, V > 50
            if 35 <= h <= 65 and s > 60 and v > 50:
                # Scale down Saturation and Value to make it look like a realistic dark/black crystal
                # Scaling retains all the original highlights and shading details!
                new_s = s * 0.15  # Desaturate heavily
                new_v = v * 0.25  # Darken but preserve shading/luminance gradient
                new_h = h         # Keep the hue (with low saturation it acts as a subtle dark tone)
                
                new_r, new_g, new_b = hsv_to_rgb(new_h, new_s, new_v)
                pixels[x, y] = (new_r, new_g, new_b, a)
                recolored_count += 1
                
    img.save(output_path)
    print(f"Successfully processed image using HSV scaling. Recolored {recolored_count} yellow pixels. Saved to {output_path}")

if __name__ == "__main__":
    recolor_image_hsv()
