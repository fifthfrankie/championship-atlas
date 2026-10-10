"""The one authoritative league table calculation. Order: points, goal difference, goals for.
Teams still level after that are flagged `tied` (EFL head-to-head rules are not applied)."""
from dataclasses import dataclass


@dataclass
class Row:
    team_id: int
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    gf: int = 0
    ga: int = 0
    adjustment: int = 0
    tied: bool = False

    @property
    def gd(self):
        return self.gf - self.ga

    @property
    def points(self):
        return 3 * self.won + self.drawn + self.adjustment


def table(team_ids, finished, adjustments=()):
    """finished: (home_id, away_id, home_goals, away_goals), regular league matches with both scores.
    adjustments: (team_id, points). Returns rows ordered best first."""
    rows = {t: Row(t) for t in team_ids}
    for h, a, hg, ag in finished:
        if hg is None or ag is None:
            raise ValueError("finished match without a score")
        for t, f, c in ((h, hg, ag), (a, ag, hg)):
            r = rows[t]
            r.played += 1
            r.gf += f
            r.ga += c
            r.won += f > c
            r.lost += f < c
            r.drawn += f == c
    for t, p in adjustments:
        rows[t].adjustment += p
    out = sorted(rows.values(), key=lambda r: (-r.points, -r.gd, -r.gf, r.team_id))
    for x, y in zip(out, out[1:]):
        if (x.points, x.gd, x.gf) == (y.points, y.gd, y.gf):
            x.tied = y.tied = True
    return out
