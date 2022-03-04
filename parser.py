# -*- coding: utf-8 -*-
"""
    sys.argv[1] - path to font file.
"""
from ttfquery import describe
import ttfquery.glyph as glyph
from ttfquery.glyphquery import glyphName
import sys

# Parses all glyphs in font if true, else parses glyphs from CUSTOM_PARSING_GLYPHS
ALL_GLYPHS = False
# If ALL_GLYPHS is False, fetch glyphs from CUSTOM_PARSING_GLYPHS
CUSTOM_PARSING_GLYPHS = u'абвгдabcd12345!@#$%'

font_path = sys.argv[1]
font = describe.openFont(font_path)
glyph_names = font.getGlyphNames() \
    if ALL_GLYPHS else [glyphName(font, gn) for gn in CUSTOM_PARSING_GLYPHS]
for glyph_name in glyph_names:
    print(glyph_name)
    g = glyph.Glyph(glyph_name)
    contours = g.calculateContours(font)
    for contour in contours:
        for point, flag in contour:
            #print(point, flag)
            pass