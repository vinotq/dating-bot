from src.calculator import calc_behavioral, calc_combined, calc_primary


class TestCalcPrimary:
    def test_full_profile(self):
        assert calc_primary(100, 5, True) == 100.0

    def test_no_photos(self):
        assert calc_primary(100, 0, True) == 70.0

    def test_no_preferences(self):
        assert calc_primary(100, 5, False) == 70.0

    def test_empty_profile(self):
        assert calc_primary(0, 0, False) == 0.0

    def test_partial_completeness(self):
        result = calc_primary(50, 5, True)
        assert result == round(40 * 0.5 + 30 + 30, 2)

    def test_photo_cap_at_5(self):
        assert calc_primary(100, 10, True) == 100.0

    def test_clamped_above_100(self):
        assert calc_primary(100, 5, True) <= 100.0

    def test_clamped_below_0(self):
        assert calc_primary(0, 0, False) >= 0.0


class TestCalcBehavioral:
    def test_zero_interactions(self):
        assert calc_behavioral(0, 0, 0, 0, 0.0) == 0.0

    def test_perfect_score(self):
        result = calc_behavioral(100, 0, 100, 100, 100.0)
        assert result <= 100.0

    def test_avg_likes_zero_skips_norm(self):
        result = calc_behavioral(10, 0, 5, 5, 0.0)
        assert result >= 0.0

    def test_like_skip_ratio(self):
        all_likes = calc_behavioral(100, 0, 50, 50, 100.0)
        half = calc_behavioral(50, 50, 25, 25, 100.0)
        assert all_likes > half

    def test_result_bounded(self):
        result = calc_behavioral(1000, 0, 1000, 1000, 1.0)
        assert 0.0 <= result <= 100.0


class TestCalcCombined:
    def test_few_interactions_weights_primary(self):
        primary_heavy = calc_combined(100.0, 0.0, 5, 0)
        assert primary_heavy == round(0.7 * 100.0 + 0.3 * 0.0, 2)

    def test_many_interactions_weights_behavioral(self):
        result = calc_combined(0.0, 100.0, 20, 0)
        assert result == round(0.3 * 0.0 + 0.7 * 100.0, 2)

    def test_referral_bonus(self):
        without = calc_combined(50.0, 50.0, 5, 0)
        with_referral = calc_combined(50.0, 50.0, 5, 1)
        assert with_referral == without + 5.0

    def test_referral_bonus_capped_at_15(self):
        result = calc_combined(50.0, 50.0, 5, 10)
        base = calc_combined(50.0, 50.0, 5, 0)
        assert result - base == 15.0

    def test_clamped_at_100(self):
        assert calc_combined(100.0, 100.0, 20, 10) <= 100.0

    def test_clamped_at_0(self):
        assert calc_combined(0.0, 0.0, 20, 0) >= 0.0
