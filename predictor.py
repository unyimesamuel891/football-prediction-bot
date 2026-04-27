"""
Football Prediction Engine - Optimized for speed
Uses football-data.org + Gemini AI
Plain text output to avoid Telegram Markdown parse errors.
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
COMPETITIONS = ["PL", "PD", "BL1", "SA", "FL1", "CL"]


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

    async def find_team_in_competition(self, session, comp: str, name: str) -> Optional[dict]:
        url = f"{FOOTBALL_DATA_BASE}/competitions/{comp}/teams"
        try:
            async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                name_lower = name.lower()
                for team in data.get("teams", []):
                    t_name = team.get("name", "").lower()
                    t_short = team.get("shortName", "").lower()
                    t_tla = team.get("tla", "").lower()
                    if (name_lower in t_name or name_lower in t_short or t_tla == name_lower):
                        return team
        except Exception:
            pass
        return None

    async def search_team(self, session, name: str) -> Optional[dict]:
        tasks = [self.find_team_in_competition(session, comp, name) for comp in COMPETITIONS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if r and not isinstance(r, Exception):
                return r
        return None

    async def get_team_matches(self, session, team_id: int) -> list:
        url = f"{FOOTBALL_DATA_BASE}/teams/{team_id}/matches"
        params = {"status": "FINISHED", "limit": 5}
        try:
            async with session.get(url, headers=self.headers, params=params,
                                   timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data.get("matches", [])[-5:]
        except Exception:
            return []

    def extract_form(self, matches, team_id):
        form = []
        for m in matches:
            home_id = m.get("homeTeam", {}).get("id")
            score = m.get("score", {}).get("fullTime", {})
            hg = score.get("home") or 0
            ag = score.get("away") or 0
            if home_id == team_id:
                form.append("W" if hg > ag else "D" if hg == ag else "L")
            else:
                form.append("W" if ag > hg else "D" if ag == hg else "L")
        return form

    def extract_goal_averages(self, matches, team_id):
        if not matches:
            return 1.5, 1.2
        scored, conceded = 0, 0
        for m in matches:
            home_id = m.get("homeTeam", {}).get("id")
            score = m.get("score", {}).get("fullTime", {})
            hg = score.get("home") or 0
            ag = score.get("away") or 0
            if home_id == team_id:
                scored += hg; conceded += ag
            else:
                scored += ag; conceded += hg
        n = len(matches)
        return round(scored / n, 2), round(conceded / n, 2)


def form_to_points(form):
    if not form:
        return 1.5
    pts = sum({"W": 3, "D": 1, "L": 0}.get(r, 0) for r in form[-5:])
    return pts / max(len(form[-5:]), 1)


def compute_summary(stats: MatchStats) -> dict:
    hfp = form_to_points(stats.home_form)
    afp = form_to_points(stats.away_form)
    xg_h = (stats.home_goals_scored + stats.away_goals_conceded) / 2 * 1.1
    xg_a = (stats.away_goals_scored + stats.home_goals_conceded) / 2
    tot_g = xg_h + xg_a
    tot_c = stats.home_corners + stats.away_corners
    btts = min(0.95, (xg_h / 2.5) * (xg_a / 2.0))
    hwp = min(0.75, max(0.15, 0.45 + (hfp - afp) * 0.05 + (xg_h - xg_a) * 0.08))
    dp = max(0.10, 0.27 - abs(hfp - afp) * 0.03)
    awp = max(0.05, 1.0 - hwp - dp)
    return {
        "xg_home": round(xg_h, 2), "xg_away": round(xg_a, 2),
        "total_goals": round(tot_g, 2), "total_corners": round(tot_c, 1),
        "btts_pct": round(btts * 100, 1),
        "home_win_pct": round(hwp * 100, 1),
        "draw_pct": round(dp * 100, 1),
        "away_win_pct": round(awp * 100, 1),
        "home_form": stats.home_form[-5:] or ["?"],
        "away_form": stats.away_form[-5:] or ["?"],
        "data_source": stats.data_source,
        "home_label": stats.home_team_full or stats.home_team,
        "away_label": stats.away_team_full or stats.away_team,
    }


def clean_text(text: str) -> str:
    """Strip markdown symbols that break Telegram's parser."""
    for ch in ["*", "_", "`", "[", "]", "(", ")"]:
        text = text.replace(ch, "")
    return text.strip()


