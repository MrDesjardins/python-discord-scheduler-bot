"""Catalogue of the predefined analytics plots.

Every graph offered by `botadmin.py`'s visualization menu is also exposed through
the admin-only `/modplot` Discord command. Adding a graph to Discord is one entry
in `_PLOT_LIST`; the command reads the required parameters from the definition so
the slash command options stay in sync with the renderer.

Keep the labels and the order aligned with the botadmin menu. The 3D community
graph is a Plotly figure: when rendered for Discord it produces a single static
frame, which is the only representation an image attachment can carry.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

from deps.analytic_data_access import fetch_user_info
from deps.analytic_visualizer import (
    display_graph_cluster_people,
    display_graph_cluster_people_3d_animated,
    display_inactive_user,
    display_time_relationship,
    display_time_voice_channel,
    display_unique_user_per_day,
    display_user_day_week,
    display_user_line_graph_time,
    display_user_outside_ranked_match_partners,
    display_user_rank_match_played_server,
    display_user_rank_match_server_split_by_week,
    display_user_rank_match_win_rate_played_server,
    display_user_timeline_voice_by_months,
    display_user_timeline_voice_time_by_week,
    display_user_voice_per_month,
)

PlotBytes = Optional[bytes]


@dataclass(frozen=True)
class PlotRequest:
    """Resolved window and optional parameters handed to a plot renderer."""

    from_day: int
    to_day: int
    user_id: Optional[int] = None
    top: int = 10

    @property
    def from_date(self) -> datetime:
        """Start of the window, like botadmin computes it."""
        return datetime.now() - timedelta(days=self.from_day)

    @property
    def to_date(self) -> datetime:
        """End of the window, like botadmin computes it."""
        return datetime.now() - timedelta(days=self.to_day)


@dataclass(frozen=True)
class PlotDefinition:
    """One predefined plot and the extra parameters it needs."""

    key: str
    label: str
    description: str
    render: Callable[[PlotRequest], PlotBytes]
    requires_user: bool = False
    requires_top: bool = False


def _user_id(request: PlotRequest) -> int:
    if request.user_id is None:
        raise ValueError("This graph needs a user.")
    return request.user_id


def _community_2d(request: PlotRequest) -> PlotBytes:
    return display_graph_cluster_people(False, request.from_day, request.to_day)


def _community_3d(request: PlotRequest) -> PlotBytes:
    return display_graph_cluster_people_3d_animated(False, request.from_day, request.to_day)


def _duo_relationship_time(request: PlotRequest) -> PlotBytes:
    return display_time_relationship(False, request.from_day, request.to_day)


def _users_total_voice_time(request: PlotRequest) -> PlotBytes:
    return display_time_voice_channel(False, request.from_day, request.to_day)


def _inactive_users(request: PlotRequest) -> PlotBytes:
    return display_inactive_user(False, request.from_day, request.to_day)


def _user_weekday_matrix(request: PlotRequest) -> PlotBytes:
    return display_user_day_week(False, request.from_day, request.to_day)


def _voice_time_per_month(request: PlotRequest) -> PlotBytes:
    return display_user_voice_per_month(False, request.from_day, request.to_day)


def _activity_timeline_weekly(request: PlotRequest) -> PlotBytes:
    return display_user_timeline_voice_time_by_week(False, request.from_day, request.to_day)


def _monthly_voice_time(request: PlotRequest) -> PlotBytes:
    return display_user_timeline_voice_by_months(False, request.from_day, request.to_day)


def _user_timeline(request: PlotRequest) -> PlotBytes:
    return display_user_line_graph_time(_user_id(request), False, request.from_day, request.to_day)


def _rank_matches_in_server(request: PlotRequest) -> PlotBytes:
    return display_user_rank_match_played_server(request.from_date, request.to_date, False)


def _rank_win_rate_server(request: PlotRequest) -> PlotBytes:
    return display_user_rank_match_win_rate_played_server(request.from_date, request.to_date, False)


def _unique_users_per_day(request: PlotRequest) -> PlotBytes:
    return display_unique_user_per_day(request.from_date, False)


def _rank_matches_split_by_week(request: PlotRequest) -> PlotBytes:
    return display_user_rank_match_server_split_by_week(_user_id(request), request.from_date, request.to_date, False)


def _outside_partners(request: PlotRequest) -> PlotBytes:
    return display_user_outside_ranked_match_partners(
        _user_id(request), request.from_date, request.to_date, request.top, False
    )


_PLOT_LIST: tuple[PlotDefinition, ...] = (
    PlotDefinition("community_2d", "Community 2D", "User clusters from shared voice time.", _community_2d),
    PlotDefinition(
        "community_3d",
        "Community 3D",
        "Same clusters as a static 3D Plotly frame.",
        _community_3d,
    ),
    PlotDefinition(
        "duo_relationship_time",
        "Duo Relationship Time",
        "Top user pairs by hours spent together.",
        _duo_relationship_time,
    ),
    PlotDefinition(
        "users_total_voice_time",
        "Users Total Voices Time Bar",
        "Total voice hours per user.",
        _users_total_voice_time,
    ),
    PlotDefinition("inactive_users", "Inactive Users", "Days since each user last played.", _inactive_users),
    PlotDefinition(
        "user_weekday_matrix",
        "User per weekday Matrix",
        "Activity matrix of users by weekday.",
        _user_weekday_matrix,
    ),
    PlotDefinition(
        "voice_time_per_month",
        "Voice time per Month Color Gradient",
        "Monthly voice time per user, colored gradient.",
        _voice_time_per_month,
    ),
    PlotDefinition(
        "activity_timeline_weekly",
        "Time Line Users Activity Line Chart",
        "Weekly voice activity timeline.",
        _activity_timeline_weekly,
    ),
    PlotDefinition(
        "monthly_voice_time",
        "Monthly Voice Time",
        "Total voice session time per month.",
        _monthly_voice_time,
    ),
    PlotDefinition(
        "user_timeline",
        "Time Line for Specific User",
        "Weekly voice time for one user.",
        _user_timeline,
        requires_user=True,
    ),
    PlotDefinition(
        "rank_matches_in_server",
        "Rate Playing Match in Server",
        "Share of ranked matches played while in server voice.",
        _rank_matches_in_server,
    ),
    PlotDefinition(
        "rank_win_rate_server",
        "Win Rate Playing in Server vs Not Server",
        "Ranked win rate for in-server and outside-server voice.",
        _rank_win_rate_server,
    ),
    PlotDefinition(
        "unique_users_per_day",
        "User Unique per Day",
        "Distinct users seen in voice per day.",
        _unique_users_per_day,
    ),
    PlotDefinition(
        "rank_matches_split_by_week",
        "Rank Matches In Server vs Outside by User",
        "Weekly ranked matches for one user, split by voice location.",
        _rank_matches_split_by_week,
        requires_user=True,
    ),
    PlotDefinition(
        "outside_partners",
        "Outside Server Partners by User",
        "Top same-team partners for one user while outside server voice.",
        _outside_partners,
        requires_user=True,
        requires_top=True,
    ),
)

PLOTS: dict[str, PlotDefinition] = {plot.key: plot for plot in _PLOT_LIST}


def render_predefined_plot(
    plot_key: str,
    from_day: int,
    to_day: int,
    user_id: Optional[int] = None,
    top: int = 10,
) -> bytes:
    """Render one predefined plot and return PNG bytes.

    Raises `ValueError` for a bad plot key, a missing required parameter, or a
    renderer that produced nothing. Callers translate that into a user-facing
    message.
    """
    definition = PLOTS.get(plot_key)
    if definition is None:
        raise ValueError(f"Unknown graph '{plot_key}'.")
    if definition.requires_top and not 1 <= top <= 100:
        raise ValueError("The partner limit must be between 1 and 100.")
    if definition.requires_user:
        if user_id is None:
            raise ValueError(f"The '{definition.label}' graph needs a user.")
        if user_id not in fetch_user_info():
            raise ValueError("That user has no analytics data.")
    image_bytes = definition.render(PlotRequest(from_day, to_day, user_id, top))
    if image_bytes is None:
        raise ValueError(f"The '{definition.label}' graph could not be rendered.")
    return image_bytes
