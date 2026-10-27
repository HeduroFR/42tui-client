"""Physical gaps and terminal resizing must never hide or move a workstation."""
import unittest
from ft_tui.features.cluster_map.geometry import load_layout, fit_tiles, neighbor, positions, row_heights


class GeometryTests(unittest.TestCase):
    def test_odd_seat_widths_center_icons_without_reducing_photo_height(self):
        for view in ('all','c1','c2','c3'):
            matrix=load_layout(view)
            for width,height in ((156,35),(200,45),(300,60)):
                with self.subTest(view=view,width=width,height=height):
                    size=fit_tiles(view,width,height)
                    self.assertEqual(size.width%2,1)
                    aisles=0 if view=='all' else sum(not any(row) for row in matrix)
                    self.assertEqual(size.height,(height-aisles)//(len(matrix)-aisles))
                    self.assertLessEqual(len(matrix[0])*size.width,width)

    def test_specific_view_keeps_seats_compact_in_wide_terminals(self):
        size=fit_tiles('c3',200,45)
        self.assertGreater(size.height,45//len(load_layout('c3')))
        self.assertLess(size.width,size.height*2)
        self.assertEqual(row_heights('c3',size).count(1),2)

    def test_reference_coordinates_and_host_sets(self):
        all_seats = positions('all')
        self.assertEqual(len(all_seats), 147)
        for view in ('c1', 'c2', 'c3'):
            self.assertEqual(len(positions(view)), 49)
        self.assertEqual(all_seats['1H4'], (3, 7))
        self.assertEqual(all_seats['2D5'], (13, 3))
        self.assertEqual(all_seats['2D1'], (8, 4))
        self.assertEqual(all_seats['3C1'], (17, 3))
        self.assertEqual(all_seats['3E1'], (17, 6))
        self.assertNotIn('1H3', all_seats)
        self.assertEqual({h for v in ('c1','c2','c3') for h in positions(v)}, set(all_seats))

    def test_fit_is_uniform_complete_and_deterministic(self):
        for view in ('all','c1','c2','c3'):
            matrix = load_layout(view)
            for width,height in ((76,15),(116,25),(156,35)):
                size = fit_tiles(view,width,height)
                self.assertIsNotNone(size)
                self.assertLessEqual(len(matrix[0])*size.width,width)
                self.assertLessEqual(sum(row_heights(view,size)),height)
                self.assertEqual(size,fit_tiles(view,width,height))
            self.assertIsNone(fit_tiles(view,1,1))

    def test_navigation_skips_real_gaps(self):
        self.assertEqual(neighbor('all','1B3','right'),'1B4')
        self.assertEqual(neighbor('all','1A7','right'),'2A1')
        self.assertEqual(neighbor('c2','2C1','down'),'2D1')
        self.assertEqual(neighbor('c3','3B1','down'),'3C1')
        self.assertIsNone(neighbor('c1','1A1','left'))
