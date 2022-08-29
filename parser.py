# -*- coding: utf-8 -*-
"""
    sys.argv[1] - path to font file.
"""
from copy import copy
import json
from ttfquery import describe
import ttfquery.glyph as glyph
import ttfquery.glyphquery as glyphquery
import sys
import os
from PIL import Image
from utils import *

ON_CURVE = 1
OFF_CURVE = 0
# Parses all glyphs in font if true, else parses glyphs from CUSTOM_PARSING_GLYPHS
ALL_GLYPHS = False
# If ALL_GLYPHS is False, fetch glyphs from CUSTOM_PARSING_GLYPHS
CUSTOM_PARSING_GLYPHS = u' `1234567890-=~!@#$%^&*()_+qwertyuiop[]QWERTYUIOP{}|asdfghjkl;\'ASDFGHJKL:"zxcvbnm,./ZXCVBNM<>?№ёЁйцукенгшщзхъ\\ЙЦУКЕНГШЩЗХЪфывапролджэФЫВАПРОЛДЖЭячсмитьбюЯЧСМИТЬБЮ'
#CUSTOM_PARSING_GLYPHS = u'еabc'
DIST_DIR = "dist"

ATLAS_WIDTH = 256
ATLAS_HEIGHT = 128

print("Glyphs: " + (CUSTOM_PARSING_GLYPHS if not ALL_GLYPHS else 'all'))

# etc

def fetch_beziers(contours, char_size):
    """
    Начало координат находится в левом нижнем углу.
    Оси направлены вверх и направо.
    """
    beziers = []
    for contour in contours:
        # Fetch contour points
        points = []
        last_fpoint = contour[-1]
        for i, fpoint in enumerate(contour):
            if (last_fpoint[1] == fpoint[1] and fpoint[1] == OFF_CURVE):
                fpoint_ = (avrpoint(fpoint[0], last_fpoint[0]), ON_CURVE)
                points.append(normalize_fpoint(fpoint_, char_size))
            if i > 0 and (last_fpoint[1] == fpoint[1] and fpoint[1] == ON_CURVE):
                fpoint_ = (avrpoint(fpoint[0], last_fpoint[0]), OFF_CURVE)
                points.append(normalize_fpoint(fpoint_, char_size))
            points.append(normalize_fpoint(fpoint, char_size))
            last_fpoint = fpoint
        # Group contour points into beziers
        for i in range(int((len(points) + 2) / 3)):
            bezier = []
            for j in range(3):
                bezier.append(points[2 * i + j][0])
            beziers.append(bezier)
    return beziers
    
def make_grid(beziers):
    """
    (i,j) cell boundaries are (d*j, d*i, d*(j + 1), d*(i + 1)), where `d` is `1/gridSize`.
    Начальная ячейка находится в нижнем левом углу.
    (i,j) соответствует i строке, j столбцу.
    @return number[][];
    """
    MAX_GRID_SIZE = 32
    MAX_CELL_BEZIERS = 4
    grid = None
    for gridsize in range(2, MAX_GRID_SIZE):
        grid = []
        skip = False
        d = 1. / gridsize
        for i in range(gridsize):
            row = []
            for j in range(gridsize):
                cellRectangle = (d*j, d*i, d*(j + 1), d*(i + 1)) # (x1,y1,x2,y2)
                cell = []
                for bi, b in enumerate(beziers):
                    if is_bezier_crossing_cell(b, cellRectangle):
                        if len(cell) == MAX_CELL_BEZIERS:
                            skip = True
                            break
                        cell.append(bi)
                if skip:
                    break
                row.append(cell)
            if skip:
                break
            grid.append(row)
        if not skip:
            break
        if gridsize == MAX_GRID_SIZE - 1:
            raise Exception("Max grid size enriched")
    return grid

def copy_grid(grid, atlas, coord):
    """Copy grid into atlas with `coord` offset."""
    if len(grid) + coord[1] >= len(atlas) or len(grid) + coord[0] >= len(atlas[0]):
        print(len(grid), len(atlas), coord)
        raise Exception('Grid exceeded atlas')
    grid_size = len(grid)
    for rowi in range(grid_size):
        for coli in range(grid_size):
            cell = grid[rowi][coli] # todo: check
            while len(cell) < 4:
                cell.append(0)
            atlas[coord[1] + rowi][coord[0] + coli] = cell

def copy_matrix(matrix, atlas, coord):
    """Copy matrix into atlas by rows with `coord` offset."""
    for r in range(len(matrix)):
        for c in range(len(matrix[r])):
            atlas[coord[1] + r][coord[0] + c] = matrix[r][c]

def convert_beziers_to_pixels(beziers):
    if len(beziers) == 0:
        return []
    pixels = []
    points = compress_beziers(beziers)
    assert(len(points) % 2 == 1, 'Points length is not odd: {0}'.format(len(points)))
    for p in points:
        x = int(p[0] * 0xff) # todo: check native shader implementation
        y = int(p[1] * 0xff)
        if len(pixels) > 0 and len(pixels[-1]) == 2:
            pixels[-1] += [x, y]
        else:
            pixels.append([x, y])
    pixels[-1] += [0,0] # Because points is odd length, needs to be aligned to 4 bytes
    return pixels


