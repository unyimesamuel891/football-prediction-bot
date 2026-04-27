"""
Football Prediction Engine
Combines statistical analysis with Google Gemini AI reasoning.
"""

import os
import re
import google.generativeai as genai
from dataclasses import dataclass, field
from typing import Optional

MARKET_NAMES = {
    "mkt_1x2": "Match Winner (1X2)",
    "mkt_btts": "Both Teams To Score (BTTS)",
    "mkt_ou": "Over/Under Goals",
    "mkt_cs": "Correct Score",
    "mkt_corners": "Expected Corners",
}


@dataclass
class MatchStats:
    home_team: str
    away_team: str
    home_form: list = field(default_factory=list)
    away_form: list = field(default_factory=list)
    home_goals_scored: float = 1.5
    away_goals_scored: float = 1.2
    home_goals_conceded: float = 1.2
    away_goals_conceded: float = 1.5
    home_corners: float = 5.0
    away_corners: float = 4.5


def parse_stats(home_team: str, away_team: str, raw: Optional[str]) -> MatchStats:
    stats = MatchStats(home_team=home_team, away_team=away_team)
    if not raw:
        return stats

    def extract_float(pattern, text, default):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
        return default

    def extract_form(pattern, text):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return [c.upper() for c in re.findall(r"[WDLwdl]", m.group(1))]
        return []

    stats.home_form = extract_form(r"home\s+form[:\s]+([WDLwdl\s]+)", raw)
    stats.away_form = extract_form(r"away\s+form[:\s]+([WDLwdl\s]+)", raw)
    stats.home_goals_scored = extract_float(r"home\s+avg\s+goals\s+scored[:\s]+([\d.]+)", raw, 1.5)
    stats.away_goals_scored = extract_float(r"away\s+avg\s+goals\s+scored[:\s]+([\d.]+)", raw, 1.2)
    stats.home_goals_conceded = extract_float(r"home\s+avg\s+goals\s+conceded[:\s]+([\d.]+)", raw, 1.2)
    stats.away_goals_conceded = extract_float(r"away\s+avg\s+goals\s+conceded[:\s]+([\d.]+)", raw, 1.5)
    stats.home_corners = extract_float(r"home\s+avg\s+corners[:\s]+([\d.]+)", raw, 5.0)
    stats.away_corners = extract_float(r"away\s+avg\s+corners[:\s]+([\d.]+)", raw, 4.5)
    return stats


def form_to_points(form: list) -> float:
    if not form:
        return 1.5
    pts = sum({"W": 3, "D": 1, "L": 0}.get(r, 0) for r in form[-5:])
    return pts / max(len(form[-5:]), 1)


def compute_stats_summary(stats: MatchStats) -> dict:
    home_form_pts = form_to_points(stats.home_form)
    away_form_pts = form_to_points(stats.away_form)

    xg_home = (stats.home_goals_scored + stats.away_goals_conceded) / 2 * 1.1
    xg_away = (stats.away_goals_scored + stats.home_goals_conceded) / 2

    expected_total_goals = xg_home + xg_away
    expected_corners = stats.home_corners + stats.away_corners
    btts_prob = min(0.95, (xg_home / 2.5) * (xg_away / 2.0))

    home_win_prob = min(0.75, max(0.15, 0.45 + (home_form_pts - away_form_pts) * 0.05 + (xg_home - xg_away) * 0.08))
    draw_prob = max(0.10, 0.27 - abs(home_form_pts - away_form_pts) * 0.03)
    away_win_prob = max(0.05, 1.0 - home_win_prob - draw_prob)

    return {
        "xg_home": round(xg_home, 2),
        "xg_away": round(xg_away, 2),
        "expected_total_goals": round(expected_total_goals, 2),
        "expected_corners": round(expected_corners, 1),
        "btts_prob": round(btts_prob * 100, 1),
        "home_win_pct": round(home_win_prob * 100, 1),
        "draw_pct": round(draw_prob * 100, 1),
        "away_win_pct": round(away_win_prob * 100, 1),
        "home_form": stats.home_form[-5:] if stats.home_form else ["?"],
        "away_form": stats.away_form[-5:] if stats.away_form else ["?"],
    }


class FootballPredictor:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Set the GEMINI_API_KEY environment variable.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    async def predict(
        self,
        home_team: str,
        away_team: str,
        stats_raw: Optional[str],
        markets: list,
    ) -> str:
        stats = parse_stats(home_team, away_team, stats_raw)
        summary = compute_stats_summary(stats)
        market_labels = [MARKET_NAMES.get(m, m) for m in markets]

        prompt = self._build_prompt(home_team, away_team, summary, market_labels)

        response = self.model.generate_content(prompt)
        ai_text = response.text

        return self._format_response(home_team, away_team, summary, market_labels, ai_text)

    def _build_prompt(self, home: str, away: str, summary: dict, markets: list) -> str:
        return f"""You are an expert football analyst. Predict the following match using both the statistical signals provided and your football knowledge.

## Match
{home} (Home) vs {away} (Away)

## Statistical Signals
- Home xG: {summary['xg_home']} | Away xG: {summary['xg_away']}
- Expected total goals: {summary['expected_total_goals']}
- Expected total corners: {summary['expected_corners']}
- BTTS probability (stats model): {summary['btts_prob']}%
- 1X2 probabilities: Home {summary['home_win_pct']}% | Draw {summary['draw_pct']}% | Away {summary['away_win_pct']}%
- Home recent form: {' '.join(summary['home_form'])}
- Away recent form: {' '.join(summary['away_form'])}

## Markets to Predict
{chr(10).join(f'- {m}' for m in markets)}

## Instructions
For each market, provide:
1. Your prediction / pick
2. Confidence level (Low / Medium / High)
3. 2-3 sentence reasoning combining stats and football knowledge

Also give a brief overall match narrative (2-3 sentences).

Format your response clearly with headers for each market. Be direct and specific.
"""

    def _format_response(self, home: str, away: str, summary: dict, markets: list, ai_text: str) -> str:
        form_h = " ".join(summary["home_form"]) or "N/A"
        form_a = " ".join(summary["away_form"]) or "N/A"

        header = (
            f"⚽ *{home}* vs *{away}*\n"
            f"{'─' * 32}\n\n"
            f"📊 *Stats Snapshot*\n"
            f"🏠 Home xG: `{summary['xg_home']}` | Form: `{form_h}`\n"
            f"✈️ Away xG: `{summary['xg_away']}` | Form: `{form_a}`\n"
            f"🎯 Total xG: `{summary['expected_total_goals']}` | Corners: `{summary['expected_corners']}`\n\n"
            f"{'─' * 32}\n"
            f"🤖 *AI + Stats Predictions*\n\n"
        )

        footer = (
            "\n\n"
            f"{'─' * 32}\n"
            "⚠️ _Predictions for entertainment only. Please gamble responsibly._\n"
            "▶️ Use /predict for another match."
        )

        return header + ai_text + footer
