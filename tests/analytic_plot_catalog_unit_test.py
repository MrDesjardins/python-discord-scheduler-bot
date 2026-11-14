"""Unit tests for the predefined analytics plot catalogue."""

import pytest

from deps.analytic_plot_catalog import PLOTS, render_predefined_plot


def test_botadmin_visualizations_are_all_exposed():
    assert len(PLOTS) == 15


def test_every_plot_has_a_unique_label_and_description():
    labels = [plot.label for plot in PLOTS.values()]
    assert len(labels) == len(set(labels))
    assert all(plot.description for plot in PLOTS.values())


def test_only_the_expected_plots_need_extra_parameters():
    assert {key for key, plot in PLOTS.items() if plot.requires_user} == {
        "user_timeline",
        "rank_matches_split_by_week",
        "outside_partners",
    }
    assert {key for key, plot in PLOTS.items() if plot.requires_top} == {"outside_partners"}


def test_unknown_plot_is_rejected():
    with pytest.raises(ValueError, match="Unknown graph"):
        render_predefined_plot("not_a_plot", 30, 0)


def test_per_user_plot_without_a_user_is_rejected_before_querying():
    with pytest.raises(ValueError, match="needs a user"):
        render_predefined_plot("user_timeline", 30, 0)


def test_partner_limit_is_validated():
    with pytest.raises(ValueError, match="between 1 and 100"):
        render_predefined_plot("outside_partners", 30, 0, user_id=1, top=0)
