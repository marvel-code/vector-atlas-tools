# -*- coding: utf-8 -*-
"""
    sys.argv[1] - path to font file.
"""
from cmath import sqrt
from copy import copy
import math
from genericpath import exists
import json
from math import ceil
from numpy import sort
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
#CUSTOM_PARSING_GLYPHS = u'еabc'
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

def insideSection(t, t1, t2):
    return t >= t1 and t <= t2
    
def fetchBezierCross(bezier, componentIndex, componentValue):
    """
    B(t) = (1-t)^2*p0 + 2(1-t)t*p1 + t^2*p2
    B(t) = (p0-2p1+p2)tt + 2(p1-p0)t + p0

    component is x or y.
    componentIndex == 0 is x.
    componentIndex == 1 is y.
    @return boolean
    """
    c0 = bezier[0][componentIndex]
    c1 = bezier[1][componentIndex]
    c2 = bezier[2][componentIndex]
    a = c0 - 2 * c1 + c2
    b = c1 - c0
    c = c0 - componentValue
    if isclose(a, 0):
        # Linear
        if isclose(b, 0):
            return []
        t = c / b / 2
        return [t] if insideSection(t, 0, 1) else []
    
    D = b ** 2 - a * c
    if D < 0:
        return []

    t1 = (-b - sqrt(D)) / a
    t2 = (-b + sqrt(D)) / a
    solution = []
    if insideSection(t1.real, 0, 1):
        solution.append(t1.real)
    if insideSection(t2.real, 0, 1):
        solution.append(t2.real)
    return solution

def calcBezier(bezier, t):
    def calcComponentBezier(c0, c1, c2, t):
        return (1-t)**2*c0 + 2*(1-t)*t*c1 + t**2*c2

    p0, p1, p2 = bezier
    return (
        calcComponentBezier(p0[0], p1[0], p2[0], t),
        calcComponentBezier(p0[1], p1[1], p2[1], t)
    )

def bezierInsideCell(bezier, cellRectangle):
    x1 = cellRectangle[0]
    y1 = cellRectangle[1]
    x2 = cellRectangle[2]
    y2 = cellRectangle[3]
    x1t = fetchBezierCross(bezier, 0, cellRectangle[0])
    y1t = fetchBezierCross(bezier, 1, cellRectangle[1])
    x2t = fetchBezierCross(bezier, 0, cellRectangle[2])
    y2t = fetchBezierCross(bezier, 1, cellRectangle[3])
    return pointInside(bezier[0], cellRectangle) or pointInside(bezier[2], cellRectangle)\
        or any(map(lambda t: insideSection(calcBezier(bezier, t)[1], y1, y2), x1t))\
        or any(map(lambda t: insideSection(calcBezier(bezier, t)[0], x1, x2), y1t))\
        or any(map(lambda t: insideSection(calcBezier(bezier, t)[1], y1, y2), x2t))\
        or any(map(lambda t: insideSection(calcBezier(bezier, t)[0], x1, x2), y2t))
    
def avrPoint(p1, p2):
    x0 = float(p1[0] + p2[0]) / 2
    y0 = float(p1[1] + p2[1]) / 2
    return (x0, y0)

def makeGrid(beziers):
    """
    @return number[][];
    """
    MAX_GRID_SIZE = 32
    MAX_CELL_BEZIERS = 4
    grid = None
    for gridSize in range(2, MAX_GRID_SIZE):
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
                if len(cell) > MAX_CELL_BEZIERS:
                    skip = True
                    break
            if skip:
                break
            grid.append(row)
        if not skip:
            break
        if gridSize == MAX_GRID_SIZE - 1:
            raise Exception("Max grid size enriched")
    return grid

def fetchBeziers(contours, charSize):
    beziers = []
    for contour in contours:
        # Contour points
        points = []
        last_fpoint = contour[-1]
        for i, fpoint in enumerate(contour):
            if (last_fpoint[1] == fpoint[1] and fpoint[1] == OFF_CURVE):
                fpoint_ = (avrPoint(fpoint[0], last_fpoint[0]), ON_CURVE)
                points.append(normalizeFPoint(fpoint_, charSize))
            if i > 0 and (last_fpoint[1] == fpoint[1] and fpoint[1] == ON_CURVE):
                fpoint_ = (avrPoint(fpoint[0], last_fpoint[0]), OFF_CURVE)
                points.append(normalizeFPoint(fpoint_, charSize))
            points.append(normalizeFPoint(fpoint, charSize))
            last_fpoint = fpoint
        # Contour beziers
        for i in range(int((len(points) + 2) / 3)):
            bezier = []
            for j in range(3):
                bezier.append(points[2 * i + j][0])
            beziers.append(bezier)
    return beziers
    

