"""T-0052 UI tabs (partial, PR 6-lite): the tabs appear in order; the Brief tab shows the system vs state peers vs
national table with 'not available' rows; the Talking points tab has one checkbox per point. AppTest, SYNCP000025.
Mutation: tabs (the Talking points tab dropped)."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_tabs_table_and_talking_points_render():
    at = AppTest.from_file(APP, default_timeout=240).run()
    at.selectbox(key="system").set_value("SYNCP000025").run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Brief", "Talking points", "Contract Q&A", "Visit record",
                                          "Integration (dry run)"]  # v0.2-f adds the dry-run tab last (T-0080)
    table = next(d.value for d in at.dataframe if "metric" in d.value.columns)
    assert list(table.columns)[:2] == ["metric", "system"]
    cells = table.astype(str).to_numpy().ravel().tolist()
    assert any(c.startswith("not available: ") for c in cells)
    metrics = " | ".join(table["metric"].astype(str))
    assert "HepB Ped" in metrics and "Influenza to Tdap" in metrics and "older" not in metrics
    boxes = at.checkbox
    assert len(boxes) >= 5 and boxes[0].label.startswith("Size: ") and boxes[-1].label.startswith("Question to ask")
    assert any(b.label.startswith("Must cover: ") for b in boxes)
