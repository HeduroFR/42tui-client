import unittest

from ft_tui.features.cluster_map.experience import estimate_experience, THRESHOLDS


class ExperienceTests(unittest.TestCase):
    def test_zero_level_has_a_real_first_level_requirement(self):
        self.assertEqual(estimate_experience(21,0),{
            'total_xp':0,'level_start_xp':0,'next_level_xp':462,'estimated':True,
        })

    def test_fractional_level_interpolates_within_cumulative_bounds(self):
        data=estimate_experience(21,1.5)
        self.assertEqual(data['total_xp'],1575)
        self.assertEqual(data['next_level_xp']-data['level_start_xp'],2226)
        self.assertTrue(data['estimated'])
        self.assertTrue(all(a<b for a,b in zip(THRESHOLDS,THRESHOLDS[1:])))

    def test_unknown_cursus_or_out_of_range_never_extrapolate(self):
        for cursus,level in ((9,1),(21,None),(21,True),(21,-1),(21,float('nan')),
                             (21,float('inf')),(21,30),(21,100)):
            with self.subTest(cursus=cursus,level=level):
                self.assertIsNone(estimate_experience(cursus,level))