flags = filter(lambda x: x[0] == '-', sys.argv[1:])
font_path = sys.argv[1]
font = describe.openFont(font_path)
charHeight = glyphquery.charHeight(font)
glyphNameMap = font['cmap'].getcmap(*describe.guessEncoding(font)).cmap # char -> glyphName
charMap = dict([(value, key) for key, value in glyphNameMap.items()]) # glyphName -> char
glyph_names = font.getGlyphNames() \
    if ALL_GLYPHS else [glyphquery.glyphName(font, gn) for gn in CUSTOM_PARSING_GLYPHS]

glyphInfos = []
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

    # Make glyph info
    charSize = (charWidth, charHeight)
    beziers = fetchBeziers(contours, charSize)
    grid = makeGrid(beziers)
    glyphInfos.append({
        'char': char,
        'grid': grid,
        'beziers': beziers,
        'size': charSize,
    })

    # Statistic
    points_count = sum(map(lambda x: sum(map(lambda y: len(y), x)), beziers))
    if stat['maxPointsCount'][0] < points_count:
        stat['maxPointsCount'] = (points_count, char)
    if stat['maxGridSize'][0] < len(grid):
        stat['maxGridSize'] = (len(grid), char)
    

print
print(stat)
print
print
print('Glyph count:', len(glyphInfos))
print


def copyGrid(grid, atlas, coord):
    if len(grid) + coord[0] >= len(atlas) or len(grid) + coord[1] >= len(atlas[0]):
        print(len(grid), len(atlas), coord)
        raise 'Grid exceeded atlas'
    gridSize = len(grid)
    for i in range(gridSize):
        for j in range(gridSize):
            cell = grid[gridSize - 1 - i][gridSize - 1 - j]
            while len(cell) < 4:
                cell.append(0)
            atlas[coord[0] + j][coord[1] + i] = cell

def copyMatrix(matrix, atlas, coord):
    for r in range(len(matrix)):
        for c in range(len(matrix[r])):
            atlas[coord[0] + c][coord[1] + r] = matrix[r][c]

def initAtlas(width, height):
    return [[[0,0,0,0] for i in range(height)] for j in range(width)]

def compressBeziers(beziers):
    points = [beziers[0][0]]
    for b in beziers:
        points.append(b[1])
        points.append(b[2])
    return points

def convertShortToBytes(x):
    return [int(x) / 256, int(x) % 256]

ATLAS_WIDTH = 256
ATLAS_HEIGHT = 128

glyphStrokes = []
glyphCoords = {}
atlas = initAtlas(ATLAS_WIDTH, ATLAS_HEIGHT)
glyphGridCoord = [0, 0]
glyphInfos.sort(key=lambda x: len(x['grid']), reverse=True)
gridRowHeight = 0
gridsHeight = 0
for gi in glyphInfos:
    # Grid
    gridSize = len(gi['grid'])
    if gridRowHeight == 0:
        gridRowHeight = gridSize
        gridsHeight += gridRowHeight
    elif glyphGridCoord[0] + gridSize >= ATLAS_WIDTH:
        glyphGridCoord[0] = 0
        glyphGridCoord[1] += gridRowHeight
        gridRowHeight = gridSize
        gridsHeight += gridRowHeight
    copyGrid(gi['grid'], atlas, glyphGridCoord)
    glyphGridCoord[0] += gridSize

    # Stroke
    gridMin = copy(glyphGridCoord)
    rasteredGridMin = [0,0,0,0]
    gridSizeBytes = convertShortToBytes(gridSize)
    gridMinX = convertShortToBytes(gridMin[0])
    print(gridMinX)
    gridMinBytes = gridMinX + convertShortToBytes(gridMin[1])
    stroke = (gi['char'], gridMinBytes + rasteredGridMin + gridSizeBytes + [0, 0] + compressBeziers(gi['beziers']))
    glyphStrokes.append(stroke)

gridsHeight += gridRowHeight

glyphInfoMatrix = []
row = []
for s in glyphStrokes:
    if len(row) + len(s[1]) - 1 >= ATLAS_WIDTH:
        glyphInfoMatrix.append(row)
        row = []
    glyphCoords[s[0]] = [len(row), len(glyphStrokes) - 1]
    row += s[1]
copyMatrix(glyphInfoMatrix, atlas, [0, gridsHeight])


if not os.path.exists(DIST_DIR):
    os.makedirs(DIST_DIR)

with open('{}/glyphCoords.json'.format(DIST_DIR), 'w') as f:
    json.dump(glyphCoords, f)

with open('{}/glyphInfos.json'.format(DIST_DIR), 'w') as f:
    json.dump(glyphInfos, f)

with open("{}/atlas.bmp".format(DIST_DIR), 'w') as f:
    img = Image.new('RGBA', (ATLAS_WIDTH, ATLAS_HEIGHT), (255, 0, 0, 255))
    pixels = img.load()
    for i in range(ATLAS_WIDTH):
        for j in range(ATLAS_HEIGHT):
            cell = atlas[i][j]
            cell[3] = 255
            pixels[i,j] = tuple(cell)
    if '--show' in flags:
        img.show()
