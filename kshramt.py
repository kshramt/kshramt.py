from math import sin, cos, acos, sqrt, hypot, pi, log10, ceil, floor
import argparse
import collections
import dataclasses
import functools
import itertools
import logging
import multiprocessing
import operator
import os
import pprint
import sys
import tempfile
import typing
import unittest


__version__ = "0.1.0"


logger = logging.getLogger(__name__)


class Error(Exception):
    pass


TICK_INTERVAL_PADDING_RATIO = 0.1
_PY37 = sys.version_info.major == 3 and sys.version_info.minor == 7


class AppendDbV1:
    def __init__(self, path):
        mkdir(path)
        self.path = path
        self.fp_index = open(jp(path, "index.i64"), "a+b")
        self.fp_data = open(jp(path, "data.txt"), "a+b")

    def __repr__(self):
        return f"{self.__class__.__name__}({repr(self.path)})"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.fp_index.close()
        self.fp_data.close()

    def __len__(self):
        s = os.fstat(self.fp_index.fileno()).st_size
        if s % 8 != 0:
            logger.warning("Incompletely written index for %s with %s B.", self.path, s)
        return s // 8

    def __getitem__(self, i: int):
        i = range(len(self))[i]
        ib1, ib2 = self._ib1_of(i), self._ib2_of(i)
        self.fp_data.seek(ib1)
        return self.fp_data.read(ib2 - ib1).decode("utf-8")

    def append(self, t: str):
        b = t.encode("utf-8")
        l = len(self)
        ib1 = self._ib1_of(l)
        self.fp_data.seek(ib1)
        dib = self.fp_data.write(b)
        self.fp_index.seek(l * 8)
        try:
            self.fp_index.write(self._bytes(ib1 + dib))
        except OSError:
            self.fp_index.truncate(l * 8)
            raise
        self.flush()

    def flush(self):
        self.fp_data.flush()
        self.fp_index.flush()

    def _ib1_of(self, i):
        return 0 if i == 0 else self._ib_of(i - 1)

    def _ib2_of(self, i):
        return self._ib_of(i)

    def _ib_of(self, i):
        self.fp_index.seek(i * 8)
        return self._int(self.fp_index.read(8))

    @staticmethod
    def _bytes(i: int):
        return i.to_bytes(8, "little", signed=False)

    @staticmethod
    def _int(b: bytes):
        return int.from_bytes(b, "little", signed=False)


class subplots:
    def __init__(self, **kwargs):
        import matplotlib.pyplot

        self.fig, self.axs = matplotlib.pyplot.subplots(**kwargs)

    def __enter__(self):
        return self.fig, self.axs

    def __exit__(self, typ, val, traceback):
        import matplotlib.pyplot

        matplotlib.pyplot.close(self.fig)


