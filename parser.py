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
#CUSTOM_PARSING_GLYPHS = u'й'
#CUSTOM_PARSING_GLYPHS = u'еabc'
DIST_DIR = "../logos-graph_webgl/public/textures/my"

ATLAS_WIDTH = 256
ATLAS_HEIGHT = 128

print("Glyphs: " + (CUSTOM_PARSING_GLYPHS if not ALL_GLYPHS else 'all'))

# etc

def fetch_beziers(contours, char_size, char):
    """
    Начало координат находится в левом нижнем углу.
    Оси направлены вверх и направо.
    """
    beziers = []
    for ci, contour in enumerate(contours):
        # Fetch contour points
        points = []
        last_fpoint = contour[-1]
        for i, fpoint in enumerate(contour):
            if (last_fpoint[1] == fpoint[1] and fpoint[1] == OFF_CURVE):
                fpoint_ = (avrpoint(fpoint[0], last_fpoint[0]), ON_CURVE)
                points.append(normalize_fpoint(fpoint_, char_size, chardescent))
            if i > 0 and (last_fpoint[1] == fpoint[1] and fpoint[1] == ON_CURVE):
                fpoint_ = (avrpoint(fpoint[0], last_fpoint[0]), OFF_CURVE)
                points.append(normalize_fpoint(fpoint_, char_size, chardescent))
            points.append(normalize_fpoint(fpoint, char_size, chardescent))
            last_fpoint = fpoint
        # Group contour points into beziers
        for i in range(len(points) // 2):
            bezier = []
            for j in range(3):
                bezier.append(points[2 * i + j][0])
            beziers.append(bezier)

        #print('Points contour_{}\n'.format(ci) + '\n'.join(list(map(lambda p: str(p[0]), points))))
        
    return beziers
    
def make_grid(beziers, char):
    """
    (i,j) cell boundaries are (d*j, d*i, d*(j + 1), d*(i + 1)), where `d` is `1/gridSize`.
    Начальная ячейка находится в нижнем левом углу.
    (i,j) соответствует i строке, j столбцу.
    @return number[][];
    """
    MAX_GRID_SIZE = 32
    MAX_CELL_BEZIERS = 4

    def encodeMidClosest(x, y, d, cell):
        # Looking for neasest bezier to mid point on y=mid_y line
        mid = (x + .5) * d, (y + .5) * d
        crossing_bezier = None
        crossing_t = None
        min_distance = -1
        for b in beziers:
            t_arr = fetch_bezier_cross(b, 1, mid[1])
            for t in t_arr:
                p = calc_bezier(b, t)
                distance = p[0] - mid[0]
                if distance < 0 or min_distance != -1 and distance > min_distance:
                    continue
                min_distance = distance
                crossing_bezier = b
                crossing_t = t
        
        # Calc bezier local direction
        is_mid_colored = False
        dy = None
        if crossing_t is not None:
            dr = 1e-01
            p1 = calc_bezier(crossing_bezier, crossing_t - dr)
            p2 = calc_bezier(crossing_bezier, crossing_t + dr)
            dy = p2[1] - p1[1]
            is_mid_colored = dy < 0

        # Encode is_mid_colored in cell
        sorted(cell)
        cell = list(filter(lambda x: x > 0, cell))
        if len(cell) == 0:
            cell = [0, 1]
        while len(cell) < 4:
            cell.insert(0, 0)
        cell_tail = [cell[0], cell[3]] if is_mid_colored else [cell[3], cell[0]]
        result = cell[1:3] + cell_tail

        #if x == 2 and y == 5:
            #print(cell, result)
            #print('\n'.join(list(map(lambda b: '\n'.join(list(map(lambda p: str(p), b))), filter(lambda b: (beziers.index(b) + 2) in cell, beziers)))))
            #print(beziers)

        return result
        
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
                bp = None
                contour_index = 0
                for bi, b in enumerate(beziers):
                    if bp is not None and bp[2] != b[0]:
                        contour_index += 1
                    if is_bezier_crossing_cell(b, cellRectangle):
                        if len(cell) == MAX_CELL_BEZIERS:
                            skip = True
                            break
                        # Индексы начинаются с 2, тк 0 и 1 нужны 
                        # на кодировку цвета центра клетки.
                        cell.append(2 + bi + contour_index)
                    bp = b
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
    
    gridsize = len(grid)
    d = 1. / gridsize
    for rowi in range(gridsize):
        for coli in range(gridsize):
            grid[rowi][coli] = encodeMidClosest(coli, rowi, d, grid[rowi][coli])

    return grid

def copy_grid(grid, atlas, coord):
    """Copy grid into atlas with `coord` offset."""
    if len(grid) + coord[1] >= len(atlas) or len(grid) + coord[0] >= len(atlas[0]):
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
            try:
                atlas[coord[1] + r][coord[0] + c] = matrix[r][c]
            except Exception as ex:
                raise Exception('Exception on {}:{} ({}:{}): {}'.format(r, c, coord[1] + r, coord[0] + c, ex))

def convert_beziers_to_pixels(beziers):
    if len(beziers) == 0:
        return []
    pixels = []
    points = compress_beziers(beziers)
    for p in points:
        x_bytes = convert_short_to_bytes(round(p[0] * 0xffff))
        y_bytes = convert_short_to_bytes(round(p[1] * 0xffff))
        pixels.append(x_bytes + y_bytes)
    return pixels


flags = filter(lambda x: x[0] == '-', sys.argv[1:])
font_path = sys.argv[1]
font = describe.openFont(font_path)
charheight = glyphquery.charHeight(font)
chardescent = glyphquery.charDescent(font)
glyphname_map = font['cmap'].getcmap(*describe.guessEncoding(font)).cmap # char -> glyphName
charmap = dict([(value, key) for key, value in glyphname_map.items()]) # glyphName -> char
glyph_names = font.getGlyphNames() \
    if ALL_GLYPHS else [glyphquery.glyphName(font, gn) for gn in CUSTOM_PARSING_GLYPHS]

glyph_infos = []
stat = {
    'maxPointsCount': (0, None),
    'maxGridSize': (0, None),
    'maxCharWidth': (0, None),
}
for glyph_name in glyph_names:
    g = glyph.Glyph(glyph_name)
    contours = g.calculateContours(font)
    charwidth = glyphquery.width(font, glyph_name)
    if charwidth == 0 or glyph_name not in charmap:
        continue
    char = unichr(charmap[glyph_name])
    if charwidth > stat['maxCharWidth'][0]:
        stat['maxCharWidth'] = (charwidth, char)
    print(char)

    # Make glyph info
    charsize = (charwidth, charheight)
    beziers = fetch_beziers(contours, charsize, char)
    grid = make_grid(beziers, char)
    glyph_info = {
        'char': char,
        'grid': grid,
        'beziers': beziers,
        'size': charsize,
    }
    glyph_infos.append(glyph_info)

    # Statistic
    points_count = sum(map(lambda x: sum(map(lambda y: len(y), x)), beziers))
    if stat['maxPointsCount'][0] < points_count:
        stat['maxPointsCount'] = (points_count, char)
    if stat['maxGridSize'][0] < len(grid):
        stat['maxGridSize'] = (len(grid), char)
    

print
print(stat)
print('Char height', charheight)
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
    gridmin = copy(g_grid_coord)
    g_grid_coord[0] += gridsize

    # Stroke
    gridmin_pixel = convert_short_to_bytes(gridmin[0]) + convert_short_to_bytes(gridmin[1])
    rasteredgridmin_pixel = [0,0,0,0]
    size_k = 255. / stat['maxCharWidth'][0]
    rasteredsize = [int(gi['size'][0] * size_k), int(gi['size'][1] * size_k)]
    gridsize_pixel = [gridsize, gridsize] + rasteredsize
    beziers_pixels = convert_beziers_to_pixels(gi['beziers'])
    g_stroke = (gi['char'], [gridmin_pixel, rasteredgridmin_pixel, gridsize_pixel] + beziers_pixels, rasteredsize)
    g_strokes.append(g_stroke)

print('Grids height', grids_height)

# glyphs_info_rows -- вторая половина атласа, которая для каждой глифы хранит инфо о сетке глифы в атласе и координаты безье кривых в сжатом виде
# glyphs_info_row ~ gridmin | rasteredgridmin | gridsize + rasteredGridSize | compressedbezierpoints...
glyphs_info_rows = []
glyphs_info_row = []
# g_infos -- хранит координаты блока с инфо глифы в атласе, ширину глифы и тп.
g_infos = {}
g_strokes_coord = [0, grids_height]
for gs in g_strokes:
    if len(gs[1]) + len(glyphs_info_row) > ATLAS_WIDTH:
        glyphs_info_rows.append(glyphs_info_row)
        glyphs_info_row = []
    g_infos[gs[0]] = {
        'atlas_x': len(glyphs_info_row),
        'atlas_y': g_strokes_coord[1] + len(glyphs_info_rows),
        'width': gs[2][0],
        'height': gs[2][1],
    }
    glyphs_info_row += gs[1]
if len(glyphs_info_row) > 0:
    glyphs_info_rows.append(glyphs_info_row)
    
copy_matrix(glyphs_info_rows, atlas, g_strokes_coord)

if not os.path.exists(DIST_DIR):
    os.makedirs(DIST_DIR)

with open('{}/glyphs.json'.format(DIST_DIR), 'w') as f:
    json.dump(g_infos, f)

img = Image.new('RGBA', (ATLAS_WIDTH, ATLAS_HEIGHT), (0, 0, 0, 0))
pixels = img.load()
for i in range(ATLAS_HEIGHT):
    for j in range(ATLAS_WIDTH):
        try:
            cell = atlas[i][j]
            r, g, b, a = cell
            pixels[j,ATLAS_HEIGHT-1- i] = (b, g, r, a)
        except Exception as ex:
            raise Exception('Exception on ({0},{1})'.format(i,j))
img.save("{}/atlas.bmp".format(DIST_DIR))
if '--show' in flags:
    img.show()

print
print('Success!')