flags = filter(lambda x: x[0] == '-', sys.argv[1:])
font_path = sys.argv[1]
font = describe.openFont(font_path)
charheight = glyphquery.charHeight(font)
glyphname_map = font['cmap'].getcmap(*describe.guessEncoding(font)).cmap # char -> glyphName
charmap = dict([(value, key) for key, value in glyphname_map.items()]) # glyphName -> char
glyph_names = font.getGlyphNames() \
    if ALL_GLYPHS else [glyphquery.glyphName(font, gn) for gn in CUSTOM_PARSING_GLYPHS]

glyph_infos = []
stat = {
    'maxPointsCount': (0, None),
    'maxGridSize': (0, None),
}
for glyph_name in glyph_names:
    g = glyph.Glyph(glyph_name)
    contours = g.calculateContours(font)
    charwidth = glyphquery.width(font, glyph_name)
    if charwidth == 0 or glyph_name not in charmap:
        continue
    char = unichr(charmap[glyph_name])
    print(char)

    # Make glyph info
    charsize = (charwidth, charheight)
    beziers = fetch_beziers(contours, charsize)
    grid = make_grid(beziers)
    glyph_infos.append({
        'char': char,
        'grid': grid,
        'beziers': beziers,
        'size': charsize,
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
print('Glyph count:', len(glyph_infos))
print

# `g`` is `glyph`
# g_strokes -- хранит массив из кортежей вида (glyphchar, glyphinfobytes)
g_strokes = []
atlas = [[[0,0,0,0] for i in range(ATLAS_WIDTH)] for j in range(ATLAS_HEIGHT)]
g_grid_coord = [0, 0]
glyph_infos.sort(key=lambda x: len(x['grid']), reverse=True)
current_grids_row_height = 0
grids_height = 0
for gi in glyph_infos:
    # Grid
    gridsize = len(gi['grid'])
    if current_grids_row_height == 0:
        current_grids_row_height = gridsize
        grids_height += current_grids_row_height
    elif g_grid_coord[0] + gridsize >= ATLAS_WIDTH:
        g_grid_coord[0] = 0
        g_grid_coord[1] += current_grids_row_height
        current_grids_row_height = gridsize
        grids_height += current_grids_row_height
    copy_grid(gi['grid'], atlas, g_grid_coord)
    g_grid_coord[0] += gridsize

    # Stroke
    gridmin = copy(g_grid_coord)
    rasteredgridmin_pixel = [0,0,0,0]
    gridsize_pixel = convert_short_to_bytes(gridsize) + [0, 0]
    gridmin_pixel = convert_short_to_bytes(gridmin[0]) + convert_short_to_bytes(gridmin[1])
    beziers_pixels = convert_beziers_to_pixels(gi['beziers'])
    g_stroke = (gi['char'], [gridmin_pixel, rasteredgridmin_pixel, gridsize_pixel] + beziers_pixels)
    g_strokes.append(g_stroke)

print('Grids height', grids_height)

# glyphs_info_rows -- вторая половина атласа, которая для каждой глифы хранит инфо о сетке глифы в атласе и координаты безье кривых в сжатом виде
# glyphs_info_row ~ gridmin | rasteredgridmin | gridsize | compressedbezierpoints
glyphs_info_rows = []
# g_coords -- хранит координаты блока с инфо глифы в атласе
g_coords = {}
glyphs_info_row = []
for gs in g_strokes:
    if len(glyphs_info_row) + len(gs[1]) > ATLAS_WIDTH:
        if len(glyphs_info_row) == 0:
            raise Exception('Glyph info row is 0 length! Check {0} with {1} length'.format(gs[0], len(gs[1])))
        glyphs_info_rows.append(glyphs_info_row)
        glyphs_info_row = []
    g_coords[gs[0]] = [len(glyphs_info_row), len(glyphs_info_rows) - 1]
    glyphs_info_row += gs[1]
copy_matrix(glyphs_info_rows, atlas, [0, grids_height])

if not os.path.exists(DIST_DIR):
    os.makedirs(DIST_DIR)

with open('{}/glyphCoords.json'.format(DIST_DIR), 'w') as f:
    json.dump(g_coords, f)

with open('{}/glyphInfos.json'.format(DIST_DIR), 'w') as f:
    json.dump(glyph_infos, f)

with open("{}/atlas.bmp".format(DIST_DIR), 'w') as f:
    img = Image.new('RGBA', (ATLAS_WIDTH, ATLAS_HEIGHT), (255, 0, 0, 255))
    pixels = img.load()
    for i in range(ATLAS_HEIGHT):
        for j in range(ATLAS_WIDTH):
            try:
                cell = atlas[i][j]
                cell[3] = 255
                pixels[j,i] = tuple(cell)
            except Exception as ex:
                raise Exception('Exception on ({0},{1})'.format(i,j))
    if '--show' in flags:
        img.show()
