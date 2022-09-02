# coding=utf-8

from cmath import sqrt
import math

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

def normalize_fpoint(fpoint, size, chardescent):
    return ((float(fpoint[0][0]) / size[0], float(fpoint[0][1] - chardescent) / size[1]), fpoint[1])

def is_point_inside(point, rectangle):
    """
    @param rectangle (x0,y0,x1,y1) x0,y0 left-bottom. x1,y1 right-top.
    """
    return point[0] >= rectangle[0] and point[0] <= rectangle[2] and \
        point[1] >= rectangle[1] and point[1] <= rectangle[3]

def is_inside_section(t, t1, t2):
    return t >= t1 and t <= t2
    
def fetch_bezier_cross(bezier, componentIndex, componentValue):
    """
    B(t) = (1-t)^2*p0 + 2(1-t)t*p1 + t^2*p2
    B(t) = (p0-2p1+p2)tt + 2(p1-p0)t + p0

    component is x or y.
    componentIndex == 0 is x.
    componentIndex == 1 is y.

    Возвращает список из t, в которых кривая безье пересекает прямую x=componentValue (или y=componentValue)
    @return [int] 
    """
    c0 = bezier[0][componentIndex]
    c1 = bezier[1][componentIndex]
    c2 = bezier[2][componentIndex]
    a = c0 - 2 * c1 + c2
    b = c1 - c0
    c = c0 - componentValue

    # Решаем уравнение ax**2 + bx + c = 0.

    # Линейная форма
    if isclose(a, 0):
        if isclose(b, 0):
            return []
        t = -c / b / 2
        return [t] if is_inside_section(t, 0, 1) else []
    # Квадратичная форма
    D = b ** 2 - a * c
    if D < 0:
        return []
    t1 = (-b - sqrt(D).real) / a
    t2 = (-b + sqrt(D).real) / a
    solution = []
    if is_inside_section(t1, 0, 1):
        solution.append(t1)
    if is_inside_section(t2, 0, 1):
        solution.append(t2)
    return solution

def calc_bezier(bezier, t):
    def calcComponentBezier(c0, c1, c2, t):
        return (1-t)**2*c0 + 2*(1-t)*t*c1 + t**2*c2

    p0, p1, p2 = bezier
    return (
        calcComponentBezier(p0[0], p1[0], p2[0], t),
        calcComponentBezier(p0[1], p1[1], p2[1], t)
    )

def is_bezier_crossing_cell(bezier, cell_rectangle):
    x1 = cell_rectangle[0]
    y1 = cell_rectangle[1]
    x2 = cell_rectangle[2]
    y2 = cell_rectangle[3]
    x1t = fetch_bezier_cross(bezier, 0, cell_rectangle[0])
    y1t = fetch_bezier_cross(bezier, 1, cell_rectangle[1])
    x2t = fetch_bezier_cross(bezier, 0, cell_rectangle[2])
    y2t = fetch_bezier_cross(bezier, 1, cell_rectangle[3])
    return is_point_inside(bezier[0], cell_rectangle) or is_point_inside(bezier[2], cell_rectangle)\
        or any(map(lambda t: is_inside_section(calc_bezier(bezier, t)[1], y1, y2), x1t))\
        or any(map(lambda t: is_inside_section(calc_bezier(bezier, t)[0], x1, x2), y1t))\
        or any(map(lambda t: is_inside_section(calc_bezier(bezier, t)[1], y1, y2), x2t))\
        or any(map(lambda t: is_inside_section(calc_bezier(bezier, t)[0], x1, x2), y2t))
    
def avrpoint(p1, p2):
    x0 = float(p1[0] + p2[0]) / 2
    y0 = float(p1[1] + p2[1]) / 2
    return (x0, y0)

def convert_short_to_bytes(x):
    return [int(x / 256), int(x % 256)]

def compress_beziers(beziers):
    """The end of i bezier is start of i+1 bezier."""
    if len(beziers) == 0:
        return []
    points = [beziers[0][0]]
    for b in beziers:
        points.append(b[1])
        points.append(b[2])
    return points

def split(a, n):
    """
    Split a array on n almost equal parts
    ref: https://stackoverflow.com/questions/2130016/splitting-a-list-into-n-parts-of-approximately-equal-length
    """
    k, m = divmod(len(a), n)
    return (a[i*k+min(i, m):(i+1)*k+min(i+1, m)] for i in range(n))

def split_by_length(a, n):
    """Split a by arrays with length = n"""
    return (a[i*n:(i+1)*n] for i in range(len(a) // n + min(len(a) % n, 1)))
