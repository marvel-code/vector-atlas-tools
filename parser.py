# -*- coding: utf-8 -*-
"""
    sys.argv[1] - path to font file.
"""
from itertools import count
from ttfquery import describe
import ttfquery.glyph as glyph
from ttfquery.glyphquery import glyphName
import sys

# Parses all glyphs in font if true, else parses glyphs from CUSTOM_PARSING_GLYPHS
ALL_GLYPHS = False
# If ALL_GLYPHS is False, fetch glyphs from CUSTOM_PARSING_GLYPHS
CUSTOM_PARSING_GLYPHS = u')'

flags = filter(lambda x: x[0] == '-', sys.argv[1:])
font_path = sys.argv[1]
font = describe.openFont(font_path)
glyph_names = font.getGlyphNames() \
    if ALL_GLYPHS else [glyphName(font, gn) for gn in CUSTOM_PARSING_GLYPHS]

glyphs_beziers = {}
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
    glyphs_beziers[glyph_name] = uncompressed_contours

print(glyphs_beziers)
    

