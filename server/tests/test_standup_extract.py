"""Extraction: the model proposes, the code decides what is kept. The model is replaced by a fake answer, and the people
and work in these entries are made up."""
from datetime import date

import pytest

from standups.llm import extract, prompt
from standups.standup_db.reader import Submission

ENTRY = Submission(
    id=1, standup_date=date(2026, 10, 12), person_name="Asha", email="asha@example.org", slack_user_id="U1",
    last_week="- Finished the fixture drawings",
    this_week="- Start the weld jig design for the rear axle\n- Review the test plan with Meena by Wednesday",
    blockers="- Waiting on supplier confirmation for bracket samples",
    combined=None, raw_content="raw", is_late_reply=False, source="slackbot_modal",
)


def item(**over):
    base = {
        "title": "Design weld jig for rear axle", "description": "The jig design is ready for review.", "kind": "new",
        "assignee": "Asha", "due": None, "priority": "medium", "subtasks": [], "related_to": None,
        "evidence_quote": "Start the weld jig design for the rear axle",
    }
    return {**base, **over}


@pytest.fixture
def model(monkeypatch):
    """Returns the prompts it was sent, and answers with whatever items the test gives it."""
    sent = []

    def install(*items):
        def fake(text, schema):
            sent.append(text)
            return {"items": list(items)}
        monkeypatch.setattr(extract, "complete_json", fake)
        return sent
    return install


def test_a_good_item_is_kept_with_its_fields(model):
    sent = model(item(due="2026-10-14", priority="high", kind="deadline", subtasks=["  a ", "", "b"]))

    [s] = extract.extract(ENTRY, [])

    assert (s.title, s.kind, s.priority, s.due, s.assignee) == ("Design weld jig for rear axle", "deadline", "high", date(2026, 10, 14), "Asha")
    assert s.subtasks == ["a", "b"] and s.related_to is None
    assert "Submitter: Asha" in sent[0] and "2026-10-12 to 2026-10-16" in sent[0] and "(nothing yet)" in sent[0]


def test_a_weekday_in_the_entry_is_worked_out_by_the_code_not_taken_from_the_model(model):
    # The standup is Monday 12 Oct 2026. The model wrongly says 10 Oct for "by Wednesday"; the code says Wed 14 Oct.
    model(item(due="2026-10-10", due_text="by Wednesday"))

    [s] = extract.extract(ENTRY, [])

    assert s.due == date(2026, 10, 14)


def test_a_weekday_on_the_standups_own_day_is_that_day_and_a_later_week_is_not_assumed(model):
    model(item(due=None, due_text="Monday?"), item(title="Review test plan with Meena", evidence_quote="Review the test plan with Meena by Wednesday", due=None, due_text="Wednesday"))

    # "Monday?" is not in the entry, so it is ignored and there is no date; the second one is found.
    first, second = extract.extract(ENTRY, [])

    assert (first.due, second.due) == (None, date(2026, 10, 14))


@pytest.mark.parametrize("due,text,expected", [
    ("2026-10-20", None, date(2026, 10, 20)),  # no weekday: the model's date is kept
    ("2026-10-09", None, None),  # before the standup: not a deadline in it
    ("garbage", None, None),
    ("2026-10-20", "by next Tuesday-ish", date(2026, 10, 20)),  # a phrase that is not in the entry is ignored
], ids=["kept", "before the standup", "unreadable", "phrase not in the entry"])
def test_a_date_without_a_weekday_in_the_entry_is_the_models_if_it_is_not_before_the_standup(model, due, text, expected):
    model(item(due=due, due_text=text))

    [s] = extract.extract(ENTRY, [])

    assert s.due == expected


def test_an_item_whose_quote_is_not_in_the_entry_is_dropped(model):
    model(item(evidence_quote="Order twelve new fixtures from the vendor"), item(evidence_quote="weld jig"))

    assert extract.extract(ENTRY, []) == []  # the first is invented, the second has only two words


def test_a_quote_matches_even_with_bullets_case_and_spacing_changed(model):
    model(item(evidence_quote="- START the  weld jig design for the rear axle"))

    assert len(extract.extract(ENTRY, [])) == 1


def test_an_item_that_repeats_the_persons_tracked_work_is_dropped_but_another_persons_is_not(model):
    model(item())
    mine = extract.Tracked("Design the weld jig for rear axle", "In Progress", "Asha", mine=True)
    theirs = extract.Tracked("Design the weld jig for rear axle", "In Progress", "Ravi", mine=False)

    assert extract.extract(ENTRY, [mine]) == []
    assert len(extract.extract(ENTRY, [theirs])) == 1


