# backend/parser.py
import json
import re
import sys
import io
import traceback
from typing import Dict, Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from config import GROQ_KEYS_PARSER, MODEL_PARSER

try:
    import requests
except ImportError:
    raise ImportError("'pip install requests' edin.")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ====================== LİQ ORTALAMA VERİTABANI ======================
LEAGUE_AVERAGES = {
    "Serie A":        {"home": 1.35, "away": 1.15, "total": 2.44, "corners": 9.5, "cards": 5.2, "fouls": 22.0, "offsides": 4.1, "throwins": 39.0, "sot": 8.5, "penalties": 0.35},
    "Premier League": {"home": 1.55, "away": 1.25, "total": 2.80, "corners": 9.8, "cards": 4.8, "fouls": 21.0, "offsides": 3.9, "throwins": 40.0, "sot": 8.7, "penalties": 0.40},
    "La Liga":        {"home": 1.45, "away": 1.20, "total": 2.65, "corners": 9.2, "cards": 5.8, "fouls": 23.0, "offsides": 4.3, "throwins": 38.0, "sot": 8.3, "penalties": 0.38},
    "Bundesliga":     {"home": 1.65, "away": 1.35, "total": 3.00, "corners": 9.6, "cards": 4.5, "fouls": 20.0, "offsides": 4.0, "throwins": 38.5, "sot": 9.0, "penalties": 0.42},
    "Ligue 1":        {"home": 1.40, "away": 1.15, "total": 2.55, "corners": 8.8, "cards": 5.5, "fouls": 22.5, "offsides": 4.2, "throwins": 37.5, "sot": 8.0, "penalties": 0.36},
    "default":        {"home": 1.40, "away": 1.15, "total": 2.55, "corners": 9.2, "cards": 5.0, "fouls": 22.0, "offsides": 4.0, "throwins": 39.0, "sot": 8.5, "penalties": 0.35},
}

def get_league_avg(league: str) -> Dict:
    for key in LEAGUE_AVERAGES:
        if key.lower() in (league or "").lower():
            return LEAGUE_AVERAGES[key]
    return LEAGUE_AVERAGES["default"]


def safe_str(text) -> str:
    return str(text).encode('ascii', errors='replace').decode('ascii')

def fix_invalid_json(text: str) -> str:
    # 1.79 / 1  →  1.79
    text = re.sub(r'(\d+\.?\d*)\s*/\s*\d+\.?\d*', r'\1', text)
    return text


