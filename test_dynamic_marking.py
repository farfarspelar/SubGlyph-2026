import ast
import json
import re
import tkinter as tk
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
import subglyph
from dynamic_marking import DynamicMarking, FanucDynamicPost, serial_digits, format_date
from nc_geometry import FrontMarking, MantleMarking, front_marking_blocks, mantle_marking_blocks


class DynamicTests(unittest.TestCase):
    def config(self, **kwargs):
        config = DynamicMarking(kind='Serienummer', **kwargs)
        config.verify()
        return config

    def marking(self):
        return FrontMarking('000001', 0, 0, 0, -.2, 2, 5, 3)

    def test_digits_and_boundaries(self):
        for value in (0, 1, 9, 10, 99, 100, 999999):
            for width in range(len(str(value)), 9):
                self.assertEqual(serial_digits(value, width), list(map(int, str(value).zfill(width))))
                self.assertEqual(serial_digits(value, width, False), list(map(int, str(value))))
        for value in (-1, 1000000, 1.5):
            with self.assertRaises(ValueError):
                serial_digits(value, 6)

    def test_date_formats(self):
        for fmt, expected in [('YYYY-MM-DD', '2026-10-03'), ('YYMMDD', '261003'),
                              ('DDMMYY', '031026'), ('YYYYMMDD', '20261003')]:
            self.assertEqual(format_date('2026-10-03', fmt), expected)
        self.assertEqual(format_date('2024-02-29', 'YYMMDD'), '240229')
        with self.assertRaises(ValueError):
            format_date('2026-02-29', 'YYYYMMDD')

    def test_verification_reset_even_if_changed_back(self):
        config = self.config()
        config.variable = '#522'
        self.assertFalse(config.verified)
        config.variable = '#520'
        self.assertFalse(config.verified)
        config.verify()
        config.position_variable = '#523'
        self.assertFalse(config.verified)

    def test_unverified_and_unsupported_refused(self):
        for controller in ('OKUMA OSP (ISO)', 'SIEMENS SINUMERIK (ISO)'):
            with self.assertRaises(ValueError):
                self.config().validate(controller)
        for config in (DynamicMarking(kind='Serienummer'), DynamicMarking(kind='Maskindatum'),
                       self.config(variable='#3000'), self.config(position_variable='#520')):
            with self.assertRaises(ValueError):
                config.validate('FANUC (ISO)')
        with self.assertRaises(ValueError):
            FanucDynamicPost().blocks(DynamicMarking(kind='Serienummer'), self.marking(), front_marking_blocks, 0)

    def test_glyph_blocks_shared_and_only_selected_variables_written(self):
        lines = FanucDynamicPost().blocks(self.config(), self.marking(), front_marking_blocks, 0)
        for digit in range(10):
            self.assertEqual(lines.count(f'N{1040 + digit}'), 1)
        writes = {re.match(r'(#\d+)=', line)[1] for line in lines if re.match(r'#\d+=', line)}
        self.assertEqual(writes, {'#520', '#521'})
        self.assertEqual(lines.count('#520=#520+1'), 1)
        self.assertNotIn('#520=1', lines)
        self.assertIn('IF [#520 EQ #0] GOTO 1005', lines)
        self.assertIn('IF [#520 GE 1000000] GOTO 1005', lines)

    def test_reused_geometry_matches_full_static_digits(self):
        # Evaluate each selected shared block at its position; compare motion
        # against one full engraving from the existing geometry engine.
        for geometry, marking in [
            (front_marking_blocks, replace(self.marking(), rotation_degrees=31, mirrored=True)),
            (mantle_marking_blocks, MantleMarking('0123456789', 20, -10, 50, 49.8, 52, 5, 3,
                                                'Längs Z-axeln', rotation_degrees=17)),
            (mantle_marking_blocks, MantleMarking('0123456789', 20, -10, 50, 49.8, 52, 5, 3,
                                                'Runt omkretsen', plane='XYZ+C', rotation_degrees=17))]:
            # Runtime capacity limited to eight digits; all ten glyphs tested
            # over two markings, with arc/stroke order compared per glyph.
            for text in ('01234567', '89'):
                count = len(text)
                config = self.config(digits=count)
                lines = FanucDynamicPost().blocks(config, marking, geometry, 0)
                for pos, digit in enumerate(text):
                    begin = lines.index(f'N{1040 + int(digit)}') + 1
                    end = lines.index('GOTO 1003', begin)
                    actual = lines[begin:end]
                    pitch = marking.width + marking.character_spacing
                    expected = geometry(replace(marking, text=digit,
                        horizontal_offset=pitch * (pos - (count-1)/2),
                        layout_width=count*marking.width+(count-1)*marking.character_spacing))[1:]
                    for a, b in zip(actual, expected):
                        def evaluate(m):
                            return str(eval(m[1].replace('#521', str(pos)), {'__builtins__': {}}))
                        a = re.sub(r'\[([^]]+)\]', evaluate, a)
                        self.assertEqual(re.findall(r'[A-Z]', a), re.findall(r'[A-Z]', b))
                        for x, y in zip(re.findall(r'-?\d+(?:\.\d*)?', a), re.findall(r'-?\d+(?:\.\d*)?', b)):
                            self.assertAlmostEqual(float(x), float(y), delta=.0011)

    def test_macro_execution_selects_digits_and_increments_once(self):
        def run(value, count, zeros):
            config = self.config(digits=count, leading_zeros=zeros)
            lines = FanucDynamicPost().blocks(config, self.marking(), front_marking_blocks, 0)
            labels = {int(line[1:]): i for i, line in enumerate(lines) if re.fullmatch(r'N\d+', line)}
            variables = {'#520': value, '#521': 0, '#0': None}
            selected = []
            pc = 0
            def expression(text):
                text = re.sub(r'#\d+', lambda m: repr(variables[m[0]]), text)
                for operator, python in [(' EQ ', ' == '), (' NE ', ' != '), (' LT ', ' < '),
                                         (' GE ', ' >= '), (' GT ', ' > '), (' LE ', ' <= ')]:
                    text = text.replace(operator, python)
                text = text.replace('FIX[', 'int(').replace('[', '(').replace(']', ')')
                return eval(text, {'__builtins__': {}, 'int': int})
            for _ in range(3000):
                if pc == len(lines):
                    return selected, variables['#520'], False
                line = lines[pc]
                if line == 'M0':
                    return selected, variables['#520'], True
                if re.fullmatch(r'N10[4][0-9]', line):
                    selected.append(int(line[-1]))
                match = re.fullmatch(r'IF (.+) GOTO (\d+)', line)
                if match and expression(match[1]):
                    pc = labels[int(match[2])]
                    continue
                if line.startswith('GOTO '):
                    pc = labels[int(line[5:])]
                    continue
                if re.match(r'#\d+=', line):
                    variable, rhs = line.split('=', 1)
                    variables[variable] = expression(rhs)
                pc += 1
            self.fail('Macro did not terminate')
        for value in (0, 1, 9, 10, 99, 100, 999999):
            for zeros in (False, True):
                digits, next_value, stopped = run(value, 6, zeros)
                self.assertEqual(digits, serial_digits(value, 6, zeros))
                self.assertEqual(next_value, value + 1)
                self.assertFalse(stopped)
        for value in (None, -1, 1.5, 1000000):
            digits, next_value, stopped = run(value, 6, True)
            self.assertEqual(digits, [])
            self.assertEqual(next_value, value)
            self.assertTrue(stopped)

    def fake_app(self):
        # Real Tcl variables exercise JSON and load paths without a display.
        root = tk.Tcl()
        app = SimpleNamespace()
        tree = ast.parse(Path(subglyph.__file__).read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SubGlyphApp')
        init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
        for node in init.body:
            if isinstance(node, ast.Assign) and ('tk.StringVar(' in ast.unparse(node.value) or 'tk.BooleanVar(' in ast.unparse(node.value)):
                source = ast.unparse(node).replace('tk.StringVar(', 'tk.StringVar(master=root, ').replace('tk.BooleanVar(', 'tk.BooleanVar(master=root, ')
                exec(source, {'tk': tk, 'root': root, 'self': app, 'MARKING_ROW_COUNT': subglyph.MARKING_ROW_COUNT,
                              **vars(subglyph)})
        app.dynamic_markings = [DynamicMarking() for _ in range(subglyph.MARKING_ROW_COUNT)]
        app._update_configuration = app._update_program_mode = app._update_font_mode = lambda: None
        app._update_permissions = lambda: None
        app.access_control = Mock()
        return app

    def test_sg_roundtrip_and_legacy(self):
        app = self.fake_app()
        app.dynamic_markings[0] = self.config(digits=4, leading_zeros=False, start=9)
        app.markings[0].set('9')
        payload = json.loads(json.dumps(subglyph.SubGlyphApp._project_data(app)))
        self.assertEqual(payload['format_version'], 2)
        self.assertNotIn('verified_variables', payload['dynamic_markings'][0])
        target = self.fake_app()
        subglyph.SubGlyphApp._apply_project_data(target, payload)
        self.assertEqual(target.dynamic_markings[0].to_dict(), app.dynamic_markings[0].to_dict())
        self.assertFalse(target.dynamic_markings[0].verified)
        del payload['dynamic_markings']
        subglyph.SubGlyphApp._apply_project_data(target, payload)
        self.assertTrue(all(c.kind == 'Statisk text' for c in target.dynamic_markings))

    def test_warning_runs_each_generation_and_cancel_prevents_body(self):
        config = self.config()
        app = SimpleNamespace(record_activity=lambda *a: None, _validate_geometry=lambda: None,
                              _dynamic_safety=lambda: [config], _confirm_dynamic=lambda c: False)
        with patch.object(subglyph.SubGlyphApp, '_confirm_dynamic', return_value=False) as warning:
            app._confirm_dynamic = lambda c: subglyph.SubGlyphApp._confirm_dynamic(app, c)
            subglyph.SubGlyphApp.generate_nc(app)
            subglyph.SubGlyphApp.generate_nc(app)
            self.assertEqual(warning.call_count, 2)

    def test_app_builds_dynamic_and_static_with_same_geometry_path(self):
        app = self.fake_app()
        app.markings[0].set('000001')
        app._selected_font_path = lambda: None
        app._row_blocks = lambda index, marking: subglyph.SubGlyphApp._row_blocks(app, index, marking)
        app._build_front_nc_body = lambda indices: subglyph.SubGlyphApp._build_front_nc_body(app, indices)
        for surface in ('Runt en axel', 'Frontplan'):
            app.surface.set(surface)
            app.dynamic_markings[0] = DynamicMarking()
            static = subglyph.SubGlyphApp._build_nc_body(app, [0])
            self.assertNotIn('#520=#520+1', static)
            app.dynamic_markings[0] = self.config()
            dynamic = subglyph.SubGlyphApp._build_nc_body(app, [0])
            self.assertIn('#520=#520+1', dynamic)
            app.dynamic_markings[0].variable = '#522'
            with self.assertRaises(ValueError):
                subglyph.SubGlyphApp._build_nc_body(app, [0])

    def test_warning_header_and_static_path(self):
        app = self.fake_app()
        app._dynamic_safety = lambda: subglyph.SubGlyphApp._dynamic_safety(app)
        self.assertEqual(subglyph.SubGlyphApp._build_nc_header(app), [])
        app.dynamic_markings[0] = self.config()
        header = subglyph.SubGlyphApp._build_nc_header(app)
        self.assertIn('MASKINSPECIFIK', header[0])
        self.assertIn('#520', header[2])
        app.dynamic_markings[0] = DynamicMarking()
        self.assertEqual(subglyph.SubGlyphApp._row_blocks(app, 0, self.marking()), front_marking_blocks(self.marking()))

if __name__ == '__main__':
    unittest.main()
