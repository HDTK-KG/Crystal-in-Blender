import math
import unittest
from crystal_builder.core import database, evaluate, expand_position, generate, get_setting, lattice_vectors
from crystal_builder.presets import PRESETS


class CrystalTests(unittest.TestCase):
    def test_every_multiplicity(self):
        self.assertEqual(len(database()), 530)
        self.assertEqual({s.number for s in database().values()}, set(range(1, 231)))
        for setting in database().values():
            for position in setting.positions.values():
                with self.subTest(setting=setting.serial, position=position.label):
                    points = expand_position(setting, position.label, (.137123, .271839, .389173))
                    self.assertEqual(len(points), position.multiplicity)
                    self.assertTrue(all(0 <= v < 1 for point in points for v in point))

    def test_known_structures(self):
        for name, count in [('NACL', 8), ('DIAMOND', 8), ('BCC', 2), ('RUTILE', 6)]:
            self.assertEqual(generate(PRESETS[name])['unit_count'], count)
        nacl = generate({**PRESETS['NACL'], 'boundary': False})
        self.assertEqual({a['fractional'] for a in nacl['atoms'] if a['element'] == 'Na'},
                         {(0, 0, 0), (0, .5, .5), (.5, 0, .5), (.5, .5, 0)})
        points = [a['position'] for a in generate({**PRESETS['DIAMOND'], 'boundary': False})['atoms']]
        nearest = min(math.dist(a, b) for i, a in enumerate(points) for b in points[i+1:])
        self.assertAlmostEqual(nearest, 3.567*math.sqrt(3)/4)

    def test_supercell(self):
        self.assertEqual(len(generate({**PRESETS['NACL'], 'repeats': [2, 3, 1], 'boundary': False})['atoms']), 48)
        self.assertEqual(len(generate(PRESETS['NACL'])['atoms']), 27)

    def test_rhombohedral(self):
        self.assertEqual(len(expand_position(get_setting(146, 433), '3a', (.2, .3, .4))), 3)
        self.assertEqual(len(expand_position(get_setting(146, 434), '1a', (.2, .3, .4))), 1)

    def test_parser(self):
        self.assertAlmostEqual(evaluate('1/3'), 1/3)
        self.assertAlmostEqual(evaluate('-2x+1/2', (.1, 0, 0)), .3)
        for text in ['__import__("os")', 'x.__class__', '1/0', '1e309', '[1][0]', '2**1000']:
            with self.subTest(text=text), self.assertRaises(ValueError): evaluate(text)

    def test_invalid_structures(self):
        for override in [
            {'cell': [5, 6, 5, 90, 90, 90]}, {'repeats': [0, 1, 1]}, {'setting': 1}, {'sites': []},
            {'sites': [{'element': 'Xx', 'wyckoff': '4a'}]},
            {'sites': [{'element': 'Na', 'wyckoff': '8a'}]},
            {'sites': [{'element': 'Na', 'wyckoff': '4a'}, {'element': 'Cl', 'wyckoff': '4a'}]},
            {'sites': [{'element': 'Na', 'wyckoff': '192l', 'xyz': [0, 0, 0]}]},
        ]:
            with self.subTest(override=override), self.assertRaises(ValueError):
                generate({**PRESETS['NACL'], **override})

    def test_lattice(self):
        vectors = lattice_vectors([3, 3, 5, 90, 90, 120])
        self.assertAlmostEqual(vectors[1][0], -1.5)
        self.assertAlmostEqual(vectors[1][1], 3*math.sqrt(3)/2)
        for cell in [[0, 1, 1, 90, 90, 90], [1, 1, 1, 10, 10, 170]]:
            with self.assertRaises(ValueError): lattice_vectors(cell)


if __name__ == '__main__':
    unittest.main()