class FootballPredictor:
    def __init__(self):
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_key:
            raise ValueError("GEMINI_API_KEY not set")
        genai.configure(api_key=gemini_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

        fd_key = os.environ.get("FOOTBALL_DATA_KEY")
        self.fd = FootballDataClient(fd_key) if fd_key else None

    async def build_stats(self, home: str, away: str) -> MatchStats:
        stats = MatchStats(home_team=home, away_team=away)
        if not self.fd:
            return stats
        try:
            async with aiohttp.ClientSession() as session:
                home_team, away_team = await asyncio.gather(
                    self.fd.search_team(session, home),
                    self.fd.search_team(session, away),
                )
                home_matches, away_matches = await asyncio.gather(
                    self.fd.get_team_matches(session, home_team["id"]) if home_team else asyncio.sleep(0, result=[]),
                    self.fd.get_team_matches(session, away_team["id"]) if away_team else asyncio.sleep(0, result=[]),
                )

            if home_team and home_matches:
                tid = home_team["id"]
                stats.home_team_full = home_team.get("name", home)
                stats.home_form = self.fd.extract_form(home_matches, tid)
                stats.home_goals_scored, stats.home_goals_conceded = self.fd.extract_goal_averages(home_matches, tid)
                stats.data_source = "live"

            if away_team and away_matches:
                tid = away_team["id"]
                stats.away_team_full = away_team.get("name", away)
                stats.away_form = self.fd.extract_form(away_matches, tid)
                stats.away_goals_scored, stats.away_goals_conceded = self.fd.extract_goal_averages(away_matches, tid)
                stats.data_source = "live"

        except Exception as e:
            print(f"Stats error: {e}")
        return stats

    async def predict(self, home_team: str, away_team: str, markets: list) -> str:
        stats = await self.build_stats(home_team, away_team)
        s = compute_summary(stats)
        market_labels = [MARKET_NAMES.get(m, m) for m in markets]

        prompt = f"""You are a football prediction expert. Give a direct prediction for this match.

Match: {s['home_label']} (Home) vs {s['away_label']} (Away)
Data: {'Live stats' if s['data_source'] == 'live' else 'AI estimated'}
Home xG: {s['xg_home']} | Form: {' '.join(s['home_form'])}
Away xG: {s['xg_away']} | Form: {' '.join(s['away_form'])}
Total xG: {s['total_goals']} | Corners: {s['total_corners']}
BTTS: {s['btts_pct']}% | 1X2: Home {s['home_win_pct']}% Draw {s['draw_pct']}% Away {s['away_win_pct']}%

Markets to predict: {', '.join(market_labels)}

IMPORTANT: Reply in plain text only. No markdown, no asterisks, no underscores, no special formatting.
For each market write: MARKET NAME: Pick | Confidence | Reason (1-2 sentences)
End with: VERDICT: one sentence summary."""

        response = self.model.generate_content(prompt)
        ai_text = clean_text(response.text)

        src = "Live stats" if s["data_source"] == "live" else "AI estimated"
        form_h = " ".join(s["home_form"])
        form_a = " ".join(s["away_form"])

        # Plain text output — no Markdown at all
        return (
            f"⚽ {s['home_label']} vs {s['away_label']}\n"
            f"{'='*32}\n"
            f"📊 Stats ({src})\n"
            f"🏠 xG: {s['xg_home']} | Form: {form_h}\n"
            f"✈️  xG: {s['xg_away']} | Form: {form_a}\n"
            f"🎯 Goals: {s['total_goals']} | Corners: {s['total_corners']}\n"
            f"{'='*32}\n"
            f"🤖 Predictions\n\n"
            f"{ai_text}\n\n"
            f"{'='*32}\n"
            f"⚠️ For entertainment only. Gamble responsibly.\n"
            f"Tap /predict for another match."
        )
