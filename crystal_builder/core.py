"""Dependency-free Wyckoff expansion. Distances are in angstroms."""
import ast
import csv
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import product
from pathlib import Path

ELEMENTS = "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og".split()
CENTRING = {
    'P': [(0, 0, 0)], 'A': [(0, 0, 0), (0, .5, .5)],
    'B': [(0, 0, 0), (.5, 0, .5)], 'C': [(0, 0, 0), (.5, .5, 0)],
    'I': [(0, 0, 0), (.5, .5, .5)],
    'F': [(0, 0, 0), (0, .5, .5), (.5, 0, .5), (.5, .5, 0)],
    'R': [(0, 0, 0), (2/3, 1/3, 1/3), (1/3, 2/3, 2/3)],
}


@dataclass
class Position:
    multiplicity: int
    letter: str
    symmetry: str
    expressions: list = field(default_factory=list)

    @property
    def label(self):
        return f'{self.multiplicity}{self.letter}'

    @property
    def variables(self):
        return sorted(set(re.findall('[xyz]', ' '.join(self.expressions))))


@dataclass
class Setting:
    serial: int
    number: int
    choice: str
    symbol: str
    hall: str
    centring: str
    positions: dict = field(default_factory=dict)

    @property
    def translations(self):
        return CENTRING['P' if self.centring == 'R' and self.choice == 'R' else self.centring]


@lru_cache(maxsize=1)
def database():
    root = Path(__file__).parent / 'data'
    if not root.exists():
        root = Path(__file__).resolve().parent.parent / 'Database_of_crystal_symmetry'
    settings = {}
    with (root / 'space_group.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in list(csv.reader(stream))[1:]:
            if not row or not row[0].strip().isdigit():
                continue
            serial = int(row[0])
            settings[serial] = Setting(serial, int(row[4]), row[2].strip(),
                                       row[7].strip(), row[6].strip(), row[10].strip())
    current = position = None
    with (root / 'Wyckoff.csv').open(encoding='utf-8-sig') as stream:
        for line in stream:
            if line.strip() == 'end of data':
                break
            fields = line.rstrip().split(':')
            if fields[0].isdigit():
                current = settings[int(fields[0])]
                position = None
            elif len(fields) >= 6:
                if fields[2].isdigit():
                    position = Position(int(fields[2]), fields[3], fields[4])
                    current.positions[position.letter] = position
                expressions = re.findall(r'\(([^()]*)\)', line)
                if position is not None:
                    position.expressions.extend(expressions)
    if len(settings) != 530 or {s.number for s in settings.values()} != set(range(1, 231)):
        raise ValueError('Incomplete symmetry database')
    return settings


def get_setting(number, serial=None):
    if serial is not None:
        setting = database().get(int(serial))
        if setting is None or setting.number != int(number):
            raise ValueError('Setting does not belong to the selected space group')
        return setting
    for setting in database().values():
        if setting.number == int(number):
            return setting
    raise ValueError('Space group must be 1..230')


@lru_cache(maxsize=4096)
def _expression(text):
    return ast.parse(re.sub(r'(\d)([xyz])', r'\1*\2', text.strip()), mode='eval').body


def evaluate(text, xyz=(0, 0, 0)):
    """Evaluate only numeric arithmetic and x/y/z; never execute Python input."""
    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.Name) and node.id in ('x', 'y', 'z'):
            return xyz['xyz'.index(node.id)]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        if isinstance(node, ast.BinOp):
            a, b = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): return a + b
            if isinstance(node.op, ast.Sub): return a - b
            if isinstance(node.op, ast.Mult): return a * b
            if isinstance(node.op, ast.Div): return a / b
        raise ValueError(f'Unsupported coordinate expression: {text}')
    try:
        result = float(visit(_expression(text)))
    except (SyntaxError, ZeroDivisionError, OverflowError) as error:
        raise ValueError(f'Invalid coordinate: {text}') from error
    if not math.isfinite(result):
        raise ValueError('Coordinates must be finite')
    return result


def wrap(point):
    return tuple(round(v % 1.0, 8) % 1.0 for v in point)


