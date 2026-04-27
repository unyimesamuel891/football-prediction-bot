"""
Football Prediction Engine
Auto-fetches real stats from football-data.org, then uses Gemini AI for predictions.
"""

import os
import asyncio
import aiohttp
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

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"

# Supported competitions on free tier
COMPETITIONS = ["PL", "PD", "BL1", "SA", "FL1", "CL", "EL", "EC", "WC"]


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
    data_source: str = "estimated"
    home_team_full: str = ""
    away_team_full: str = ""


class FootballDataClient:
    def __init__(self, api_key: str):
        self.headers = {"X-Auth-Token": api_key}

    async def search_team(self, session: aiohttp.ClientSession, name: str) -> Optional[dict]:
        """Search all competitions for a team matching the name."""
        name_lower = name.lower()
        for comp in COMPETITIONS:
            url = f"{FOOTBALL_DATA_BASE}/competitions/{comp}/teams"
            try:
                async with session.get(url, headers=self.headers) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    for team in data.get("teams", []):
                        t_name = team.get("name", "").lower()
                        t_short = team.get("shortName", "").lower()
                        t_tla = team.get("tla", "").lower()
                        if (name_lower in t_name or name_lower in t_short
                                or t_tla == name_lower
                                or name_lower == t_name
                                or name_lower == t_short):
                            return {"team": team, "competition": comp}
            except Exception:
                continue
        return None

    async def get_team_matches(self, session: aiohttp.ClientSession, team_id: int, last: int = 5) -> list:
        """Get last N matches for a team."""
        url = f"{FOOTBALL_DATA_BASE}/teams/{team_id}/matches"
        params = {"status": "FINISHED", "limit": last}
        try:
            async with session.get(url, headers=self.headers, params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                matches = data.get("matches", [])
                # Return last N only
                return matches[-last:] if len(matches) >= last else matches
        except Exception:
            return []

    def extract_form(self, matches: list, team_id: int) -> list:
        """Extract W/D/L from recent matches."""
        form = []
        for m in matches:
            home_id = m.get("homeTeam", {}).get("id")
            score = m.get("score", {}).get("fullTime", {})
            home_goals = score.get("home", 0) or 0
            away_goals = score.get("away", 0) or 0

            if home_id == team_id:
                if home_goals > away_goals:
                    form.append("W")
                elif home_goals == away_goals:
                    form.append("D")
                else:
                    form.append("L")
            else:
                if away_goals > home_goals:
                    form.append("W")
                elif away_goals == home_goals:
                    form.append("D")
                else:
                    form.append("L")
        return form

    def extract_goal_averages(self, matches: list, team_id: int) -> tuple:
        """Return (avg_scored, avg_conceded) from recent matches."""
        if not matches:
            return 1.5, 1.2
        scored, conceded = 0, 0
        for m in matches:
            home_id = m.get("homeTeam", {}).get("id")
            score = m.get("score", {}).get("fullTime", {})
            hg = score.get("home", 0) or 0
            ag = score.get("away", 0) or 0
            if home_id == team_id:
                scored += hg
                conceded += ag
            else:
                scored += ag
                conceded += hg
        n = len(matches)
        return round(scored / n, 2), round(conceded / n, 2)


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

    home_win_prob = min(0.75, max(0.15,
        0.45 + (home_form_pts - away_form_pts) * 0.05 + (xg_home - xg_away) * 0.08))
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
        "data_source": stats.data_source,
        "home_team_full": stats.home_team_full,
        "away_team_full": stats.away_team_full,
    }