class rcparams:
    """
    Use `plt.rc_context` instead of this.
    """

    def __init__(self, *args):
        assert len(args) % 2 == 0
        self.params = (
            (args[2 * i + 0], args[2 * i + 1]) for i in range(len(args) // 2)
        )

    def __enter__(self):
        import matplotlib

        self.rcparams_orig = list(matplotlib.rcParams.items())
        for k, v in self.params:
            matplotlib.rcParams[k] = v

    def __exit__(self, typ, val, traceback):
        import matplotlib

        matplotlib.rcParams.clear()
        for k, v in self.rcparams_orig:
            matplotlib.rcParams[k] = v


if _PY37:

    def dataclass_of(cls, x):
        if dataclasses.is_dataclass(cls):
            if not isinstance(x, dict):
                raise TypeError(f"{x}: {type(x)} is not compatible with {cls}")
            fields = {f.name: f.type for f in dataclasses.fields(cls)}
            if set(fields.keys()) != set(x.keys()):
                raise TypeError(f"{x}: {type(x)} is not compatible with {cls}")
            return cls(**{k: dataclass_of(fields[k], v) for k, v in x.items()})
        elif type(cls) == type:
            if not isinstance(x, cls):
                raise TypeError(f"{x}: {type(x)} is not compatible with {cls}")
            return x
        elif isinstance(cls, tuple):
            if x not in cls:
                raise TypeError(f"{x} is not compatible with {cls}")
            return x
        elif cls.__origin__ == list or cls.__origin__ == collections.abc.Sequence:
            vcls = cls.__args__[0]
            return [dataclass_of(vcls, v) for v in x]
        elif cls.__origin__ == dict or cls.__origin__ == collections.abc.Mapping:
            kcls, vcls = cls.__args__
            return {dataclass_of(kcls, k): dataclass_of(vcls, v) for k, v in x.items()}
        elif cls.__origin__ == set:
            vcls = cls.__args__[0]
            return {dataclass_of(vcls, v) for v in x}
        elif cls.__origin__ == tuple:
            vclss = cls.__args__
            if len(vclss) != len(x):
                raise TypeError(f"{x}: {type(x)} is not compatible with {cls}")
            return tuple(dataclass_of(vcls, v) for vcls, v in zip(vclss, x))
        elif cls.__origin__ == typing.Union:
            for ucls in cls.__args__:
                try:
                    return dataclass_of(ucls, x)
                except TypeError:
                    pass
            raise TypeError(f"{x}: {type(x)} is not compatible with {cls}")
        else:
            raise ValueError(f"Unsupported value {x}: {type(x)}")


else:

    def dataclass_of(cls, x):
        if dataclasses.is_dataclass(cls):
            if not isinstance(x, dict):
                raise TypeError(f"{x}: {type(x)} is not compatible with {cls}")
            fields = {f.name: f.type for f in dataclasses.fields(cls)}
            if set(fields.keys()) != set(x.keys()):
                raise TypeError(f"{x}: {type(x)} is not compatible with {cls}")
            return cls(**{k: dataclass_of(fields[k], v) for k, v in x.items()})
        elif type(cls) == type:
            if not isinstance(x, cls):
                raise TypeError(f"{x}: {type(x)} is not compatible with {cls}")
            return x
        elif cls.__origin__ == typing.Literal:
            if x not in cls.__args__:
                raise TypeError(f"{x} is not compatible with {cls}")
            return x
        elif cls.__origin__ == list or cls.__origin__ == collections.abc.Sequence:
            vcls = cls.__args__[0]
            return [dataclass_of(vcls, v) for v in x]
        elif cls.__origin__ == dict or cls.__origin__ == collections.abc.Mapping:
            kcls, vcls = cls.__args__
            return {dataclass_of(kcls, k): dataclass_of(vcls, v) for k, v in x.items()}
        elif cls.__origin__ == set:
            vcls = cls.__args__[0]
            return {dataclass_of(vcls, v) for v in x}
        elif cls.__origin__ == tuple:
            vclss = cls.__args__
            if len(vclss) != len(x):
                raise TypeError(f"{x}: {type(x)} is not compatible with {cls}")
            return tuple(dataclass_of(vcls, v) for vcls, v in zip(vclss, x))
        elif cls.__origin__ == typing.Union:
            for ucls in cls.__args__:
                try:
                    return dataclass_of(ucls, x)
                except TypeError:
                    pass
            raise TypeError(f"{x}: {type(x)} is not compatible with {cls}")
        else:
            raise ValueError(f"Unsupported value {x}: {type(x)}")


def consume(g):
    import collections

    collections.deque(g, maxlen=0)


def shell_escape(s):
    """
    Use `shlex.quote` instead of this
    """
    import io

    fp = io.StringIO()
    sq = "'" + '"' + "'" + '"' + "'"
    dollar = "'" + "'" + "$" + "'" + "'"
    print("'", end="", file=fp)
    for c in s:
        if c == "'":
            print(sq, end="", file=fp)
        elif c == "$":
            print(dollar, end="", file=fp)
        else:
            print(c, end="", file=fp)
    print("'", end="", file=fp)
    return fp.getvalue()


def split_dt(ts, xss, dt, t_min):
    assert all(len(ts) == len(xs) for xs in xss)
    from scipy import searchsorted

    t1, t2 = t_min, t_min + dt
    i1, i2 = searchsorted(ts, t1), searchsorted(ts, t2)
    while True:
        yield ts[i1:i2], tuple(xs[i1:i2] for xs in xss)
        t2 += dt
        i1, i2 = i2, searchsorted(ts, t2)


def split(xs, n):
    assert n > 0
    ret = [None for _ in range(n)]
    i = 0
    for x in xs:
        ret[i] = x
        i += 1
        if i % n == 0:
            yield ret
            ret = [None for _ in range(n)]
            i = 0


def mapcat(f, xs):
    return concat(map(f, xs))


def concat(xss):
    for xs in xss:
        yield from xs


def dump_structured_points_3(
    vs, dx=1, dy=1, dz=1, x0=0, y0=0, z0=0, dtype="FLOAT", fp=sys.stdout
):
    assert dx > 0
    assert dy > 0
    assert dz > 0
    nx = len(vs)
    assert nx >= 1
    ny = len(vs[0])
    assert ny >= 1
    nz = len(vs[0][0])
    assert nz >= 1
    print(
        """# vtk DataFile Version 3.0
voxel
ASCII
DATASET STRUCTURED_POINTS
DIMENSIONS {nx} {ny} {nz}
ORIGIN {x0} {y0} {z0}
SPACING {dx} {dy} {dz}
POINT_DATA {n}
SCALARS v {dtype}
LOOKUP_TABLE default""".format(
            nx=nx,
            ny=ny,
            nz=nz,
            x0=x0,
            y0=y0,
            z0=z0,
            dx=dx,
            dy=dy,
            dz=dz,
            n=nx * ny * nz,
            dtype=dtype,
        ),
        file=fp,
    )
    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                print(vs[ix][iy][iz], file=fp)


def make_load(record_generator, parse_record):
    def load(fp, error_f=None):
        g = record_generator(fp)
        if error_f is None:
            for r in g:
                yield parse_record(r)
        else:
            for r in g:
                try:
                    yield parse_record(r)
                except Exception as e:
                    should_yield, v = error_f(r, e)
                    if should_yield:
                        yield v

    return load


def sign(x):
    if x > 0:
        return 1
    elif x < 0:
        return -1
    else:
        return 0


def rad(d):
    return d * pi / 180


def deg(r):
    return r * 180 / pi


def _R_theta_phi(theta, phi):
    ct = cos(theta)
    st = sin(theta)
    cp = cos(phi)
    sp = sin(phi)
    return dot(
        ((ct, 0, -st), (0, 1, 0), (st, 0, ct)), ((cp, -sp, 0), (sp, cp, 0), (0, 0, 1))
    )


_INVARIANT_ROTATIONS_FOR_DIAG = (
    ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    ((-1, 0, 0), (0, -1, 0), (0, 0, 1)),
    ((1, 0, 0), (0, -1, 0), (0, 0, -1)),
    ((-1, 0, 0), (0, 1, 0), (0, 0, -1)),
)


def kagan_angles(P, Q):
    """
    P: rotation matrix [3x3]
    Q: rotation matrix [3x3]

    Reference: Kagan, Y. Y. (1991), 3-D rotation of double-couple earthquake sources, Geophys. J. Int., 106(3), 709–716, doi:10.1111/j.1365-246X.1991.tb06343.x.
    """

    PtQ = dot(P, transpose(Q))
    # If `diag(dot(PtQ, R)) + 1 < 0` (when input is inaccurate), replace it by 0.
    # This replacement may not cause any problematic result since:
    # 1) If the term is near 0, angle is near π.
    # 2) The minimum rotation angle cannot exceed 120 degrees (Kagan, 1990).
    return tuple(
        2 * acos(sqrt(max(sum(diag(dot(PtQ, R))) + 1, 0)) / 2)
        for R in _INVARIANT_ROTATIONS_FOR_DIAG
    )


def diag(m):
    return [m[i][i] for i in range(min(len(m), len(m[0])))]


def dot(*ms):
    return functools.reduce(_dot, ms)


def _dot(A, B):
    m = len(A)
    nA = len(A[0])
    nB = len(B)
    assert nA == nB
    l = len(B[0])
    m_range = range(m)
    n_range = range(nA)
    l_range = range(l)
    ret = []
    for i in m_range:
        Ai = A[i]
        ret.append([sum(Ai[k] * B[k][j] for k in n_range) for j in l_range])
    return ret


def transpose(A):
    m = len(A)
    n = len(A[0])
    m_range = range(m)
    n_range = range(n)
    return [[A[i][j] for i in m_range] for j in n_range]


def binning(xs, bins, x_min=None, x_max=None):
    if bins < 1:
        return []
    n_xs = len(xs)
    if n_xs < 1:
        return []
    elif n_xs == 1:
        x_min = xs[0] - 1 / 2 if x_min is None else x_min
        x_max = xs[0] + 1 / 2 if x_max is None else x_max
    else:
        x_min = min(xs) if x_min is None else x_min
        x_max = max(xs) if x_max is None else x_max
    dx = (x_max - x_min) / bins
    assert 0 < max(abs(x_min), abs(x_max)) * sys.float_info.epsilon <= dx
    ns = [0 for _ in range(bins)]
    for x in xs:
        if x < x_min or x_max < x:
            continue
        fi_bin = (x - x_min) / dx
        i_bin = int(fi_bin)
        if i_bin <= 0:
            ns[0] += 1
        elif i_bin >= bins:
            ns[-1] += 1
        elif fi_bin == i_bin:
            ns[i_bin] += 1 / 2
            ns[i_bin - 1] += 1 / 2
        else:
            ns[i_bin] += 1
    return (
        dx,
        [
            (x1, x2, n, n / n_xs)
            for (x1, x2), n in zip(each_cons(linspace(x_min, x_max, bins + 1), 2), ns)
        ],
    )


def min_max(xs):
    assert len(xs)
    min_ = max_ = xs[0]
    for x in xs[1:]:
        if x > max_:
            max_ = x
        elif x < min_:
            min_ = x
    return min_, max_


def linspace(start, stop, num=50):
    if num < 1:
        return []
    elif num == 1:
        return [start]
    step = (stop - start) / (num - 1)
    ret = [start + step * i for i in range(num - 1)]
    ret.append(stop)
    return ret


GOLDEN_RATIO = (1 + sqrt(5)) / 2
_SPHERE_MESH_BASES = {
    4: (
        [(0, 1, 2), (1, 2, 3), (2, 3, 0), (0, 1, 3)],
        [
            (0, 0, 1),
            (2 * sqrt(2) / 3, 0, -1 / 3),
            (-sqrt(2) / 3, sqrt(2 / 3), -1 / 3),
            (-sqrt(2) / 3, -sqrt(2 / 3), -1 / 3),
        ],
        1,
    ),
    8: (
        [
            (4, 0, 1),
            (4, 1, 2),
            (4, 2, 3),
            (4, 3, 0),
            (5, 0, 1),
            (5, 1, 2),
            (5, 2, 3),
            (5, 3, 0),
        ],
        [(1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)],
        1,
    ),
    # http://en.wikipedia.org/wiki/Icosahedron#Cartesian_coordinates
    20: (
        [
            (8, 9, 5),
            (8, 9, 4),
            (7, 5, 2),
            (7, 5, 3),
            (3, 1, 9),
            (3, 1, 11),
            (4, 6, 1),
            (4, 6, 0),
            (0, 2, 8),
            (0, 2, 10),
            (10, 11, 6),
            (10, 11, 7),
            (2, 8, 5),
            (8, 4, 0),
            (0, 6, 10),
            (10, 7, 2),
            (5, 3, 9),
            (9, 4, 1),
            (1, 6, 11),
            (11, 3, 7),
        ],
        [
            (0, 1, GOLDEN_RATIO),
            (0, 1, -GOLDEN_RATIO),
            (0, -1, GOLDEN_RATIO),
            (0, -1, -GOLDEN_RATIO),
            (1, GOLDEN_RATIO, 0),
            (1, -GOLDEN_RATIO, 0),
            (-1, GOLDEN_RATIO, 0),
            (-1, -GOLDEN_RATIO, 0),
            (GOLDEN_RATIO, 0, 1),
            (GOLDEN_RATIO, 0, -1),
            (-GOLDEN_RATIO, 0, 1),
            (-GOLDEN_RATIO, 0, -1),
        ],
        sqrt(1 ** 2 + GOLDEN_RATIO ** 2),
    ),
}


def sphere_mesh(n=0, r=1, base=20):
    assert n >= 0
    triangles, points, r_ = _SPHERE_MESH_BASES[base]
    points_ = [(x / r_, y / r_, z / r_) for x, y, z in points]
    for _ in range(0, n):
        new_triangles = []
        for triangle in triangles:
            new_triangles.extend(_divide_triangle(triangle, points_))
        triangles = new_triangles
    return list(triangles), [(r * x, r * y, r * z) for x, y, z in points_]


def _divide_triangle(triangle, points):
    i_p1, i_p2, i_p3 = triangle
    p1 = points[i_p1]
    p2 = points[i_p2]
    p3 = points[i_p3]
    n_points = len(points)
    p12 = _unit_middle_point(p1, p2)
    points.append(p12)
    i_p12 = n_points + 0
    p23 = _unit_middle_point(p2, p3)
    points.append(p23)
    i_p23 = n_points + 1
    p31 = _unit_middle_point(p3, p1)
    points.append(p31)
    i_p31 = n_points + 2
    return (
        (i_p1, i_p12, i_p31),
        (i_p2, i_p12, i_p23),
        (i_p3, i_p23, i_p31),
        (i_p12, i_p23, i_p31),
    )


def _unit_middle_point(p1, p2):
    x1, y1, z1 = p1
    x2, y2, z2 = p2
    x = (x1 + x2) / 2
    y = (y1 + y2) / 2
    z = (z1 + z2) / 2
    r = sqrt(x * x + y * y + z * z)
    return x / r, y / r, z / r


def is_in_polygon(x, y, xs, ys):
    """Winding-number algorithm
    (x1, y1)-(x2, y2)-...-(xn, yn)-(x1, y1)
    points should be counterclockwise and should not intersect.
    """

    xs = [xi - x for xi in xs]
    n = len(xs)
    assert n > 2
    xs.append(xs[0])
    ys = [yi - y for yi in ys]
    assert len(ys) == n
    ys.append(ys[0])
    th = 0
    for i in range(n):
        x1 = xs[i]
        y1 = ys[i]
        x2 = xs[i + 1]
        y2 = ys[i + 1]
        th += sign(x1 * y2 - y1 * x2) * _acos(
            (x1 * x2 + y1 * y2) / (hypot(x1, y1) * hypot(x2, y2))
        )
    return abs(th) > 1


def _acos(x):
    try:
        return acos(x)
    except ValueError:
        assert abs(x) < 1.000001
        if x > 0:
            return 0
        else:
            return pi


def is_in_convex_polygon(px, py, xys, is_counterclockwise=True):
    if not is_counterclockwise:
        return is_in_convex_polygon(px, py, list(reversed(xys)))
    else:
        assert is_convex(xys, is_counterclockwise)
        x1, y1 = xys[0]
        x1 -= px
        y1 -= py
        for x2, y2 in itertools.chain(xys, xys[0:1]):
            x2 -= px
            y2 -= py
            if x1 * y2 - y1 * x2 < 0:
                return False
            x1 = x2
            y1 = y2
        return True


def is_convex(xys, is_counterclockwise=True):
    if not is_counterclockwise:
        return is_convex(list(reversed(xys)))
    else:
        assert len(xys) >= 3
        (x1, y1), (x2, y2), *more = xys
        for x3, y3 in itertools.chain(more, xys[0:1]):
            dx12 = x2 - x1
            dy12 = y2 - y1
            dx23 = x3 - x2
            dy23 = y3 - y2
            if dx12 * dy23 - dy12 * dx23 < 0:
                return False
            x1 = x2
            y1 = y2
            x2 = x3
            y2 = y3
        return True


def seq(x1, dx, x2=None, end=True, comp=operator.le):
    x = x1
    if x2 is None:
        while True:
            yield x
            x += dx
    else:
        while comp(x, x2):
            yield x
            x += dx
        if end:
            yield x


def each_cons(xs, n):
    assert n >= 1
    if isinstance(xs, collections.abc.Iterator):
        return _each_cons_iter(xs, n)
    else:
        return _each_cons(xs, n)


def _each_cons_iter(xs, n):
    ret = []
    try:
        for _ in range(n):
            ret.append(next(xs))
    except StopIteration:
        return
    yield ret
    for x in xs:
        ret = ret[1:]
        ret.append(x)
        yield ret


def _each_cons(xs, n):
    return [xs[i : i + n] for i in range(len(xs) - (n - 1))]


def parallel_for(f, *indicess, commons=(), chunk_size=1):
    p = multiprocessing.Pool()
    ret = reshape(
        p.starmap(
            f,
            (ijk + commons for ijk in itertools.product(*indicess)),
            chunksize=chunk_size,
        ),
        [len(indices) for indices in indicess],
    )
    p.close()
    return ret


def reshape(xs, ns):
    assert len(ns)
    assert len(xs) == functools.reduce(operator.mul, ns, 1)
    return _reshape(xs, ns)


def _reshape(xs, ns):
    if len(ns) == 1:
        return xs
    return _reshape(partition(xs, ns[-1]), ns[0:-1])


def partition(xs, n):
    return [xs[i - n : i] for i in range(n, len(xs) + 1, n)]


def memoize(f):
    cache = {}

    def memoized_f(*args):
        if args in cache:
            return cache[args]
        else:
            cache[args] = retv = f(*args)
            return retv

    memoized_f.cache = cache
    return memoized_f


def profiled_memoize(f):
    cache = {}
    profile = {"new": 0, "hit": 0}

    def profiled_memoized_f(*args):
        if args in cache:
            profile["hit"] += 1
            return cache[args]
        else:
            profile["new"] += 1
            cache[args] = retv = f(*args)
            return retv

    profiled_memoized_f.cache = cache
    profiled_memoized_f.profile = profile
    return profiled_memoized_f


def _get_interval(lx):
    assert lx > 0
    dx = 10 ** (ceil(log10(lx)) - 1)
    if lx > 5 * dx:
        return dx
    elif lx > 2 * dx:
        return 5 * dx / 10
    else:
        return 2 * dx / 10


def _get_lower_limit(x, dx, padding_ratio=TICK_INTERVAL_PADDING_RATIO):
    assert dx > 0
    lower = floor(x / dx) * dx
    if x <= lower + dx * padding_ratio:
        lower -= dx
    return lower


def _get_upper_limit(x, dx, padding_ratio=TICK_INTERVAL_PADDING_RATIO):
    assert dx > 0
    upper = ceil(x / dx) * dx
    if x >= upper - dx * padding_ratio:
        upper += dx
    return upper


def get_tick_configurations(x1, x2, padding_ratio=TICK_INTERVAL_PADDING_RATIO):
    x_small, x_large = sorted([x1, x2])
    dx = _get_interval(x_large - x_small)
    lower = _get_lower_limit(x_small, dx, padding_ratio)
    upper = _get_upper_limit(x_large, dx, padding_ratio)
    return lower, upper, dx


def pp(x):
    pprint.pprint(x, stream=sys.stderr)
    return x


def flatten(xss):
    """
    # Flatten containers

    ## Note
    Do not include recursive elements.

    ## Exceptions
    - `RuntimeError`: Recursive elements will cause this
    """
    if isinstance(xss, str):
        yield xss
    else:
        for xs in xss:
            if isinstance(xs, collections.abc.Iterable):
                for x in flatten(xs):
                    yield x
            else:
                yield xs


def list_2d(n_row, n_column, init=None):
    assert n_row >= 1
    assert n_column >= 1

    return [[init for _ in range(n_column)] for _ in range(n_row)]


def make_parse_fixed_width(fields):
    """
    fields: (('density', 3, int),
             2, # skip 2 characters
             ('opacity', 7, float))
    """
    lower = 0
    upper_max = 0
    _fields = []
    for field in fields:
        if isinstance(field, int):
            upper = lower + field
        else:
            name, length, converter = field
            upper = lower + length
            _fields.append((name, lower, upper, converter))
        if upper > upper_max:
            upper_max = upper
        lower = upper
    record_width = upper_max

    def parse_fixed_width(s):
        assert len(s) >= record_width
        return {
            name: converter(s[lower:upper]) for name, lower, upper, converter in _fields
        }

    return parse_fixed_width


def let(f):
    return f()


def mkdir(path):
    os.makedirs(path, exist_ok=True)


def dirname(path):
    return os.path.dirname(path) or os.path.curdir


def jp(path, *more):
    return os.path.normpath(os.path.sep.join((path, os.path.sep.join(more))))


class TestAction(argparse.Action):
    def __init__(
        self,
        option_strings,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help=None,
    ):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        unittest.main(argv=sys.argv[:1])
        parser.exit()


def _fn_for_test_parallel_for(x, y):
    return x, y


class _Tester(unittest.TestCase):
    def test_shell_escape(self):
        for s, ex in (
            ("", "''"),
            ("\\", "'\\'"),
            ("\n$", "'\n''$'''"),
            ("a'b'", "'a'\"'\"'b'\"'\"''"),
        ):
            self.assertEqual(shell_escape(s), ex)

    def test_split_dt(self):
        import itertools

        self.assertEqual(
            list(itertools.islice(split_dt([0, 1, 1.1], ([4, 5, 5.1],), 0.5, -0.6), 5)),
            [
                ([], ([],)),
                ([0], ([4],)),
                ([], ([],)),
                ([1, 1.1], ([5, 5.1],)),
                ([], ([],)),
            ],
        )

    def test_split(self):
        self.assertEqual(list(split(range(5), 2)), [[0, 1], [2, 3]])
        self.assertEqual(list(split(range(0), 2)), [])
        self.assertEqual(list(split(range(1), 2)), [])
        self.assertEqual(list(split(range(6), 3)), [[0, 1, 2], [3, 4, 5]])
        with self.assertRaises(AssertionError):
            list(split(range(5), 0))

    def test_mapcat(self):
        self.assertEqual(
            list(mapcat(lambda xs: map(int, xs), [["1", "2"], [], ["3"]])), [1, 2, 3]
        )

    def test_seq(self):
        self.assertEqual(list(seq(1, 1, 3)), [1, 2, 3, 4])
        self.assertEqual(list(seq(1, 1, 3, end=False)), [1, 2, 3])
        self.assertEqual(list(seq(1, 5, 3)), [1, 6])
        self.assertEqual(list(seq(1, 5, 3, end=False)), [1])
        self.assertEqual(list(seq(3, -1, 1)), [3])
        self.assertEqual(list(seq(3, -1, 1, comp=operator.ge)), [3, 2, 1, 0])
        self.assertEqual(list(seq(3, -1, 1, end=False, comp=operator.ge)), [3, 2, 1])

    def test_kagan_angles(self):
        d = 0.001
        self.assertTrue(
            abs(
                deg(
                    min(
                        kagan_angles(
                            _R_theta_phi(rad(30), rad(20)),
                            _R_theta_phi(rad(30 + d), rad(20 + d)),
                        )
                    )
                    - d * sqrt(2)
                )
                <= d * 1e-3
            )
        )

    def test_transpose(self):
        A = ((1, 2), (3, 4))
        self.assertEqual(transpose(A), [[1, 3], [2, 4]])
        A = ((1, 2, 3), (4, 5, 6))
        self.assertEqual(transpose(A), [[1, 4], [2, 5], [3, 6]])

    def test_dot(self):
        A = ((1, 2), (3, 4))
        B = [[5, 6], (7, 8)]
        self.assertEqual(dot(A, B), [[19, 22], [43, 50]])
        A = ([1], [2])
        B = [(3, 4)]
        self.assertEqual(dot(A, B), [[3, 4], [6, 8]])

    def test_binning(self):
        bins = 10
        dx, bs = binning([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], bins)
        self.assertAlmostEqual(dx, 1)
        b0 = bs[0]
        self.assertAlmostEqual(b0[0], 0)
        self.assertAlmostEqual(b0[1], 1)
        self.assertAlmostEqual(b0[2], 1.5)
        self.assertAlmostEqual(b0[3], 1.5 / 11)
        bbins = bs[-1]
        self.assertAlmostEqual(bbins[0], 9)
        self.assertAlmostEqual(bbins[1], 10)
        self.assertAlmostEqual(bbins[2], 1.5)
        self.assertAlmostEqual(bbins[3], 1.5 / 11)
        for i, b in enumerate(bs[1 : bins - 1]):
            self.assertAlmostEqual(b[0], i + 1)
            self.assertAlmostEqual(b[1], i + 2)
            self.assertAlmostEqual(b[2], 1)
            self.assertAlmostEqual(b[3], 1 / 11)

        r = -1.5
        s = 6.5
        dx, bs = binning([0, 1, 2, 3, 4, 5], 8, r, s)
        self.assertAlmostEqual(dx, (s - r) / 8)
        x1, x2, n, np = bs[0]
        self.assertAlmostEqual(x1, r)
        self.assertAlmostEqual(x2, r + 1)
        self.assertAlmostEqual(n, 0)
        self.assertAlmostEqual(np, 0)
        x1, x2, n, np = bs[-1]
        self.assertAlmostEqual(x1, s - 1)
        self.assertAlmostEqual(x2, s)
        self.assertAlmostEqual(n, 0)
        self.assertAlmostEqual(np, 0)
        for i, (x1, x2, n, np) in enumerate(bs[1:-1]):
            self.assertAlmostEqual(x1, r + i + 1)
            self.assertAlmostEqual(x2, r + i + 2)
            self.assertAlmostEqual(n, 1)
            self.assertAlmostEqual(np, 1 / 6)

    def test_linspace(self):
        for x, y in zip(linspace(0, 10, 11), list(range(11))):
            self.assertAlmostEqual(x, y)

    def test_sphere_mesh(self):
        triangles, points = sphere_mesh(n=2, base=4)
        self.assertEqual(len(triangles), 4 ** 3)
        self.assertEqual(len(points), 4 ** 3)

    def test__divide_triangle(self):
        points = [(0, 0, 1), (1, 0, 0), (0, 1, 0)]
        triangles = _divide_triangle((0, 1, 2), points)
        self.assertEqual(triangles, ((0, 3, 5), (1, 3, 4), (2, 4, 5), (3, 4, 5)))
        self.assertEqual(
            points,
            [
                (0, 0, 1),
                (1, 0, 0),
                (0, 1, 0),
                (0.7071067811865475, 0.0, 0.7071067811865475),
                (0.7071067811865475, 0.7071067811865475, 0.0),
                (0.0, 0.7071067811865475, 0.7071067811865475),
            ],
        )

    def test_is_in_polygon(self):
        with self.assertRaises(AssertionError):
            is_in_polygon(1, 2, [1, 2], [1, 2])
        with self.assertRaises(AssertionError):
            is_in_polygon(1, 2, [1, 2, 3], [1, 2, 3, 4])
        self.assertTrue(is_in_polygon(1, 2, [0, 2, 2, 0], [0, 0, 3, 3]))
        self.assertFalse(is_in_polygon(1, 2, [0, 2, 2, 0], [0, 0, 1, 1]))
        self.assertTrue(is_in_polygon(1, 0, [0, 2, 2, 0], [0, 0, 2, 2]))
        self.assertTrue(is_in_polygon(2, 1, [0, 2, 2, 0], [0, 0, 2, 2]))
        self.assertTrue(is_in_polygon(1, 2, [0, 2, 2, 0], [0, 0, 2, 2]))
        self.assertTrue(is_in_polygon(0, 1, [0, 2, 2, 0], [0, 0, 2, 2]))
        self.assertFalse(
            is_in_polygon(
                135.9675,
                35.5805,
                [130.5, 131, 131.6, 131.5, 130.3],
                [32.3, 32.6, 33.4, 33.5, 32.8],
            )
        )

    def test_is_in_convex_polygon(self):
        with self.assertRaises(AssertionError):
            is_in_convex_polygon(1, 2, [(0, 0), (1, 0), (1, -1)])
        self.assertTrue(is_in_convex_polygon(0, 0, [(0, 0), (1, 0), (1, 1)]))
        xys = [(0, 0), (2, 0), (2, 1), (2, 2), (1, 2)]
        self.assertTrue(is_in_convex_polygon(1, 1, xys))
        self.assertTrue(is_in_convex_polygon(1, 1, list(reversed(xys)), False))
        self.assertFalse(is_in_convex_polygon(3, 3, xys))

    def test_is_convex(self):
        with self.assertRaises(AssertionError):
            is_convex([])
        with self.assertRaises(AssertionError):
            is_convex([(1, 2)])
        with self.assertRaises(AssertionError):
            is_convex([(1, 2), (3, 4)])
        self.assertTrue(is_convex([(0, 0), (1, 0), (0.5, 1)]))
        self.assertTrue(is_convex([(0, 0), (1, 0), (1, 1), (1, 2), (0, 1)]))
        self.assertFalse(is_convex([(0, 0), (1, 0), (0.5, 1), (0, 5)]))
        self.assertFalse(is_convex([(0, 0), (0.5, 1), (1, 0)]))
        self.assertTrue(is_convex([(0, 0), (0.5, 1), (1, 0)], False))

    def test_each_cons(self):
        with self.assertRaises(AssertionError):
            each_cons([1, 2, 3], 0)
        with self.assertRaises(AssertionError):
            each_cons(map(int, [1, 2, 3]), 0)

        for xs, n, expected in (
            ([], 1, [],),
            ([1, 2, 3], 1, [[1], [2], [3]],),
            ([1, 2, 3], 2, [[1, 2], [2, 3]],),
            ([1, 2, 3], 3, [[1, 2, 3]],),
            ([1, 2, 3], 4, [],),
        ):
            self.assertEqual(each_cons(xs, n), expected)

        for xs, n, expected in (
            ([], 1, [],),
            ([1, 2, 3], 1, [[1], [2], [3]],),
            ([1, 2, 3], 2, [[1, 2], [2, 3]],),
            ([1, 2, 3], 3, [[1, 2, 3]],),
            ([1, 2, 3], 4, [],),
        ):
            self.assertEqual(list(each_cons(map(int, xs), n)), expected)

    def test_parallel_for(self):
        self.assertEqual(
            parallel_for(_fn_for_test_parallel_for, [1, 2], [3, 4, 5]),
            [[(1, 3), (1, 4), (1, 5)], [(2, 3), (2, 4), (2, 5)]],
        )
        self.assertEqual(
            parallel_for(_fn_for_test_parallel_for, [1, 2], [3, 4, 5], chunk_size=3),
            [[(1, 3), (1, 4), (1, 5)], [(2, 3), (2, 4), (2, 5)]],
        )

    def test_reshape(self):
        with self.assertRaises(AssertionError):
            reshape((1,), ())
        with self.assertRaises(AssertionError):
            reshape((1, 2, 3), (2, 2))

        for xs, ns, expected in (
            ([1, 2, 3], (3,), [1, 2, 3]),
            ([1, 2, 3], (3, 1), [[1], [2], [3]]),
            ([1, 2, 3, 4], (2, 2), [[1, 2], [3, 4]]),
            ([1, 2, 3, 4, 5, 6], (2, 3), [[1, 2, 3], [4, 5, 6]]),
            ([1, 2, 3, 4, 5, 6, 7, 8], (2, 2, 2), [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]),
        ):
            self.assertEqual(reshape(xs, ns), expected)

    def test_partition(self):
        with self.assertRaises(ValueError):
            partition((1, 2), 0)

        for xs, n, expected in (
            ((), -1, []),
            ((1, 2), -1, []),
            ((), 1, []),
            ((), 2, []),
            ([1, 3], 1, [[1], [3]]),
            ([1, 4], 2, [[1, 4]]),
            ([1, 5], 3, []),
        ):
            self.assertEqual(partition(xs, n), expected)

    def test__get_interval(self):
        with self.assertRaises(AssertionError):
            _get_interval(-1)
        with self.assertRaises(AssertionError):
            _get_interval(0)

        lx_dx = [
            (1, 0.1),
            (2, 0.2),
            (3, 0.5),
            (4, 0.5),
            (5, 0.5),
            (6, 1),
            (7, 1),
            (8, 1),
            (9, 1),
            (10, 1),
            (11, 2),
            (12, 2),
            (19, 2),
            (20, 2),
            (21, 5),
            (22, 5),
            (49, 5),
            (50, 5),
            (51, 10),
            (52, 10),
            (99, 10),
            (100, 10),
        ]
        for lx, dx in lx_dx:
            self.assertAlmostEqual(_get_interval(lx), dx)

    def test__get_lower_limit(self):
        with self.assertRaises(AssertionError):
            _get_lower_limit(0, 0)
        with self.assertRaises(AssertionError):
            _get_lower_limit(0, -1)

        self.assertAlmostEqual(_get_lower_limit(-10, 3), -12)
        self.assertAlmostEqual(_get_lower_limit(-12, 3), -15)

    def test__get_upper_limit(self):
        with self.assertRaises(AssertionError):
            _get_upper_limit(0, 0)
        with self.assertRaises(AssertionError):
            _get_upper_limit(0, -1)

        self.assertAlmostEqual(_get_upper_limit(-10, 3), -9)
        self.assertAlmostEqual(_get_upper_limit(-12, 3), -9)

    def test_get_tick_configurations(self):
        x1, x2, dx = get_tick_configurations(101.001, 103.0001)
        self.assertAlmostEqual(x1, 100.8)
        self.assertAlmostEqual(x2, 103.2)
        self.assertAlmostEqual(dx, 0.2)

        x1, x2, dx = get_tick_configurations(0, 1)
        self.assertAlmostEqual(x1, -0.1)
        self.assertAlmostEqual(x2, 1.1)
        self.assertAlmostEqual(dx, 0.1)

    def test_list_2d(self):
        self.assertEqual(list_2d(2, 3), [[None, None, None], [None, None, None]])

        self.assertEqual(list_2d(2, 3, 0), [[0, 0, 0], [0, 0, 0]])

    def test_flatten(self):
        self.assertEqual(list(flatten([])), [])
        self.assertEqual(list(flatten([1, 2])), [1, 2])
        self.assertEqual(list(flatten([1, [2, 3]])), [1, 2, 3])
        self.assertEqual(list(flatten(["ab"])), ["ab"])
        self.assertEqual(
            tuple(sorted(flatten((1, 2, (3, [4, set([5, 6]), 7], [8, 9]))))),
            tuple(sorted((1, 2, 3, 4, 5, 6, 7, 8, 9))),
        )

    def test_make_parse_fixed_width(self):
        parse_fixed_width = make_parse_fixed_width(
            (("a", 3, int), ("b", 7, lambda x: -int(x)))
        )
        self.assertEqual(parse_fixed_width(" 325      "), {"a": 32, "b": -5})
        self.assertEqual(parse_fixed_width(" 325      \n"), {"a": 32, "b": -5})
        self.assertEqual(parse_fixed_width(" 32  5    "), {"a": 32, "b": -5})
        self.assertEqual(parse_fixed_width("32   5    abc"), {"a": 32, "b": -5})
        with self.assertRaises(AssertionError):
            parse_fixed_width("123456789")
        parse_fixed_width = make_parse_fixed_width((("a", 1, int), 2, ("b", 3, int),))
        self.assertEqual(parse_fixed_width("123456"), {"a": 1, "b": 456})
        self.assertEqual(parse_fixed_width("1234567"), {"a": 1, "b": 456})
        with self.assertRaises(AssertionError):
            parse_fixed_width("12345")

    def test_AppendDbV1(self):
        with tempfile.TemporaryDirectory() as td:
            with AppendDbV1(jp(td, "l1")) as ad:
                assert len(ad) == 0, len(ad)
                with self.assertRaises(IndexError):
                    ad[0]
                with self.assertRaises(IndexError):
                    ad[-1]
                ad.append("どうだろう？\n")
                with self.assertRaises(IndexError):
                    ad[-2]
                with self.assertRaises(IndexError):
                    ad[1]
                assert len(ad) == 1, len(ad)
                assert ad[0] == "どうだろう？\n", repr(ad[0])
                assert ad[-1] == "どうだろう？\n", repr(ad[-1])
                ad.append("もう1つ\n")
                assert len(ad) == 2, len(ad)
                assert ad[0] == "どうだろう？\n", repr(ad[0])
                assert ad[-1] == "もう1つ\n", repr(ad[-1])
                assert ad[1] == "もう1つ\n", repr(ad[1])
                with self.assertRaises(IndexError):
                    ad[-3]
                with self.assertRaises(IndexError):
                    ad[2]
            with AppendDbV1(jp(td, "l1")) as ad:
                assert len(ad) == 2, len(ad)
                assert ad[1] == "もう1つ\n", repr(ad[1])
                assert ad[0] == "どうだろう？\n", repr(ad[0])
                ad.append("OK??\n")
                assert ad[2] == "OK??\n", repr(ad[2])

    if _PY37:

        def test_dataclass_of(self):
            @dataclasses.dataclass
            class c4:
                x: int
                y: float

            @dataclasses.dataclass
            class c3:
                x: ("yy",)
                y: typing.Mapping[str, typing.Optional[c4]]

            @dataclasses.dataclass
            class c2:
                x: ("xx",)
                y: typing.Dict[str, typing.Optional[c4]]

            @dataclasses.dataclass
            class c1:
                x: typing.List[typing.Union[c2, c3]]
                y: c4
                z: typing.Sequence[int]
                a: typing.Set[str]
                b: typing.Tuple[int, str, float]

            x = c1(
                x=[c2(x="xx", y=dict(a=None, b=c4(x=2, y=1.0))), c3(x="yy", y=dict())],
                y=c4(x=1, y=1.3),
                z=[1],
                a=set(["a"]),
                b=(1, "two", 3.4),
            )
            self.assertEqual(x, dataclass_of(c1, dataclasses.asdict(x)))

    else:

        def test_dataclass_of(self):
            @dataclasses.dataclass
            class c4:
                x: int
                y: float

            @dataclasses.dataclass
            class c3:
                x: typing.Literal["yy"]
                y: typing.Mapping[str, typing.Optional[c4]]

            @dataclasses.dataclass
            class c2:
                x: typing.Literal["xx", "zz"]
                y: typing.Dict[str, typing.Optional[c4]]

            @dataclasses.dataclass
            class c1:
                x: typing.List[typing.Union[c2, c3]]
                y: c4
                z: typing.Sequence[int]
                a: typing.Set[str]
                b: typing.Tuple[int, str, float]

            x = c1(
                x=[c2(x="xx", y=dict(a=None, b=c4(x=2, y=1.0))), c3(x="yy", y=dict())],
                y=c4(x=1, y=1.3),
                z=[1],
                a=set(["a"]),
                b=(1, "two", 3.4),
            )
            self.assertEqual(x, dataclass_of(c1, dataclasses.asdict(x)))


if __name__ == "__main__":
    unittest.main()