def test_related_to_keeps_a_similar_item_and_only_a_real_tracked_title_counts(model):
    blocker = item(
        title="Get supplier confirmation for bracket samples", kind="blocker", priority="high",
        evidence_quote="Waiting on supplier confirmation for bracket samples", related_to="order bracket samples",
    )
    model(blocker, item(title="Review test plan with Meena", evidence_quote="Review the test plan with Meena by Wednesday", related_to="Not a tracked task"))
    tracked = [extract.Tracked("Order bracket samples", "In Progress", "Asha", mine=True)]

    first, second = extract.extract(ENTRY, tracked)

    assert first.related_to == "Order bracket samples"  # matched ignoring case, shown with the tracked title
    assert second.related_to is None


def test_two_items_that_mean_the_same_keep_only_the_first(model):
    model(item(), item(title="Design the weld jig for the rear axle"))

    assert len(extract.extract(ENTRY, [])) == 1


# Twelve titles with no words in common, so the "means the same thing" check never drops one of them.
TITLES = [
    "Calibrate torque sensor", "Draft supplier contract", "Review firmware release", "Order bracket samples",
    "Update DFMEA sheet", "Validate battery pack", "Prepare vibration report", "Book test rig",
    "Finalize harness routing", "Release cover drawing", "Audit paint line", "Schedule customer demo",
]


def twelve():
    quotes = [f"line number {n} about a distinct deliverable" for n in range(len(TITLES))]
    entry = Submission(**{**ENTRY.__dict__, "this_week": "\n".join(f"- {q}" for q in quotes)})
    return entry, [item(title=t, evidence_quote=q) for t, q in zip(TITLES, quotes)]


def test_at_most_ten_are_kept_in_the_order_the_model_ranked_them(model):
    entry, items = twelve()
    sent = model(*items)

    kept = extract.extract(entry, [])

    assert [s.title for s in kept] == TITLES[:10]
    assert "at most 10 tasks" in sent[0]


def test_an_item_that_fails_a_check_does_not_use_up_one_of_the_ten_places(model):
    entry, items = twelve()
    invented = item(title="Invented work item zzz", evidence_quote="a quote that is nowhere in the entry")
    model(invented, *items)

    assert [s.title for s in extract.extract(entry, [])] == TITLES[:10]


def test_bad_values_from_the_model_are_repaired_or_dropped(model):
    model(
        item(kind="nonsense", priority="urgent", due="next friday", assignee=""),
        item(title="", evidence_quote="Review the test plan with Meena by Wednesday"),
        item(description="  ", evidence_quote="Review the test plan with Meena by Wednesday"),
        "not an object",
    )

    [s] = extract.extract(ENTRY, [])

    assert (s.kind, s.priority, s.due, s.assignee) == ("new", "medium", None, "Asha")


def test_an_answer_without_a_list_of_items_gives_nothing(monkeypatch):
    monkeypatch.setattr(extract, "complete_json", lambda text, schema: {"items": "oops"})

    assert extract.extract(ENTRY, []) == []


def test_the_prompt_lists_tracked_work_with_status_and_owner(model):
    sent = model()

    extract.extract(ENTRY, [extract.Tracked("Order bracket samples", "In Progress", "Ravi", mine=False)])

    assert "- Order bracket samples (In Progress, Ravi)" in sent[0]


def test_the_entry_text_uses_the_sections_then_falls_back_to_combined_then_raw():
    assert extract.entry_text(ENTRY).startswith("LAST WEEK:\n- Finished the fixture drawings\n\nTHIS WEEK:")
    assert "BLOCKERS:\n- Waiting on supplier" in extract.entry_text(ENTRY)
    no_blockers = Submission(**{**ENTRY.__dict__, "blockers": " "})
    assert "BLOCKERS" not in extract.entry_text(no_blockers)
    combined_only = Submission(**{**ENTRY.__dict__, "this_week": None, "combined": "all in one"})
    assert extract.entry_text(combined_only) == "all in one"
    raw_only = Submission(**{**ENTRY.__dict__, "this_week": " ", "combined": None})
    assert extract.entry_text(raw_only) == "raw"


def test_the_prompt_fills_every_placeholder_and_has_a_stable_hash():
    filled = prompt.PROMPT.format(date="d", week_start="s", week_end="e", max_items=10, tracked="t", name="n", text="x")

    assert "{" not in filled and len(prompt.PROMPT_HASH) == 64
