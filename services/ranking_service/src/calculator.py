from __future__ import annotations


def calc_primary(
    completeness_score: int,
    photo_count: int,
    preferences_filled: bool,
) -> float:
    norm = completeness_score / 100.0
    photo_norm = min(photo_count / 5.0, 1.0)
    pref = 1.0 if preferences_filled else 0.0
    score = 40.0 * norm + 30.0 * photo_norm + 30.0 * pref
    return round(min(100.0, max(0.0, score)), 2)


def calc_behavioral(
    total_likes: int,
    total_skips: int,
    total_matches: int,
    total_chats: int,
    avg_likes_system: float,
) -> float:
    if avg_likes_system > 0:
        likes_norm = min(total_likes / avg_likes_system, 1.0)
    else:
        likes_norm = 0.0

    total_swipes = total_likes + total_skips
    like_skip_ratio = total_likes / total_swipes if total_swipes > 0 else 0.0
    match_rate = total_matches / total_likes if total_likes > 0 else 0.0
    chat_rate = total_chats / total_matches if total_matches > 0 else 0.0

    score = 100.0 * (
        0.25 * likes_norm
        + 0.25 * like_skip_ratio
        + 0.25 * min(match_rate, 1.0)
        + 0.15 * min(chat_rate, 1.0)
    )
    return round(min(100.0, max(0.0, score)), 2)


def calc_combined(
    primary_score: float,
    behavioral_score: float,
    total_interactions: int,
    referral_count: int,
) -> float:
    w1 = 0.7 if total_interactions < 20 else 0.3
    w2 = 1.0 - w1
    bonus = min(5.0 * referral_count, 15.0)
    score = w1 * primary_score + w2 * behavioral_score + bonus
    return round(min(100.0, max(0.0, score)), 2)
