import math
import re
import unittest
import tempfile
from dataclasses import replace

from decimal import Decimal
from datetime import datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import patch

from subglyph import (
    calculate_diameter_levels,
    create_nc_collection,
    create_email_draft,
    create_fanuc_files,
    create_siemens_files,
    create_nc_program,
    format_nc_number,
    front_text_point,
    flat_stock_surface_dimension,
    group_program_indices,
    load_directory_history,
    parse_coordinate,
    rotate_front_position,
    save_directory_history,
)
import subglyph
from nc_geometry import (
    FrontMarking,
    MantleMarking,
    front_marking_blocks,
    mantle_marking_blocks,
    nc_number,
)
from vector_font import text_arcs, text_strokes
from system_font import outline_text_strokes, system_fonts


class CreateNcProgramTests(unittest.TestCase):
    def test_okuma_rotary_orientation_reflects_about_selected_index_only(self) -> None:
        base = MantleMarking(
            text="OILQUICK", c_degrees=0, z=-8.5, diameter=54.42,
            engraving_diameter=54.32, clearance_diameter=56.42,
            height=4.5, width=3, orientation="Runt omkretsen",
            turret="Upper", z_direction="Z-", plunge_feed=300, engraving_feed=800,
        )
        axis = re.compile(r" C(-?[\d.]+)")
        for index in (0, 90, -60):
            for mirrored in (False, True):
                for orientation in ("Runt omkretsen", "Längs Z-axeln"):
                    with self.subTest(index=index, mirrored=mirrored, orientation=orientation):
                        marking = replace(base, c_degrees=index, mirrored=mirrored, orientation=orientation)
                        before = mantle_marking_blocks(marking)
                        after = subglyph.posted_mantle_marking_blocks(marking, "Okuma")
                        self.assertEqual(len(before), len(after))
                        for old, new in zip(before, after):
                            self.assertEqual(axis.sub("", old), axis.sub("", new))
                            a, b = axis.search(old), axis.search(new)
                            if a:
                                # Existing Upper/Z- indexing is -index.
                                self.assertEqual(Decimal(a.group(1)) + Decimal(b.group(1)), -2 * index)
                        content = create_nc_program("8451", body_lines=after, control_system="Okuma")
                        self.assertIn("G94\n", content)
                        self.assertIn("M15", content)
                        self.assertIn("M16", content)

    def test_okuma_rotary_fix_does_not_change_fanuc_or_siemens_geometry(self) -> None:
        for plane in ("XZ+C", "XYZ+C"):
            marking = MantleMarking(
                text="OILQUICK", c_degrees=60, z=-12, diameter=26.9,
                engraving_diameter=26.8, clearance_diameter=28.9,
                height=3, width=1.5, orientation="Längs Z-axeln",
                turret="Upper", z_direction="Z-", plane=plane,
                rotation_degrees=180, character_spacing=0.3,
            )
            original = mantle_marking_blocks(marking)
            for controller in ("Fanuc", subglyph.FANUC_ISO, subglyph.SIEMENS_SINUMERIK_ISO):
                self.assertEqual(subglyph.posted_mantle_marking_blocks(marking, controller), original)

    def test_okuma_xyz_uses_radius_for_all_x_levels_and_continuous_circle(self) -> None:
        marking = MantleMarking(
            text="O", c_degrees=90, z=-12, diameter=40,
            engraving_diameter=39.8, clearance_diameter=42,
            rotation_clearance_diameter=60, height=1, width=1,
            orientation="Längs Z-axeln", plane="XYZ+C",
            plunge_feed=100, engraving_feed=300,
        )
        lines = subglyph.posted_mantle_marking_blocks(marking, "Okuma")
        self.assertEqual(lines[0], "G19")
        self.assertIn("G0 X30.", lines)
        self.assertIn("G0 X21.", lines)
        self.assertEqual(lines.count("G1 X19.9F100"), 1)
        arcs = [line for line in lines if re.match(r"^G[23] ", line)]
        self.assertEqual(len(arcs), 2)
        self.assertEqual(lines.index(arcs[1]), lines.index(arcs[0]) + 1)
        self.assertEqual(lines[-1], "G0 X21.")
        for line in arcs:
            offsets = {axis: float(value) for axis, value in
                       re.findall(r"([JK])(-?[\d.]+)", line)}
            self.assertAlmostEqual(math.hypot(offsets["J"], offsets["K"]), 0.5, places=3)
        # The diameter input continues to describe the physical stock.
        self.assertEqual(marking.engraving_diameter, 39.8)

    def test_okuma_arc_direction_and_small_ellipse(self) -> None:
        for mirrored in (False, True):
            for turret in ("Upper", "Lower"):
                for z_direction in ("Z+", "Z-"):
                    marking = MantleMarking(
                        text="O O", c_degrees=0, z=-10, diameter=20,
                        engraving_diameter=19.8, clearance_diameter=22,
                        height=0.8, width=0.5, orientation="Längs Z-axeln",
                        plane="XYZ+C", mirrored=mirrored, turret=turret,
                        z_direction=z_direction, rotation_degrees=37,
                    )
                    original = mantle_marking_blocks(marking)
                    posted = subglyph.posted_mantle_marking_blocks(marking, "Okuma")
                    original_arcs = [x for x in original if re.match(r"^G[23] ", x)]
                    posted_arcs = [x for x in posted if re.match(r"^G[23] ", x)]
                    self.assertEqual(posted_arcs, original_arcs)
                    self.assertEqual(posted.count("G1 X9.9"), 2)
                    self.assertEqual(posted.count("G0 X11."), 2)

    def test_okuma_leaves_y_axis_mode_to_main_program_and_preserves_xzc(self) -> None:
        base = MantleMarking(
            text="O", c_degrees=90, z=-12, diameter=40,
            engraving_diameter=39.8, clearance_diameter=42,
            height=1, width=1, orientation="Längs Z-axeln",
        )
        programs = []
        for index, plane in enumerate(("XZ+C", "XYZ+C"), start=1):
            marking = replace(base, plane=plane)
            lines = subglyph.posted_mantle_marking_blocks(marking, "Okuma")
            if plane == "XZ+C":
                self.assertEqual(lines, mantle_marking_blocks(marking, reverse_rotary_c=True))
            programs.append((str(index), "", lines))
        content = create_nc_collection(programs, control_system="Okuma")
        self.assertNotRegex(content, r"\bG13[68]\b")
        self.assertIn("G19\n", content)

    def test_project_and_nc_directories_are_persisted_separately(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project_directory = root / "projects"
            nc_directory = root / "nc"
            project_directory.mkdir()
            nc_directory.mkdir()
            settings = root / "directory-history.json"
            save_directory_history(
                {"project": str(project_directory), "nc": str(nc_directory)}, settings
            )
            self.assertEqual(
                load_directory_history(settings),
                {"project": str(project_directory), "nc": str(nc_directory)},
            )

    def test_invalid_directory_history_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = Path(temporary) / "directory-history.json"
            settings.write_text("not json", encoding="utf-8")
            self.assertEqual(load_directory_history(settings), {})

    def test_system_font_generates_closed_outline_strokes(self) -> None:
        fonts = system_fonts()
        if not fonts:
            self.skipTest("No system TrueType/OpenType fonts installed")
        font_path = next(iter(fonts.values()))
        strokes = outline_text_strokes("O", 5.0, 3.0, font_path)
        self.assertGreaterEqual(len(strokes), 2)
        self.assertTrue(all(stroke[0] == stroke[-1] for stroke in strokes))
        self.assertTrue(all(-1.6 <= x <= 1.6 and -2.6 <= y <= 2.6
                            for stroke in strokes for x, y in stroke))

    def test_system_font_nc_uses_contours_without_standard_font_arcs(self) -> None:
        fonts = system_fonts()
        if not fonts:
            self.skipTest("No system TrueType/OpenType fonts installed")
        blocks = front_marking_blocks(FrontMarking(
            text="O", x=0, y=0, c_degrees=0, engraving_z=-0.2,
            clearance_z=2, height=5, width=3,
            font_path=next(iter(fonts.values())),
        ))
        self.assertTrue(any(block.startswith("G1 X") for block in blocks))
        self.assertFalse(any(block.startswith(("G2 ", "G3 ")) for block in blocks))

    def test_double_quote_has_engraving_strokes_instead_of_fallback_box(self) -> None:
        strokes = text_strokes('"', 5, 3)
        self.assertEqual(len(strokes), 2)
        self.assertTrue(all(len(stroke) == 2 for stroke in strokes))

    def test_mixed_case_oilquick_uses_a_complete_planar_u(self) -> None:
        self.assertEqual(
            text_strokes("Oilquick", 5, 3, use_planar_arcs=True),
            text_strokes("OILQUICK", 5, 3, use_planar_arcs=True),
        )
        strokes = text_strokes("u", 5, 3, use_planar_arcs=True)
        arcs = text_arcs("u", 5, 3)
        self.assertEqual(len(strokes), 1)
        self.assertEqual(strokes[0][0][1], 2.5)
        self.assertEqual(strokes[0][-1][1], 2.5)
        self.assertEqual(min(y for _x, y in strokes[0]), -2.5)
        self.assertEqual(arcs, [])

    def test_character_spacing_changes_distance_without_changing_glyph_width(self) -> None:
        normal = text_strokes("II", 5, 3, spacing=0)
        spaced = text_strokes("II", 5, 3, spacing=2)
        normal_centres = [a[0] for stroke in normal for a, b in zip(stroke, stroke[1:])
                          if a[0] == b[0] and a[1] == 2.5 and b[1] == -2.5]
        spaced_centres = [a[0] for stroke in spaced for a, b in zip(stroke, stroke[1:])
                          if a[0] == b[0] and a[1] == 2.5 and b[1] == -2.5]
        self.assertAlmostEqual(normal_centres[1] - normal_centres[0], 3.0)
        self.assertAlmostEqual(spaced_centres[1] - spaced_centres[0], 5.0)
        for stroke in (*normal, *spaced):
            self.assertEqual(max(x for x, _ in stroke) - min(x for x, _ in stroke), 3)

    def test_i_and_k_have_connected_symmetric_paths_without_extra_cross_lines(self) -> None:
        expected = {
            "I": [((-1.5, 2.5), (0, 2.5)), ((0, 2.5), (1.5, 2.5)),
                  ((0, 2.5), (0, -2.5)), ((-1.5, -2.5), (0, -2.5)),
                  ((0, -2.5), (1.5, -2.5))],
            "K": [((-1.5, 2.5), (-1.5, 0)), ((-1.5, 0), (-1.5, -2.5)),
                  ((-1.5, 0), (1.5, 2.5)), ((-1.5, 0), (1.5, -2.5))],
        }
        for letter, segments in expected.items():
            strokes = text_strokes(letter, 5, 3)
            self.assertEqual(len(strokes), 1)
            actual = {frozenset((a, b)) for a, b in zip(strokes[0], strokes[0][1:])}
            self.assertEqual(actual, {frozenset(segment) for segment in segments})

    def test_i_and_k_stay_at_depth_through_all_junctions(self) -> None:
        for letter in ("I", "K"):
            for plane in ("XZ+C", "XYZ+C"):
                marking = MantleMarking(
                    text=letter, c_degrees=90, z=-8.5, diameter=54.42,
                    engraving_diameter=54.32, clearance_diameter=56.42,
                    height=4.5, width=3, orientation="Runt omkretsen",
                    turret="Upper", z_direction="Z-", plane=plane,
                    plunge_feed=300, engraving_feed=800,
                )
                for controller in ("Okuma", "Fanuc"):
                    body = subglyph.posted_mantle_marking_blocks(marking, controller)
                    content = create_nc_program("8451", body_lines=body, control_system=controller)
                    moves = [line for line in content.splitlines() if line.startswith(("G0 ", "G1 "))]
                    self.assertEqual(sum(line.startswith("G1 X") for line in moves), 1)
                    self.assertEqual(sum(line.startswith("G0 ") for line in moves), 2)
                    self.assertTrue(all(line.startswith("G1 ") for line in moves[1:-1]))

    def test_custom_c_axis_is_used_for_indexing_and_rotary_engraving(self) -> None:
        blocks = mantle_marking_blocks(MantleMarking(
            text="I", c_degrees=60, z=0, diameter=50,
            engraving_diameter=49.5, clearance_diameter=52,
            height=5, width=3, orientation="Radiell", c_axis="CS",
        ))
        self.assertTrue(any(" CS60." in line for line in blocks))
        self.assertFalse(any(" C60." in line for line in blocks))
        self.assertTrue(any(" CS" in line for line in blocks if line.startswith("G1 Z")))

    def test_custom_c_axis_is_used_for_front_indexing(self) -> None:
        blocks = front_marking_blocks(FrontMarking(
            text="I", x=0, y=0, c_degrees=60,
            engraving_z=-0.5, clearance_z=2, height=5, width=3,
            c_axis="CS",
        ))
        self.assertTrue(any(" CS60." in line for line in blocks))

    def test_support_email_draft_contains_recipient_reply_address_and_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attachment = root / "crash.txt"
            attachment.write_text("traceback", encoding="utf-8")
            destination = root / "report.eml"
            with patch.object(subglyph, "timestamped_report_path", return_value=destination):
                result = create_email_draft(
                    "operator@example.com", "SubGlyph bug", "Details", (attachment,)
                )
            message = BytesParser(policy=policy.default).parsebytes(result.read_bytes())
            self.assertEqual(message["To"], "subglyph@gmail.com")
            self.assertEqual(message["Reply-To"], "operator@example.com")
            self.assertEqual(message["X-Unsent"], "1")
            self.assertEqual(
                [part.get_filename() for part in message.iter_attachments()], ["crash.txt"]
            )

    def test_flat_stock_surface_dimension_follows_indexed_face(self) -> None:
        self.assertEqual(flat_stock_surface_dimension("Sexkant", 30, 40, 20, 60), 30)
        self.assertEqual(flat_stock_surface_dimension("Rektangel", 30, 40, 20, 0), 40)
        self.assertEqual(flat_stock_surface_dimension("Rektangel", 30, 40, 20, 90), 20)

    def test_front_text_point_uses_xy_position_for_straight_text(self) -> None:
        self.assertEqual(front_text_point(3, 2, 10, 20, 0, None), (13, 22))

    def test_front_text_point_follows_bending_radius(self) -> None:
        x, y = front_text_point(0, 0, 0, 0, 90, 50)
        self.assertAlmostEqual(x, 0, places=9)
        self.assertAlmostEqual(y, 0, places=9)
        x, y = front_text_point(50 * 3.141592653589793 / 2, 0, 0, 0, 0, 50)
        self.assertAlmostEqual(x, 50, places=9)
        self.assertAlmostEqual(y, 50, places=9)

    def test_bending_does_not_move_front_text_anchor(self) -> None:
        for radius in (10, 25, 50):
            self.assertEqual(front_text_point(0, 0, 12, -8, 37, radius), (12, -8))

    def test_c_indexes_front_position_around_workpiece_centre(self) -> None:
        x, y = rotate_front_position(25, 0, 90)
        self.assertAlmostEqual(x, 0, places=9)
        self.assertAlmostEqual(y, 25, places=9)

    def test_text_rotation_does_not_change_front_anchor(self) -> None:
        for rotation in (0, 45, 180):
            self.assertEqual(front_text_point(0, 0, 8, 3, rotation, 25), (8, 3))

    def test_creates_program_with_comment(self) -> None:
        self.assertEqual(
            create_nc_program("2541", "testprogram", generated_at=datetime(2026, 8, 12, 17, 45, 6)),
            "%\nO2541(testprogram)\n(SKAPAT MED SUBGLYPH VERSION 1.13-test)\n(SKAPAT 2026-08-12 17:45:06)\n\nM99\n%\n",
        )

    def test_accepts_leading_o(self) -> None:
        self.assertEqual(
            create_nc_program("O2541", generated_at=datetime(2026, 8, 12, 17, 45, 6)),
            "%\nO2541\n(SKAPAT MED SUBGLYPH VERSION 1.13-test)\n(SKAPAT 2026-08-12 17:45:06)\n\nM99\n%\n",
        )

    def test_creates_okuma_subprogram_without_percent_delimiters(self) -> None:
        self.assertEqual(
            create_nc_program("2541", "testprogram", control_system="Okuma", generated_at=datetime(2026, 8, 12, 17, 45, 6)),
            "O2541(testprogram)\n(SKAPAT MED SUBGLYPH VERSION 1.13-test)\n(SKAPAT 2026-08-12 17:45:06)\nG94\n\nRTS\n",
        )

    def test_each_okuma_subprogram_overrides_inherited_feed_per_revolution(self) -> None:
        content = create_nc_collection(
            [("8451", "", ["G0 X56.42", "G1 X54.32F300", "G1 Z-7.375 C-32.638F800"]),
             ("8452", "", ["G1 X54.32F300"])],
            control_system="OKUMA OSP (ISO)",
        )
        for section in content.split("RTS")[:-1]:
            feed_mode = "G95"  # The production caller uses feed/revolution.
            feed_moves = 0
            for line in section.splitlines():
                for word in line.split():
                    if word in {"G94", "G95"}:
                        feed_mode = word
                if line.startswith("G1 "):
                    self.assertEqual(feed_mode, "G94")
                    feed_moves += 1
            self.assertGreater(feed_moves, 0)

    def test_creates_siemens_iso_subprogram_with_m17(self) -> None:
        self.assertEqual(
            create_nc_program(
                "2541",
                "testprogram",
                control_system="SIEMENS SINUMERIK (ISO)",
                generated_at=datetime(2026, 8, 12, 17, 45, 6),
            ),
            "%\nO2541(testprogram)\n(SKAPAT MED SUBGLYPH VERSION 1.13-test)\n"
            "(SKAPAT 2026-08-12 17:45:06)\n\nM17\n%\n",
        )

    def test_okuma_first_o_stroke_moves_negative_then_positive_without_full_turns(self) -> None:
        body = [
            "(O C999)", "G0 X56.42 Z-6.25 C-31.059", "G1 X54.32F300",
            "G1 Z-7.375 C-32.638F800", "G1 Z-9.625 C-32.638",
            "G1 Z-10.75 C-31.059", "G1 Z-10.75 C-27.9",
        ]
        content = create_nc_program("8451", body_lines=body, control_system="Okuma")
        self.assertIn("(O C999)", content)
        self.assertIn("G0 X56.42 Z-6.25 C328.941 M15", content)
        self.assertIn("G1 Z-7.375 C327.362F800 M16", content)
        self.assertIn("G1 Z-9.625\n", content)
        self.assertIn("G1 Z-10.75 C328.941 M15", content)
        self.assertIn("G1 Z-10.75 C332.1 M15", content)
        for controller in ("Fanuc", "SIEMENS SINUMERIK (ISO)"):
            other = create_nc_program("8451", body_lines=body, control_system=controller)
            self.assertIn("\n".join(body), other)
            self.assertNotIn("M16", other)

    def test_okuma_direction_preserves_unwrapped_cutting_path_across_zero(self) -> None:
        angles = [Decimal("-0.5"), Decimal("0.5"), Decimal("-0.25"),
                  Decimal("-200"), Decimal("-199.999"), Decimal("0.001")]
        body = [f"{'G0' if index == 0 else 'G1'} Z{-index} C{angle}"
                for index, angle in enumerate(angles)]
        posted = subglyph.okuma_c_direction_blocks(body)
        previous = angles[0] % 360 + 360
        previous %= 360
        for index, line in enumerate(posted[1:], 1):
            target = Decimal(re.search(r"C([\d.]+)", line).group(1))
            self.assertTrue(0 <= target < 360)
            if "M16" in line:
                actual = -((previous - target + 360) % 360)
            else:
                self.assertIn("M15", line)
                actual = (target - previous + 360) % 360
            self.assertEqual(actual, angles[index] - angles[index - 1])
            previous = target

    def test_okuma_short_rapid_custom_axis_and_independent_program_entry(self) -> None:
        body = ["G0 Z0 CS359.", "G0 Z1 CS1.", "G0 Z2 CS359."]
        content = create_nc_collection(
            [("1", "", body), ("2", "", body)], control_system="Okuma", c_axis="CS",
        )
        self.assertEqual(content.count("G0 Z0 CS359. M15"), 2)
        self.assertEqual(content.count("G0 Z1 CS1. M15"), 2)
        self.assertEqual(content.count("G0 Z2 CS359. M16"), 2)

    def test_okuma_does_not_drop_a_full_turn_cut_when_normalizing(self) -> None:
        for target in ("360", "-360", "720"):
            with self.assertRaises(ValueError):
                subglyph.okuma_c_direction_blocks(["G0 C0", f"G1 C{target}"])

    def test_siemens_files_use_spf_extension(self) -> None:
        files = create_siemens_files(
            (("1200", "projekt", ["(RAD 1)"]), ("O1201", "projekt", ["(RAD 2)"]))
        )
        self.assertEqual([filename for filename, _ in files], ["1200.spf", "1201.spf"])
        self.assertTrue(all(content.endswith("M17\n%\n") for _, content in files))

    def test_legacy_controller_names_map_to_current_names(self) -> None:
        self.assertEqual(subglyph.normalize_control_system("Fanuc"), "FANUC (ISO)")
        self.assertEqual(subglyph.normalize_control_system("Okuma"), "OKUMA OSP (ISO)")

    def test_fanuc_collection_contains_multiple_o_programs_in_one_file(self) -> None:
        content = create_nc_collection(
            (("1234", "projekt", ["(RAD 1)"]), ("5678", "projekt", ["(RAD 2)"]))
        )
        self.assertEqual(content.count("%"), 2)
        self.assertIn("O1234(projekt)", content)
        self.assertIn("O5678(projekt)", content)
        self.assertEqual(content.count("M99"), 2)

    def test_okuma_collection_contains_multiple_o_programs_in_one_ssb_content(self) -> None:
        content = create_nc_collection(
            (("1234", "projekt", ["(RAD 1)"]), ("5678", "projekt", ["(RAD 2)"])),
            control_system="Okuma",
        )
        self.assertNotIn("%", content)
        self.assertIn("O1234(projekt)", content)
        self.assertIn("O5678(projekt)", content)
        self.assertEqual(content.count("RTS"), 2)

    def test_equal_program_numbers_group_marking_rows_into_one_program(self) -> None:
        self.assertEqual(
            group_program_indices((("1234", 0), ("O1234", 1), ("5678", 2))),
            [("1234", [0, 1]), ("5678", [2])],
        )

        content = create_nc_collection(
            (("1234", "projekt", ["(RAD 1)", "(RAD 2)"]),)
        )
        self.assertEqual(content.count("O1234"), 1)
        self.assertEqual(content.count("M99"), 1)
        self.assertTrue(content.endswith("M99\n%\n"))

    def test_fanuc_files_use_o_prefixed_program_number_as_filename(self) -> None:
        files = create_fanuc_files(
            (
                ("1200", "projekt", ["(RAD 1)", "(RAD 2)"]),
                ("O1201", "projekt", ["(RAD 3)"]),
            )
        )
        self.assertEqual([filename for filename, _ in files], ["O1200", "O1201"])
        self.assertEqual(files[0][1].count("O1200"), 1)
        self.assertNotIn("O1201", files[0][1])
        self.assertIn("O1201", files[1][1])

    def test_adds_comments_only_for_non_empty_markings(self) -> None:
        self.assertEqual(
            create_nc_program("2541", "jobb", ["ABC", "", "123"], generated_at=datetime(2026, 8, 12, 17, 45, 6)),
            "%\nO2541(jobb)\n(SKAPAT MED SUBGLYPH VERSION 1.13-test)\n(SKAPAT 2026-08-12 17:45:06)\n\n(ABC)\n\n(123)\n\nM99\n%\n",
        )

    def test_rejects_parentheses_in_marking(self) -> None:
        with self.assertRaises(ValueError):
            create_nc_program("2541", markings=["A(B)"])

    def test_rejects_non_numeric_program_number(self) -> None:
        with self.assertRaises(ValueError):
            create_nc_program("25A1")

    def test_rejects_parentheses_in_comment(self) -> None:
        with self.assertRaises(ValueError):
            create_nc_program("2541", "test(program)")

    def test_calculates_engraving_and_clearance_diameters(self) -> None:
        self.assertEqual(
            calculate_diameter_levels("50", "0,5", "2"),
            (Decimal("49.5"), Decimal("52")),
        )

    def test_rejects_depth_larger_than_diameter(self) -> None:
        with self.assertRaises(ValueError):
            calculate_diameter_levels("10", "11", "2")

    def test_formats_nc_number_without_unnecessary_zeroes(self) -> None:
        self.assertEqual(format_nc_number(Decimal("49.500")), "49.5")

    def test_format_nc_number_preserves_integer_zeroes(self) -> None:
        self.assertEqual(format_nc_number(Decimal("150")), "150")
        self.assertEqual(format_nc_number(Decimal("800")), "800")

    def test_signed_z_coordinate_accepts_decimal_comma(self) -> None:
        self.assertEqual(parse_coordinate("-12,5", "Z"), Decimal("-12.5"))

    def test_mantle_nc_uses_clearance_depth_z_and_c(self) -> None:
        blocks = mantle_marking_blocks(
            MantleMarking(
                text="I",
                c_degrees=90,
                z=10,
                diameter=50,
                engraving_diameter=49.5,
                clearance_diameter=52,
                height=5,
                width=3,
                orientation="Axiell",
            )
        )
        self.assertEqual(blocks[0], "(I)")
        self.assertTrue(any(line.startswith("G0 X52. Z") and "C" in line for line in blocks))
        self.assertIn("G1 X49.5", blocks)
        self.assertEqual(blocks[-1], "G0 X52.")

    def test_along_z_position_is_the_inboard_left_text_edge(self) -> None:
        common = dict(
            text="II", c_degrees=0, z=-20, diameter=50,
            engraving_diameter=49.5, clearance_diameter=52,
            height=5, width=3, character_spacing=1,
            orientation="Längs Z-axeln", z_direction="Z-",
        )
        for turret in ("Lower", "Upper"):
            for rotation in (0, 180):
                blocks = mantle_marking_blocks(MantleMarking(
                    **common, turret=turret, rotation_degrees=rotation
                ))
                z_values = [
                    float(token[1:])
                    for line in blocks
                    for token in line.split()
                    if token.startswith("Z")
                ]
                self.assertAlmostEqual(min(z_values), -20.0)
                self.assertTrue(all(value >= -20.0 for value in z_values))

    def test_upper_z_minus_reverses_c_index_to_match_visible_workpiece_side(self) -> None:
        common = dict(
            text="I", c_degrees=60, z=-12, diameter=26.9,
            engraving_diameter=26.8, clearance_diameter=28.9,
            height=3, width=1.5, orientation="Längs Z-axeln",
            plane="XYZ+C",
        )
        upper_z_minus = mantle_marking_blocks(MantleMarking(
            **common, turret="Upper", z_direction="Z-"
        ))
        lower_z_minus = mantle_marking_blocks(MantleMarking(
            **common, turret="Lower", z_direction="Z-"
        ))
        upper_z_plus = mantle_marking_blocks(MantleMarking(
            **common, turret="Upper", z_direction="Z+"
        ))
        self.assertTrue(any(" C-60." in line for line in upper_z_minus))
        self.assertTrue(any(" C60." in line for line in lower_z_minus))
        self.assertTrue(any(" C60." in line for line in upper_z_plus))

    def test_unchecked_mirror_posts_machine_correct_text_direction(self) -> None:
        common = dict(
            text="L",
            c_degrees=0,
            z=0,
            diameter=50,
            engraving_diameter=49.5,
            clearance_diameter=52,
            height=5,
            width=3,
            orientation="Radiell",
        )
        normal = mantle_marking_blocks(MantleMarking(**common, mirrored=False))
        mirrored = mantle_marking_blocks(MantleMarking(**common, mirrored=True))

        normal_c = [line.split(" C", 1)[1] for line in normal if " C" in line]
        mirrored_c = [line.split(" C", 1)[1] for line in mirrored if " C" in line]
        self.assertEqual(
            [float(value) for value in normal_c],
            [-float(value) for value in mirrored_c],
        )

    def test_z_direction_reverses_complete_posted_z_coordinate(self) -> None:
        common = dict(
            text="L", c_degrees=0, z=10, diameter=50,
            engraving_diameter=49.5, clearance_diameter=52,
            height=5, width=3, orientation="Axiell",
        )
        positive = mantle_marking_blocks(MantleMarking(**common, z_direction="Z+"))
        negative = mantle_marking_blocks(MantleMarking(**common, z_direction="Z-"))
        positive_z = [float(line.split(" Z", 1)[1].split()[0]) for line in positive if " Z" in line]
        negative_z = [float(line.split(" Z", 1)[1].split()[0]) for line in negative if " Z" in line]
        self.assertEqual(len(positive_z), len(negative_z))
        for z_plus, z_minus in zip(positive_z, negative_z):
            self.assertAlmostEqual(z_plus, -z_minus)

    def test_upper_turret_automatically_compensates_text_mirroring(self) -> None:
        common = dict(
            text="L", c_degrees=0, z=0, diameter=50,
            engraving_diameter=49.5, clearance_diameter=52,
            height=5, width=3, orientation="Längs Z-axeln", z_direction="Z-",
        )
        lower = mantle_marking_blocks(MantleMarking(**common, turret="Lower"))
        upper = mantle_marking_blocks(MantleMarking(**common, turret="Upper"))
        manually_mirrored = mantle_marking_blocks(
            MantleMarking(**common, turret="Lower", mirrored=True)
        )
        self.assertNotEqual(lower, upper)
        self.assertEqual(upper, manually_mirrored)

    def test_manual_mirror_can_reverse_upper_turret_compensation(self) -> None:
        common = dict(
            text="L", c_degrees=0, z=0, diameter=50,
            engraving_diameter=49.5, clearance_diameter=52,
            height=5, width=3, orientation="Längs Z-axeln", z_direction="Z-",
        )
        lower = mantle_marking_blocks(MantleMarking(**common, turret="Lower"))
        upper_mirrored = mantle_marking_blocks(
            MantleMarking(**common, turret="Upper", mirrored=True)
        )
        self.assertEqual(lower, upper_mirrored)

    def test_new_orientation_names_match_legacy_project_values(self) -> None:
        common = dict(
            text="L",
            c_degrees=15,
            z=-10,
            diameter=50,
            engraving_diameter=49.5,
            clearance_diameter=52,
            height=5,
            width=3,
        )
        for legacy, current in (
            ("Axiell", "Längs Z-axeln"),
            ("Radiell", "Runt omkretsen"),
        ):
            self.assertEqual(
                mantle_marking_blocks(MantleMarking(**common, orientation=legacy)),
                mantle_marking_blocks(MantleMarking(**common, orientation=current)),
            )

    def test_xy_plane_indexes_c_and_engraves_in_z_and_y(self) -> None:
        blocks = mantle_marking_blocks(
            MantleMarking(
                text="I",
                c_degrees=60,
                z=10,
                diameter=50,
                engraving_diameter=49.5,
                clearance_diameter=52,
                height=5,
                width=3,
                orientation="Axiell",
                plane="XY",
                y=7,
            )
        )
        positioning_blocks = [line for line in blocks if line.startswith("G0 X52. Z")]
        engraving_blocks = [line for line in blocks if line.startswith("G1 Z")]
        self.assertTrue(positioning_blocks)
        self.assertTrue(all(" Y" in line and " C60." in line for line in positioning_blocks))
        self.assertTrue(any("Y4.5" in line or "Y9.5" in line for line in positioning_blocks))
        self.assertTrue(engraving_blocks)
        self.assertTrue(all(" Y" in line and " C" not in line for line in engraving_blocks))

    def test_xyz_plane_indexes_c_and_engraves_in_z_and_y(self) -> None:
        blocks = mantle_marking_blocks(
            MantleMarking(
                text="I", c_degrees=120, z=10, y=2, diameter=50,
                engraving_diameter=49.5, clearance_diameter=52,
                height=5, width=3, orientation="Längs Z-axeln", plane="XYZ",
            )
        )
        positioning = [line for line in blocks if line.startswith("G0 X52. Z")]
        engraving = [line for line in blocks if line.startswith("G1 Z")]
        self.assertTrue(all(" C120." in line for line in positioning))
        self.assertTrue(all(" Y" in line and " C" not in line for line in engraving))

    def test_xyz_uses_explicit_arcs_without_setting_g19(self) -> None:
        blocks = mantle_marking_blocks(
            MantleMarking(
                text="O", c_degrees=0, z=0, y=0, diameter=50,
                engraving_diameter=49.5, clearance_diameter=52,
                height=5, width=4, orientation="Längs Z-axeln", plane="XYZ",
            )
        )
        self.assertTrue(any(line.startswith(("G2 ", "G3 ")) for line in blocks))
        self.assertTrue(any(" J" in line and " K" in line for line in blocks))
        self.assertFalse(any("G19" in line for line in blocks))

    def test_planar_u_uses_unambiguous_g1_path(self) -> None:
        blocks = mantle_marking_blocks(
            MantleMarking(
                text="U", c_degrees=0, z=0, y=0, diameter=50,
                engraving_diameter=49.5, clearance_diameter=52,
                height=5, width=3, orientation="Längs Z-axeln", plane="XYZ+C",
                z_direction="Z-",
            )
        )
        self.assertFalse(any(line.startswith(("G2 ", "G3 ")) for line in blocks))
        engraving = [line for line in blocks if line.startswith("G1 Z")]
        self.assertGreaterEqual(len(engraving), 5)

    def test_elliptical_c_uses_tolerance_correct_g2_g3_segments(self) -> None:
        arcs = text_arcs("C", height=3, width=1.5, spacing=0.3)
        self.assertGreater(len(arcs), 2)
        for start, end, center, _clockwise in arcs:
            start_radius = math.hypot(start[0] - center[0], start[1] - center[1])
            end_radius = math.hypot(end[0] - center[0], end[1] - center[1])
            self.assertAlmostEqual(start_radius, end_radius, places=9)

    def test_project_4118460_elliptical_c_survives_nc_rounding(self) -> None:
        blocks = mantle_marking_blocks(MantleMarking(
            text="C", c_degrees=0, z=-12, diameter=26.9,
            engraving_diameter=26.8, clearance_diameter=28.9,
            height=3, width=1.5, character_spacing=0.3,
            orientation="Längs Z-axeln", rotation_degrees=180,
            plane="XYZ+C", z_direction="Z-", turret="Upper",
        ))
        current_z = current_y = 0.0
        checked = 0
        for line in blocks:
            z_match = re.search(r"(?:^| )Z(-?\d+(?:\.\d*)?)", line)
            y_match = re.search(r"(?:^| )Y(-?\d+(?:\.\d*)?)", line)
            if line.startswith(("G2 ", "G3 ")):
                self.assertIsNotNone(z_match)
                self.assertIsNotNone(y_match)
                k = float(re.search(r" K(-?\d+(?:\.\d*)?)", line).group(1))
                j = float(re.search(r" J(-?\d+(?:\.\d*)?)", line).group(1))
                end_z, end_y = float(z_match.group(1)), float(y_match.group(1))
                start_radius = math.hypot(k, j)
                end_radius = math.hypot(end_z - (current_z + k), end_y - (current_y + j))
                self.assertLess(abs(start_radius - end_radius), 0.002)
                checked += 1
            if z_match:
                current_z = float(z_match.group(1))
            if y_match:
                current_y = float(y_match.group(1))
        self.assertGreater(checked, 2)

    def test_xz_c_keeps_curves_as_g1_segments(self) -> None:
        blocks = mantle_marking_blocks(
            MantleMarking(
                text="O", c_degrees=0, z=0, diameter=50,
                engraving_diameter=49.5, clearance_diameter=52,
                height=5, width=4, orientation="Längs Z-axeln", plane="XZ+C",
            )
        )
        self.assertFalse(any(line.startswith(("G2 ", "G3 ")) for line in blocks))

    def test_flat_stock_retracts_past_corners_before_c_indexing(self) -> None:
        blocks = mantle_marking_blocks(
            MantleMarking(
                text="I", c_degrees=90, z=0, y=0, diameter=20,
                engraving_diameter=19.5, clearance_diameter=22,
                rotation_clearance_diameter=46.721,
                height=5, width=3, orientation="Längs Z-axeln", plane="XYZ",
            )
        )
        c_index = next(i for i, line in enumerate(blocks) if "C90." in line)
        self.assertEqual(blocks[c_index - 1], "G0 X46.721")
        self.assertNotIn(" X", blocks[c_index])
        self.assertEqual(blocks[c_index + 1], "G0 X22.")
        self.assertEqual(sum(" C90." in line for line in blocks), 1)
        self.assertFalse(any(first == second for first, second in zip(blocks, blocks[1:])))

    def test_same_flat_face_does_not_reindex_c(self) -> None:
        blocks = mantle_marking_blocks(
            MantleMarking(
                text="I", c_degrees=120, z=0, y=0, diameter=20,
                engraving_diameter=19.5, clearance_diameter=22,
                rotation_clearance_diameter=46.721, index_c=False,
                height=5, width=3, orientation="Längs Z-axeln", plane="XYZ",
            )
        )
        self.assertFalse(any(" C" in line for line in blocks))
        self.assertNotIn("G0 X46.721", blocks)

    def test_every_program_in_collection_has_generator_comment(self) -> None:
        content = create_nc_collection(
            (("1200", "", ["(RAD 1)"]), ("1201", "", ["(RAD 2)"]))
        )
        self.assertEqual(content.count("(SKAPAT MED SUBGLYPH VERSION 1.13-test)"), 2)

    def test_subprogram_does_not_set_modal_units(self) -> None:
        content = create_nc_program("1200", body_lines=["G1 X49.5"])
        self.assertNotIn("G20", content)
        self.assertNotIn("G21", content)

    def test_generated_comments_follow_selected_language(self) -> None:
        generated_at = datetime(2026, 8, 12, 17, 45, 6)
        english = create_nc_program("1200", generated_at=generated_at, language="English")
        finnish = create_nc_program("1200", generated_at=generated_at, language="Suomi")
        bosnian = create_nc_program("1200", generated_at=generated_at, language="Bosanski")
        polish = create_nc_program("1200", generated_at=generated_at, language="Polski")
        self.assertIn("(CREATED WITH SUBGLYPH VERSION 1.13-test)", english)
        self.assertIn("(CREATED 2026-08-12 17:45:06)", english)
        self.assertIn("(LUOTU SUBGLYPH-VERSIOLLA 1.13-test)", finnish)
        self.assertIn("(LUOTU 2026-08-12 17:45:06)", finnish)
        self.assertIn("(KREIRANO POMOCU SUBGLYPH VERZIJE 1.13-test)", bosnian)
        self.assertIn("(UTWORZONO ZA POMOCA SUBGLYPH W WERSJI 1.13-test)", polish)

    def test_new_languages_cover_all_translated_text(self) -> None:
        reference_ui = set(subglyph.TRANSLATIONS["English"])
        reference_support = set(subglyph.SUPPORT_TRANSLATIONS["English"])
        for language in ("Bosanski", "Polski"):
            self.assertEqual(set(subglyph.TRANSLATIONS[language]), reference_ui)
            self.assertEqual(set(subglyph.SUPPORT_TRANSLATIONS[language]), reference_support)

    def test_direct_feeds_are_written_to_nc_blocks(self) -> None:
        blocks = mantle_marking_blocks(
            MantleMarking(
                text="L",
                c_degrees=0,
                z=-10,
                diameter=50,
                engraving_diameter=49.5,
                clearance_diameter=52,
                height=5,
                width=3,
                orientation="Axiell",
                plunge_feed=150,
                engraving_feed=800,
            )
        )
        self.assertIn("G1 X49.5F150", blocks)
        self.assertTrue(any(line.endswith("F800") for line in blocks))
        self.assertFalse(any("#" in line for line in blocks))

    def test_nc_coordinates_have_decimal_point_and_max_three_decimals(self) -> None:
        self.assertEqual(nc_number(50), "50.")
        self.assertEqual(nc_number(12.34567), "12.346")

    def test_frontplane_engraves_xy_with_z_depth_and_c_index(self) -> None:
        blocks = front_marking_blocks(FrontMarking(
            text="L", x=10, y=5, c_degrees=0,
            engraving_z=-0.4, clearance_z=2,
            height=5, width=3, plunge_feed=100, engraving_feed=500,
        ))
        self.assertTrue(any(line.startswith("G0 Z2. X") and " C0." in line for line in blocks))
        self.assertIn("G1 Z-0.4F100", blocks)
        self.assertTrue(any(line.startswith("G1 X") and " Y" in line for line in blocks))
        self.assertIn("G0 Z2.", blocks)
        self.assertFalse(any("G17" in line for line in blocks))

    def test_frontplane_arcs_use_ij_without_defining_plane(self) -> None:
        blocks = front_marking_blocks(FrontMarking(
            text="O", x=0, y=0, c_degrees=0,
            engraving_z=-0.2, clearance_z=1,
            height=5, width=3,
        ))
        arcs = [line for line in blocks if line.startswith(("G2 ", "G3 "))]
        self.assertTrue(arcs)
        self.assertTrue(all(" I" in line and " J" in line for line in arcs))
        self.assertFalse(any("G17" in line for line in blocks))

    def test_frontplane_c_rotates_anchor_and_can_skip_reindex(self) -> None:
        blocks = front_marking_blocks(FrontMarking(
            text="I", x=10, y=0, c_degrees=90,
            engraving_z=-0.2, clearance_z=1,
            height=5, width=3, index_c=False,
        ))
        first_position = next(line for line in blocks if line.startswith("G0 X"))
        self.assertIn("X-2.5", first_position)
        self.assertIn("Y8.5", first_position)
        self.assertNotIn(" C", first_position)


if __name__ == "__main__":
    unittest.main()
