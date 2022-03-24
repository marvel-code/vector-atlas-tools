# -*- coding: utf-8 -*-
"""
    sys.argv[1] - path to font file.
"""
import json
from ttfquery import describe
import ttfquery.glyph as glyph
import ttfquery.glyphquery as glyphquery
import sys
import os
from PIL import Image

# Parses all glyphs in font if true, else parses glyphs from CUSTOM_PARSING_GLYPHS
ALL_GLYPHS = False
# If ALL_GLYPHS is False, fetch glyphs from CUSTOM_PARSING_GLYPHS
CUSTOM_PARSING_GLYPHS = u' `1234567890-=~!@#$%^&*()_+qwertyuiop[]QWERTYUIOP{}|asdfghjkl;\'ASDFGHJKL:"zxcvbnm,./ZXCVBNM<>?№ёЁйцукенгшщзхъ\\ЙЦУКЕНГШЩЗХЪфывапролджэФЫВАПРОЛДЖЭячсмитьбюЯЧСМИТЬБЮ'
#CUSTOM_PARSING_GLYPHS = u'е'
DIST_DIR = "dist"

print("Glyphs: " + (CUSTOM_PARSING_GLYPHS if not ALL_GLYPHS else 'all'))

def normalizeFPoint(fpoint, size):
    return ((float(fpoint[0][0]) / size[0], float(fpoint[0][1]) / size[1]), fpoint[1])

flags = filter(lambda x: x[0] == '-', sys.argv[1:])
font_path = sys.argv[1]
font = describe.openFont(font_path)
charHeight = glyphquery.charHeight(font)
glyphNameMap = font['cmap'].getcmap(*describe.guessEncoding(font)).cmap # char -> glyphName
charMap = dict([(value, key) for key, value in glyphNameMap.items()]) # glyphName -> char
glyph_names = font.getGlyphNames() \
    if ALL_GLYPHS else [glyphquery.glyphName(font, gn) for gn in CUSTOM_PARSING_GLYPHS]

glyphCoords = {}
glyphInfos = {}
stat = {
    'maxPointsCount': (0, None),
}
for glyph_name in glyph_names:
    g = glyph.Glyph(glyph_name)
    contours = g.calculateContours(font)
    charWidth = glyphquery.width(font, glyph_name)
    if charWidth == 0 or glyph_name not in charMap:
        continue
    char = unichr(charMap[glyph_name])
    charSize = (charWidth, charHeight)

    # uncomporessed_contours
    uncompressed_contours = []
    for contour in contours:
        points = []
        last_fpoint = contour[-1]
        for i, fpoint in enumerate(contour):
            if (last_fpoint[1] == fpoint[1] and fpoint[1] == 0):
                x0 = float(last_fpoint[0][0] + fpoint[0][0]) / 2
                y0 = float(last_fpoint[0][1] + fpoint[0][1]) / 2
                fpoint_ = ((x0, y0), 1)
                points.append(normalizeFPoint(fpoint_, charSize))
            if (last_fpoint[1] == fpoint[1] and fpoint[1] == 1):
                fpoint_ = (fpoint[0], 0)
                points.append(normalizeFPoint(fpoint_, charSize))
            points.append(normalizeFPoint(fpoint, charSize))
            last_fpoint = fpoint
        uncompressed_contours.append(points)

    glyphInfos[char] = {
        'gridSize': None, # todo
        'contours': uncompressed_contours,
    }
    glyphCoords[char] = [0, 0] # todo

    points_count = sum(map(lambda x: sum(map(lambda y: len(y), x)), uncompressed_contours))
    if stat['maxPointsCount'][0] < points_count:
        stat['maxPointsCount'] = (points_count, char)

print
print(stat)
print

if not os.path.exists(DIST_DIR):
    os.makedirs(DIST_DIR)

with open('{}/glyphCoords.json'.format(DIST_DIR), 'w') as f:
    json.dump(glyphCoords, f)

with open('{}/glyphInfos.json'.format(DIST_DIR), 'w') as f:
    json.dump(glyphInfos, f)

with open("{}/atlas.bmp".format(DIST_DIR), 'w') as f:
    img = Image.new('RGBA', (255, 255), (255, 0, 0, 255))
    pixels = img.load()
    for i in range(img.size[0]):
        for j in range(img.size[1]):
            pixels[i,j] = (i, j, 100) # Set the colour accordingly
    if '--show' in flags:
        img.show()
