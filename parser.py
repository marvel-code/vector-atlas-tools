# -*- coding: utf-8 -*-
"""
    sys.argv[1] - path to font file.
"""
import json
from ttfquery import describe
import ttfquery.glyph as glyph
import ttfquery.glyphquery as glyphquery
import sys
from PIL import Image

# Parses all glyphs in font if true, else parses glyphs from CUSTOM_PARSING_GLYPHS
ALL_GLYPHS = True
# If ALL_GLYPHS is False, fetch glyphs from CUSTOM_PARSING_GLYPHS
CUSTOM_PARSING_GLYPHS = u'='

flags = filter(lambda x: x[0] == '-', sys.argv[1:])
font_path = sys.argv[1]
font = describe.openFont(font_path)
glyph_names = font.getGlyphNames() \
    if ALL_GLYPHS else [glyphquery.glyphName(font, gn) for gn in CUSTOM_PARSING_GLYPHS]

glyph_infos = {}
max_points_count = 0
for glyph_name in glyph_names:
    if not ALL_GLYPHS:
        print(glyph_name)
    g = glyph.Glyph(glyph_name)
    contours = g.calculateContours(font)
    uncompressed_contours = []
    for contour in contours:
        points = []
        last_fpoint = contour[-1]
        for i, fpoint in enumerate(contour):
            if (last_fpoint[1] == fpoint[1] and fpoint[1] == 0):
                x0 = (last_fpoint[0][0] + fpoint[0][0]) / 2
                y0 = (last_fpoint[0][1] + fpoint[0][1]) / 2
                points.append(([x0, y0], 1))
            points.append(fpoint)
            last_fpoint = fpoint
        uncompressed_contours.append(points)
    glyph_infos[glyph_name] = {
        'contours': uncompressed_contours,
        'width': glyphquery.width(font, glyph_name),
    }
    points_count = sum(map(lambda x: sum(map(lambda y: len(y), x)), uncompressed_contours))
    max_points_count = max(max_points_count, points_count)

print('height', glyphquery.charHeight(font))
#print(glyph_infos)
print(max_points_count)
print(len(glyph_infos))

with open('atlas.bmp', 'w') as f:
    img = Image.new('RGBA', (255, 255), (255, 0, 0, 0))
    pixels = img.load()
    for i in range(img.size[0]):    # For every pixel:
        for j in range(img.size[1]):
            pixels[i,j] = (i, j, 100) # Set the colour accordingly
    if '--show' in flags:
        img.show()