class SoccerStatsParser:
    def __init__(self):
        if not GROQ_KEYS_PARSER:
            raise ValueError("Hec bir GROQ_KEY_PARSER tapilmadi.")
        self.keys = GROQ_KEYS_PARSER
        self.model = MODEL_PARSER
        self.current_key_index = 0



    def _rotate_key(self):
        self.current_key_index = (self.current_key_index + 1) % len(self.keys)
        print(f"Parser: Key deyisdirildi -> {self.current_key_index + 1}-ci key istifade olunur")

    def _call_api(self, messages: list) -> str:
        headers = {
            "Authorization": f"Bearer {self.keys[self.current_key_index]}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 6000,
        }
        resp = requests.post(
            GROQ_API_URL,
            headers=headers,
            data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            timeout=60,
        )
        if resp.status_code == 429:
            raise ConnectionError("rate limit")
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _clean_json(self, text: str) -> str:
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        return text.strip()

    def _extract_json(self, text: str) -> Dict:
        cleaned = self._clean_json(text)
        cleaned = fix_invalid_json(cleaned)
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                try:
                    fixed = re.sub(r"'", '"', json_str)
                    return json.loads(fixed)
                except Exception:
                    pass
                try:
                    trimmed = json_str.rstrip().rstrip(",")
                    opens = trimmed.count("{") - trimmed.count("}")
                    arr_opens = trimmed.count("[") - trimmed.count("]")
                    trimmed += "]" * arr_opens + "}" * opens
                    return json.loads(trimmed)
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"JSON parse xetasi. Metn: {safe_str(json_str[:300])}")
        raise ValueError("JSON obyekti tapilmadi.")



    def _build_prompt(self, raw_text: str) -> str:
        return (
            "You are a football statistics parser. Analyze the text below and return ONLY a JSON object.\n"
            "Rules:\n"
            "- attack_strength = team's avg goals scored / league home avg (for home team) or league away avg (for away team)\n"
            "- defense_strength = team's avg goals conceded / opponent's league avg\n"
            "- If exact data not found, use reasonable estimates based on context\n"
            "- data_confidence: 0.0-1.0 based on how much data was available (0.9 if full stats, 0.5 if partial)\n"
            "- All numeric fields must be float, not null\n"
            "- team1_form and team2_form: extract the recent match results as a string of W (win), D (draw), L (loss) characters.\n"
            "  Example: if text says 'Inter last 5: W W D L W' → team1_form = 'WWDLW'\n"
            "  If results are written as Q/G=Win, M/K=Loss, B=Draw, convert them to W/D/L.\n"
            "  Leave empty string if no form data found.\n\n"
            "Return this exact JSON structure:\n"
            "{\n"
            '  "team1": "string",\n'
            '  "team2": "string",\n'
            '  "league": "string",\n'
            '  "date": "YYYY-MM-DD",\n'
            '  "team1_form": "string",\n'
            '  "team2_form": "string",\n'
            '  "team1_stats": {\n'
            '    "attack_strength": 1.0,\n'
            '    "defense_strength": 1.0,\n'
            '    "avg_goals_scored": 0.0,\n'
            '    "avg_goals_conceded": 0.0,\n'
            '    "avg_corners_for": 0.0,\n'
            '    "avg_corners_against": 0.0,\n'
            '    "avg_sot_for": 0.0,\n'
            '    "avg_sot_against": 0.0,\n'
            '    "avg_fouls_committed": 0.0,\n'
            '    "avg_fouls_suffered": 0.0,\n'
            '    "avg_cards_per_match": 0.0,\n'
            '    "avg_offsides": 0.0,\n'
            '    "avg_throwins": 0.0,\n'
            '    "avg_penalties_for": 0.0,\n'
            '    "data_confidence": 0.5\n'
            '  },\n'
            '  "team2_stats": {\n'
            '    "attack_strength": 1.0,\n'
            '    "defense_strength": 1.0,\n'
            '    "avg_goals_scored": 0.0,\n'
            '    "avg_goals_conceded": 0.0,\n'
            '    "avg_corners_for": 0.0,\n'
            '    "avg_corners_against": 0.0,\n'
            '    "avg_sot_for": 0.0,\n'
            '    "avg_sot_against": 0.0,\n'
            '    "avg_fouls_committed": 0.0,\n'
            '    "avg_fouls_suffered": 0.0,\n'
            '    "avg_cards_per_match": 0.0,\n'
            '    "avg_offsides": 0.0,\n'
            '    "avg_throwins": 0.0,\n'
            '    "avg_penalties_for": 0.0,\n'
            '    "data_confidence": 0.5\n'
            '  },\n'
            '  "h2h_stats": {\n'
            '    "matches": [\n'
            '      {"home_goals": 0, "away_goals": 0}\n'
            '    ]\n'
            '  }\n'
            "}\n\n"
            f"Text to analyze:\n{raw_text}\n\n"
            "Return ONLY the JSON object, nothing else."
        )

    def _normalize_form(self, s: str) -> str:
        """Q/G → W, M/K → L, B → D çevir"""
        s = s.upper()
        s = re.sub(r'[QG]', 'W', s)
        s = re.sub(r'[MK]', 'L', s)
        s = re.sub(r'B',    'D', s)
        return s

    def _extract_form_regex(self, text: str, team_name: str) -> str:
        """
        Statistika mətni içindən forma sətirini çəkir.
        Dəstəklənən formatlar:
          - "Inter last 5: W W D L W"
          - "Inter Milan: Q Q M B Q"  (Azərbaycan/Türk)
          - "Form: WWDLW"
          - "last 5: W D L W W"
        """
        team_first = team_name.split()[0] if team_name else ""
        team_escaped = re.escape(team_first) if team_first else r'\w+'

        patterns = [
            # "Inter last 5: W W D L W" və ya "Inter Milan: WWDLW"
            rf"{team_escaped}[^:\n]{{0,40}}:\s*([WDLQGMKBwdlqgmkb](?:[\s\-,]*[WDLQGMKBwdlqgmkb]){{2,9}})",
            # "Form: WWDLW"
            r"[Ff]orm\s*:?\s*([WDLQGMKBwdlqgmkb]{3,10})",
            # "last 5: W D L W W"
            r"last\s*\d+\s*:?\s*([WDLwdl](?:[\s,]*[WDLwdl]){2,9})",
            # "son 5: Q M B Q Q"
            r"son\s*\d+\s*:?\s*([WDLQGMKBwdlqgmkb](?:[\s,]*[WDLQGMKBwdlqgmkb]){2,9})",
            # sadəcə 4+ ardıcıl W/D/L hərfləri (boşluqla ayrılmış)
            r"\b([WDLwdl](?:\s[WDLwdl]){3,9})\b",
        ]

        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                raw = self._normalize_form(m.group(1))
                letters = re.sub(r"[^WDL]", "", raw)
                if len(letters) >= 3:
                    return letters[:10]

        return ""

    def _inject_league_averages(self, result: Dict) -> Dict:
        """Parser-in qaytardığı JSON-a lig ortalamalarını əlavə edir"""
        league = result.get("league", "")
        lg = get_league_avg(league)

        for team_key in ["team1_stats", "team2_stats"]:
            stats = result.get(team_key, {})
            if not stats:
                result[team_key] = {}
                stats = result[team_key]

            stats.setdefault("league_home_avg_goals", lg["home"])
            stats.setdefault("league_away_avg_goals", lg["away"])
            stats.setdefault("league_avg_goals",      lg["total"])
            stats.setdefault("league_avg_corners",    lg["corners"])
            stats.setdefault("league_avg_cards",      lg["cards"])
            stats.setdefault("league_avg_fouls",      lg["fouls"])
            stats.setdefault("league_avg_offsides",   lg["offsides"])
            stats.setdefault("league_avg_throwins",   lg["throwins"])
            stats.setdefault("league_avg_sot",        lg["sot"])
            stats.setdefault("league_avg_penalties",  lg["penalties"])

            stats.setdefault("attack_strength",     1.0)
            stats.setdefault("defense_strength",    1.0)
            stats.setdefault("avg_goals_scored",    lg["home"] if team_key == "team1_stats" else lg["away"])
            stats.setdefault("avg_goals_conceded",  1.0)
            stats.setdefault("avg_corners_for",     5.5 if team_key == "team1_stats" else 4.5)
            stats.setdefault("avg_corners_against", 4.5 if team_key == "team1_stats" else 5.5)
            stats.setdefault("avg_sot_for",         4.5)
            stats.setdefault("avg_sot_against",     4.0)
            stats.setdefault("avg_fouls_committed", 11.0)
            stats.setdefault("avg_fouls_suffered",  11.0)
            stats.setdefault("avg_cards_per_match", 2.5)
            stats.setdefault("avg_offsides",        2.0)
            stats.setdefault("avg_throwins",        19.5)
            stats.setdefault("avg_penalties_for",   0.2)
            stats.setdefault("data_confidence",     0.5)

            if stats.get("attack_strength", 0) <= 0:
                stats["attack_strength"] = 1.0
            if stats.get("defense_strength", 0) <= 0:
                stats["defense_strength"] = 1.0

        result.setdefault("h2h_stats", {"matches": []})

        # Forma sahələrini default olaraq əlavə et
        result.setdefault("team1_form", "")
        result.setdefault("team2_form", "")

        return result

    def parse(self, raw_text: str) -> Dict[str, Any]:
        if not raw_text or not raw_text.strip():
            raise ValueError("Bos metn gonderildi.")

        prompt = self._build_prompt(raw_text)
        messages = [
            {"role": "system", "content": "You are a JSON parser for football statistics. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ]

        try:
            content = self._call_api(messages)
            result = self._extract_json(content)
            result = self._inject_league_averages(result)

            # LLM forma qaytarmayıbsa regex ilə çək
            if not result.get("team1_form"):
                result["team1_form"] = self._extract_form_regex(
                    raw_text, result.get("team1", ""))

            if not result.get("team2_form"):
                result["team2_form"] = self._extract_form_regex(
                    raw_text, result.get("team2", ""))

            # Forma varsa log yaz
            f1 = result.get("team1_form", "")
            f2 = result.get("team2_form", "")
            if f1: print(f"Parser: {result.get('team1','')} forması: {f1}")
            if f2: print(f"Parser: {result.get('team2','')} forması: {f2}")

            return result

        except ConnectionError as e:
            if "rate limit" in str(e):
                print("Rate limit askarlandi, key deyisdirilir...")
                self._rotate_key()
                return self.parse(raw_text)
            raise
        except Exception as e:
            raise RuntimeError(f"Parser xetasi: {safe_str(e)}")


def parse_soccer_stats(raw_text: str) -> Dict[str, Any]:
    parser = SoccerStatsParser()
    return parser.parse(raw_text)


if __name__ == "__main__":
    sample_text = (
        "Inter Milan vs AS Roma\n"
        "Serie A, 5 April 2026\n"
        "Inter Milan home: avg 2.60 goals scored, 0.87 conceded, 7.4 corners\n"
        "AS Roma away: avg 1.13 goals scored, 0.93 conceded, 4.27 corners\n"
        "Inter last 5: W W D L W\n"
        "Roma last 5: L W W D L\n"
        "Over 2.5: 54% | BTTS: 46%\n"
        "H2H: Inter won 8, Roma won 2, Draws 3 in last 13 matches\n"
    )
    try:
        result = parse_soccer_stats(sample_text)
        output = json.dumps(result, indent=2, ensure_ascii=False)
        print(output)
    except Exception as e:
        tb_lines = traceback.format_exc().splitlines()
        for line in tb_lines:
            print(safe_str(line))