def expand_position(setting, label, xyz=(0, 0, 0), strict=True):
    match = re.fullmatch(r'(\d*)([a-zA-Z])', label.strip())
    if not match or match[2] not in setting.positions:
        raise ValueError(f'Unknown Wyckoff position {label} for {setting.symbol}')
    position = setting.positions[match[2]]
    if match[1] and int(match[1]) != position.multiplicity:
        raise ValueError(f'Expected {position.label}, not {label}')
    coordinates = set()
    for expression in position.expressions:
        point = tuple(evaluate(part, xyz) for part in expression.split(','))
        for translation in setting.translations:
            coordinates.add(wrap([a + b for a, b in zip(point, translation)]))
    if strict and len(coordinates) != position.multiplicity:
        raise ValueError(f'{position.label}: generated {len(coordinates)} positions; expected '
                         f'{position.multiplicity}. Coordinates may lie on a special position, '
                         'or the source database may be inconsistent.')
    return sorted(coordinates)


def lattice_vectors(cell):
    a, b, c, alpha, beta, gamma = map(float, cell)
    if not all(math.isfinite(v) for v in (a, b, c, alpha, beta, gamma)):
        raise ValueError('Cell parameters must be finite')
    if min(a, b, c) <= 0 or not all(0 < v < 180 for v in (alpha, beta, gamma)):
        raise ValueError('Cell lengths must be positive; angles must be between 0 and 180')
    ca, cb, cg = [math.cos(math.radians(v)) for v in (alpha, beta, gamma)]
    sg = math.sin(math.radians(gamma))
    cy = (ca - cb * cg) / sg
    cz2 = 1 - cb * cb - cy * cy
    if cz2 <= 1e-12:
        raise ValueError('Cell angles produce zero or imaginary volume')
    return ((a, 0, 0), (b*cg, b*sg, 0), (c*cb, c*cy, c*math.sqrt(cz2)))


def cartesian(fractional, vectors):
    return tuple(sum(fractional[i] * vectors[i][j] for i in range(3)) for j in range(3))


def validate_metric(setting, vectors):
    """Test the lattice metric against the general-position rotation matrices."""
    metric = [[sum(a*b for a, b in zip(u, v)) for v in vectors] for u in vectors]
    tolerance = max(metric[i][i] for i in range(3)) * 1e-5
    general = next(iter(setting.positions.values()))
    for expr in general.expressions:
        parts = expr.split(',')
        zero = [evaluate(p) for p in parts]
        rotation = [[evaluate(p, tuple(int(k == j) for k in range(3))) - zero[i]
                     for j in range(3)] for i, p in enumerate(parts)]
        for i, j in product(range(3), repeat=2):
            transformed = sum(rotation[k][i]*metric[k][l]*rotation[l][j]
                              for k, l in product(range(3), repeat=2))
            if abs(transformed - metric[i][j]) > tolerance:
                raise ValueError('Lattice lengths/angles are incompatible with this space-group setting')


def generate(config):
    setting = get_setting(config['space_group'], config.get('setting'))
    vectors = lattice_vectors(config['cell'])
    validate_metric(setting, vectors)
    repeats = config.get('repeats', [1, 1, 1])
    if len(repeats) != 3 or any(type(n) is not int or not 1 <= n <= 20 for n in repeats):
        raise ValueError('Repeats must be three integers in 1..20')
    sites = config.get('sites', [])
    if not sites:
        raise ValueError('Add at least one atomic site')
    unit, occupied = [], set()
    for index, site in enumerate(sites):
        element = site['element'].strip().capitalize()
        if element not in ELEMENTS:
            raise ValueError(f'Unknown element: {element}')
        xyz = site.get('xyz', [0, 0, 0])
        if len(xyz) != 3:
            raise ValueError('Provide x, y and z')
        xyz = tuple(evaluate(str(v)) for v in xyz)
        for point in expand_position(setting, site['wyckoff'], xyz):
            if point in occupied:
                raise ValueError(f'Site {index+1} overlaps an earlier site at {point}')
            occupied.add(point)
            unit.append((element, point, index))
    boundary = bool(config.get('boundary', True))
    estimate = len(unit) * math.prod(n + int(boundary) for n in repeats)
    if estimate > 30000:
        raise ValueError('Structure is too large (conservative limit: 30,000 displayed atoms)')
    atoms = []
    for element, point, index in unit:
        ranges = [range(n + int(boundary and abs(p) < 1e-8)) for p, n in zip(point, repeats)]
        for offset in product(*ranges):
            fractional = tuple(p + t for p, t in zip(point, offset))
            atoms.append({'element': element, 'fractional': fractional,
                          'position': cartesian(fractional, vectors), 'site': index})
    return {'setting': setting, 'vectors': vectors, 'atoms': atoms,
            'unit_count': len(unit), 'repeats': repeats}