class FootballPredictor:
    def __init__(self):
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_key:
            raise ValueError("Set the GEMINI_API_KEY environment variable.")
        genai.configure(api_key=gemini_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

        fd_key = os.environ.get("FOOTBALL_DATA_KEY")
        self.fd_client = FootballDataClient(fd_key) if fd_key else None

    async def build_match_stats(self, home_team: str, away_team: str) -> MatchStats:
        stats = MatchStats(home_team=home_team, away_team=away_team)

        if not self.fd_client:
            return stats

        try:
            async with aiohttp.ClientSession() as session:
                home_result, away_result = await asyncio.gather(
                    self.fd_client.search_team(session, home_team),
                    self.fd_client.search_team(session, away_team),
                )

                tasks = []
                if home_result:
                    tasks.append(self.fd_client.get_team_matches(
                        session, home_result["team"]["id"], last=5))
                else:
                    tasks.append(asyncio.sleep(0))

                if away_result:
                    tasks.append(self.fd_client.get_team_matches(
                        session, away_result["team"]["id"], last=5))
                else:
                    tasks.append(asyncio.sleep(0))

                results = await asyncio.gather(*tasks)
                home_matches = results[0] if home_result else []
                away_matches = results[1] if away_result else []

            if home_result and home_matches:
                team = home_result["team"]
                stats.home_team_full = team.get("name", home_team)
                tid = team["id"]
                stats.home_form = self.fd_client.extract_form(home_matches, tid)
                stats.home_goals_scored, stats.home_goals_conceded = \
                    self.fd_client.extract_goal_averages(home_matches, tid)
                stats.data_source = "live"

            if away_result and away_matches:
                team = away_result["team"]
                stats.away_team_full = team.get("name", away_team)
                tid = team["id"]
                stats.away_form = self.fd_client.extract_form(away_matches, tid)
                stats.away_goals_scored, stats.away_goals_conceded = \
                    self.fd_client.extract_goal_averages(away_matches, tid)
                stats.data_source = "live"

        except Exception as e:
            print(f"Stats fetch error: {e}")
            stats.data_source = "estimated"

        return stats

    async def predict(self, home_team: str, away_team: str, markets: list) -> str:
        stats = await self.build_match_stats(home_team, away_team)
        summary = compute_stats_summary(stats)
        market_labels = [MARKET_NAMES.get(m, m) for m in markets]

        prompt = self._build_prompt(home_team, away_team, summary, market_labels)
        response = self.model.generate_content(prompt)
        return self._format_response(summary, home_team, away_team, response.text)

    def _build_prompt(self, home: str, away: str, summary: dict, markets: list) -> str:
        source = "live football-data.org stats" if summary["data_source"] == "live" else "AI-estimated stats"
        return f"""You are an expert football analyst. Predict this match using the stats below ({source}) combined with your football knowledge.

## Match
{summary.get('home_team_full') or home} (Home) vs {summary.get('away_team_full') or away} (Away)

## Statistical Signals
- Home xG: {summary['xg_home']} | Away xG: {summary['xg_away']}
- Expected total goals: {summary['expected_total_goals']}
- Expected total corners: {summary['expected_corners']}
- BTTS probability: {summary['btts_prob']}%
- 1X2: Home {summary['home_win_pct']}% | Draw {summary['draw_pct']}% | Away {summary['away_win_pct']}%
- Home last 5: {' '.join(summary['home_form'])}
- Away last 5: {' '.join(summary['away_form'])}

## Markets to Predict
{chr(10).join(f'- {m}' for m in markets)}

For each market give:
1. Your exact pick
2. Confidence: Low / Medium / High
3. 2-3 sentences of reasoning

End with a 2-sentence match narrative. Be direct and specific.
"""

    def _format_response(self, summary: dict, home: str, away: str, ai_text: str) -> str:
        form_h = " ".join(summary["home_form"]) or "N/A"
        form_a = " ".join(summary["away_form"]) or "N/A"
        home_label = summary.get("home_team_full") or home
        away_label = summary.get("away_team_full") or away
        source_emoji = "🟢" if summary["data_source"] == "live" else "🟡"
        source_label = "Live stats" if summary["data_source"] == "live" else "AI estimated"

        return (
            f"⚽ *{home_label}* vs *{away_label}*\n"
            f"{'─' * 32}\n\n"
            f"📊 *Stats* {source_emoji} _{source_label}_\n"
            f"🏠 xG: `{summary['xg_home']}` | Form: `{form_h}`\n"
            f"✈️ xG: `{summary['xg_away']}` | Form: `{form_a}`\n"
            f"🎯 Total xG: `{summary['expected_total_goals']}` | Corners: `{summary['expected_corners']}`\n\n"
            f"{'─' * 32}\n"
            f"🤖 *Predictions*\n\n"
            f"{ai_text}\n\n"
            f"{'─' * 32}\n"
            "⚠️ _For entertainment only. Gamble responsibly._\n"
            "▶️ /predict for another match."
        )
