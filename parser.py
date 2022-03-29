# -*- coding: utf-8 -*-
"""
    sys.argv[1] - path to font file.
"""
import math
from genericpath import exists
import json
from math import ceil
from ttfquery import describe
import ttfquery.glyph as glyph
import ttfquery.glyphquery as glyphquery
import sys
import os
from PIL import Image

ON_CURVE = 1
OFF_CURVE = 0
# Parses all glyphs in font if true, else parses glyphs from CUSTOM_PARSING_GLYPHS
ALL_GLYPHS = False
# If ALL_GLYPHS is False, fetch glyphs from CUSTOM_PARSING_GLYPHS
CUSTOM_PARSING_GLYPHS = u' `1234567890-=~!@#$%^&*()_+qwertyuiop[]QWERTYUIOP{}|asdfghjkl;\'ASDFGHJKL:"zxcvbnm,./ZXCVBNM<>?№ёЁйцукенгшщзхъ\\ЙЦУКЕНГШЩЗХЪфывапролджэФЫВАПРОЛДЖЭячсмитьбюЯЧСМИТЬБЮ'
#CUSTOM_PARSING_GLYPHS = u'е'
DIST_DIR = "dist"

print("Glyphs: " + (CUSTOM_PARSING_GLYPHS if not ALL_GLYPHS else 'all'))

def isclose(a, b, rel_tol=1e-09, abs_tol=0.0):
    '''
    Python 2 implementation of Python 3.5 math.isclose()
    https://hg.python.org/cpython/file/tip/Modules/mathmodule.c#l1993
    '''
    # sanity check on the inputs
    if rel_tol < 0 or abs_tol < 0:
        raise ValueError("tolerances must be non-negative")

    # short circuit exact equality -- needed to catch two infinities of
    # the same sign. And perhaps speeds things up a bit sometimes.
    if a == b:
        return True

    # This catches the case of two infinities of opposite sign, or
    # one infinity and one finite number. Two infinities of opposite
    # sign would otherwise have an infinite relative tolerance.
    # Two infinities of the same sign are caught by the equality check
    # above.
    if math.isinf(a) or math.isinf(b):
        return False

    # now do the regular computation
    # this is essentially the "weak" test from the Boost library
    diff = math.fabs(b - a)
    result = (((diff <= math.fabs(rel_tol * b)) or
               (diff <= math.fabs(rel_tol * a))) or
              (diff <= abs_tol))
    return result

def normalizeFPoint(fpoint, size):
    return ((float(fpoint[0][0]) / size[0], float(fpoint[0][1]) / size[1]), fpoint[1])

def pointInside(point, rectangle):
    """
    @param rectangle (x0,y0,x1,y1) x0,y0 left-bottom. x1,y1 right-top.
    """
    return point[0] >= rectangle[0] and point[0] <= rectangle[2] and \
        point[1] >= rectangle[1] and point[1] <= rectangle[3]
    
def bezierCrossComponent(bezier, componentIndex, componentValue):
    """
    component is x or y.
    componentIndex == 0 is x.
    componentIndex == 1 is y.
    @return boolean
    """
    c0 = bezier[0][componentIndex]
    c1 = bezier[1][componentIndex]
    c2 = bezier[2][componentIndex]
    if isclose(c0, 2*c1 + c2):
        # Linear
        if isclose(2*c1, c0):
            return False
        return True
    D = (c1 - c0) ** 2 - (c0 - 2*c1 + c2) * (c0 - componentValue)
    return D >= 0

def bezierInsideCell(bezier, cellRectangle):
    return pointInside(bezier[0], cellRectangle) or pointInside(bezier[2], cellRectangle)\
        or bezierCrossComponent(bezier, 0, cellRectangle[0]) or bezierCrossComponent(bezier, 0, cellRectangle[2])\
        or bezierCrossComponent(bezier, 1, cellRectangle[1]) or bezierCrossComponent(bezier, 1, cellRectangle[3])
    
    

def makeGrid(beziers):
    """
    @return number[][];
    """
    grid = None
    for gridSize in range(2, 100):
        grid = []
        skip = False
        for i in range(gridSize):
            row = []
            for j in range(gridSize):
                cellRectangle = (1. / gridSize * i, 1. / gridSize * j, 1. / gridSize * (i + 1), 1. / gridSize * (j + 1))
                cell = []
                for bi, b in enumerate(beziers):
                    if bezierInsideCell(b, cellRectangle):
                        cell.append(bi)
                row.append(cell)
            if filter(lambda x: len(x) > 4, row):
                skip = True
                break
            grid.append(row)
        if not skip:
            break
    return grid
    

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
    'maxGridSize': (0, None),
}
for glyph_name in glyph_names:
    g = glyph.Glyph(glyph_name)
    contours = g.calculateContours(font)
    charWidth = glyphquery.width(font, glyph_name)
    if charWidth == 0 or glyph_name not in charMap:
        continue
    char = unichr(charMap[glyph_name])
    print(char)
    charSize = (charWidth, charHeight)

    # Beziers
    beziers = []
    for contour in contours:
        # Contour points
        points = []
        last_fpoint = contour[-1]
        for i, fpoint in enumerate(contour):
            if (last_fpoint[1] == fpoint[1] and fpoint[1] == OFF_CURVE):
                x0 = float(last_fpoint[0][0] + fpoint[0][0]) / 2
                y0 = float(last_fpoint[0][1] + fpoint[0][1]) / 2
                fpoint_ = ((x0, y0), ON_CURVE)
                points.append(normalizeFPoint(fpoint_, charSize))
            if i > 0 and (last_fpoint[1] == fpoint[1] and fpoint[1] == ON_CURVE):
                fpoint_ = (fpoint[0], OFF_CURVE)
                points.append(normalizeFPoint(fpoint_, charSize))
            points.append(normalizeFPoint(fpoint, charSize))
            last_fpoint = fpoint
        # Contour beziers
        for i in range(int((len(points) + 2) / 3)):
            bezier = []
            for j in range(3):
                bezier.append(points[2 * i + j][0])
            beziers.append(bezier)
    # Grid
    grid = makeGrid(beziers)

    glyphInfos[char] = {
        'grid': grid,
        'beziers': beziers,
        'size': charSize,
    }
    glyphCoords[char] = [0, 0] # todo

    points_count = sum(map(lambda x: sum(map(lambda y: len(y), x)), beziers))
    if stat['maxPointsCount'][0] < points_count:
        stat['maxPointsCount'] = (points_count, char)
    if stat['maxGridSize'][0] < len(grid):
        stat['maxGridSize'] = (len(grid), char)
    

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
