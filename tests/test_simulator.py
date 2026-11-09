"""Tests for the simulator (R1, R2, R9) and the shared labelling and risk rules. Run with: pytest"""

import numpy as np
import pandas as pd
import pytest

from simulator.cli import main, run_batch
from simulator.config import FaultRates, SimConfig
from src.labelling import BANDS, band_points, label
from src.risk import RISK_GROUPS, RISK_LEVEL, risk_group, risk_points
from src.vitals import VITALS, is_plausible

SMALL = SimConfig(n_patients=24, n_clinicians=3, days=1, seed=7)


@pytest.fixture(scope="module")
def batch():
    return run_batch(SMALL)


# --- Reproducibility ---------------------------------------------------------------------------


def test_same_seed_gives_identical_output(batch):
    again = run_batch(SMALL)
    for first, second in zip(batch, again, strict=True):
        pd.testing.assert_frame_equal(first, second)


def test_different_seed_gives_different_output(batch):
    other = run_batch(SimConfig(n_patients=24, n_clinicians=3, days=1, seed=8))
    assert not batch[2]["true_heart_rate"].equals(other[2]["true_heart_rate"])


# --- Patients (R1) -----------------------------------------------------------------------------


def test_every_patient_has_a_risk_group_and_a_clinician(batch):
    patients = batch[0]
    assert patients["risk_group"].isin(RISK_GROUPS).all()
    assert patients["clinician_id"].notna().all()
    assert patients["clinician_id"].nunique() >= 3


def test_risk_group_matches_the_documented_rule(batch):
    for _, p in batch[0].iterrows():
        conditions = [c for c in ("hypertension", "diabetes", "arrhythmia", "copd") if p[c]]
        points = risk_points(p["age_band"], conditions, p["admissions_12m"], bool(p["prior_critical_event"]))
        assert p["risk_points"] == points
        assert p["risk_group"] == risk_group(points)
        assert p["risk_level"] == RISK_LEVEL[p["risk_group"]]


def test_clinicians_share_patients_evenly(batch):
    counts = batch[0]["clinician_id"].value_counts()
    assert counts.max() - counts.min() <= 1


def test_risk_rule_bands():
    assert risk_group(risk_points("18-49", [], 0, False)) == "Low"
    assert risk_group(risk_points("65-79", ["hypertension"], 0, False)) == "Medium"  # 2 + 1 = 3
    assert risk_group(risk_points("80+", ["copd"], 1, False)) == "High"  # 3 + 2 + 1 = 6
    assert risk_points("50-64", [], 5, False) == 1 + 2  # admissions count at most 2 points
    with pytest.raises(ValueError):
        risk_points("90+", [], 0, False)


# --- Readings (R2) -----------------------------------------------------------------------------


def test_one_expected_reading_per_patient_per_minute(batch):
    truth = batch[2]
    assert len(truth) == SMALL.n_patients * SMALL.n_readings
    assert truth["msg_id"].is_unique


def test_glucose_is_null_for_patients_without_diabetes(batch):
    patients, delivered, truth = batch
    no_diabetes = patients.loc[patients["diabetes"] == 0, "patient_id"]
    assert len(no_diabetes) > 0
    assert delivered.loc[delivered["patient_id"].isin(no_diabetes), "glucose"].isna().all()
    assert truth.loc[truth["patient_id"].isin(no_diabetes), "true_glucose"].isna().all()


def test_glucose_is_present_for_patients_with_diabetes(batch):
    patients, delivered, truth = batch
    diabetic = patients.loc[patients["diabetes"] == 1, "patient_id"]
    assert len(diabetic) > 0
    rows = truth[truth["patient_id"].isin(diabetic)]
    assert rows["true_glucose"].notna().all()


def test_every_delivered_message_is_in_the_ground_truth(batch):
    _, delivered, truth = batch
    assert set(delivered["msg_id"]) <= set(truth["msg_id"])


def test_labels_are_the_three_classes(batch):
    assert set(batch[1]["status"]) <= {"Normal", "Warning", "Critical"}


# --- Faults (R9) -------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def faulty():
    """A bigger run with higher window-fault rates, so the rates can be measured."""
    rates = FaultRates(
        missing_vital=0.03, impossible=0.01, late=0.02, duplicate=0.02, silent_per_day=2.0, stuck_per_day=2.0
    )
    return run_batch(SimConfig(n_patients=40, days=1, seed=11, faults=rates)), rates


@pytest.mark.parametrize("fault", ["missing_vital", "impossible", "late", "duplicate"])
def test_per_reading_fault_rates_are_roughly_as_configured(faulty, fault):
    (_, _, truth), rates = faulty
    share = (truth["fault_type"] == fault).mean()
    assert share == pytest.approx(getattr(rates, fault), rel=0.3)


def test_window_faults_happen(faulty):
    (_, _, truth), _ = faulty
    assert (truth["fault_type"] == "silent").sum() > 0
    assert (truth["fault_type"] == "stuck").sum() > 0


def test_silent_readings_are_never_delivered(faulty):
    (_, delivered, truth), _ = faulty
    silent = set(truth.loc[truth["fault_type"] == "silent", "msg_id"])
    assert silent and not silent & set(delivered["msg_id"])


def test_duplicates_are_delivered_twice(faulty):
    (_, delivered, truth), _ = faulty
    duplicated = set(truth.loc[truth["fault_type"] == "duplicate", "msg_id"])
    counts = delivered["msg_id"].value_counts()
    assert set(counts[counts == 2].index) == duplicated


def test_late_messages_arrive_out_of_order(faulty):
    (_, delivered, truth), _ = faulty
    late = truth.loc[truth["fault_type"] == "late"]
    assert late["delay_minutes"].between(2, 15).all()
    measured = pd.to_datetime(delivered["measured_at"])
    assert (measured.diff().dt.total_seconds() < 0).any()  # some readings arrive after newer ones


def test_missing_vital_faults_leave_exactly_that_vital_empty(faulty):
    (_, delivered, truth), _ = faulty
    missing = truth[truth["fault_type"] == "missing_vital"].set_index("msg_id")
    rows = delivered.drop_duplicates("msg_id").set_index("msg_id").loc[missing.index]
    for msg_id, vital in missing["fault_vital"].items():
        assert np.isnan(rows.at[msg_id, vital])


def test_impossible_values_only_where_the_ground_truth_says_so(faulty):
    (_, delivered, truth), _ = faulty
    fault = delivered["msg_id"].map(truth.set_index("msg_id")["fault_type"])
    implausible = np.zeros(len(delivered), dtype=bool)
    for vital in VITALS:
        implausible |= ~is_plausible(vital, delivered[vital])
    assert implausible.any()
    assert (fault[implausible] == "impossible").all()
    assert implausible[(fault == "impossible").to_numpy()].all()


def test_stuck_sensor_repeats_one_value(faulty):
    (_, delivered, truth), _ = faulty
    stuck = truth[truth["fault_type"] == "stuck"].copy()
    assert stuck["fault_vital"].isin(VITALS).all()
    stuck["minute"] = stuck["msg_id"].str.split("-").str[1].astype(int)
    stuck = stuck.sort_values(["patient_id", "fault_vital", "minute"])
    # a new window starts when the patient, the vital or an unbroken run of minutes changes
    new_window = (
        stuck["patient_id"].ne(stuck["patient_id"].shift())
        | stuck["fault_vital"].ne(stuck["fault_vital"].shift())
        | stuck["minute"].diff().ne(SMALL.interval_minutes)
    )
    stuck["window"] = new_window.cumsum()
    feed = delivered.drop_duplicates("msg_id").set_index("msg_id")
    for _, rows in stuck.groupby("window"):
        vital = rows["fault_vital"].iloc[0]
        assert feed.loc[rows["msg_id"], vital].nunique(dropna=False) == 1


# --- Labelling rule (NEWS2-inspired) ---------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "points"), [(40, 3), (41, 1), (50, 1), (51, 0), (90, 0), (91, 1), (110, 1), (111, 2), (130, 2), (131, 3)]
)
def test_pulse_band_edges(value, points):
    assert band_points(value, BANDS["heart_rate"])[0] == points


@pytest.mark.parametrize(
    ("value", "points"), [(90, 3), (91, 2), (100, 2), (101, 1), (110, 1), (111, 0), (219, 0), (220, 3)]
)
def test_systolic_band_edges(value, points):
    assert band_points(value, BANDS["systolic_bp"])[0] == points


@pytest.mark.parametrize(
    ("value", "points"), [(35.0, 3), (35.1, 1), (36.0, 1), (36.1, 0), (38.0, 0), (38.1, 1), (39.0, 1), (39.1, 2)]
)
def test_temperature_band_edges(value, points):
    assert band_points(value, BANDS["temperature"])[0] == points


def test_spo2_scales():
    assert band_points([91, 92, 93, 94, 95, 96], BANDS["spo2_scale1"]).tolist() == [3, 2, 2, 1, 1, 0]
    assert band_points([83, 84, 85, 86, 87, 88, 92, 97], BANDS["spo2_scale2"]).tolist() == [3, 2, 2, 1, 1, 0, 0, 0]


def test_labels_from_scores():
    assert label(75, 97, 125, 36.8)[1][0] == "Normal"
    assert label(105, 93, 125, 36.8)[1][0] == "Warning"  # 1 + 2 = 3
    assert label(75, 90, 125, 36.8)[1][0] == "Critical"  # SpO2 91 or lower is a single red score
    assert label(115, 94, 105, 38.5)[1][0] == "Critical"  # 2 + 1 + 1 + 1 = 5
    assert label(75, 90, 125, 36.8, spo2_scale=2)[1][0] == "Normal"  # 88-92% is on target for Scale 2


def test_missing_value_scores_zero_and_glucose_bands():
    assert label(np.nan, 97, 125, 36.8)[1][0] == "Normal"
    assert label(75, 97, 125, 36.8, glucose=2.9)[1][0] == "Critical"
    assert label(75, 97, 125, 36.8, glucose=7.0)[1][0] == "Normal"


# --- Command line ------------------------------------------------------------------------------


def test_cli_batch_writes_the_three_files(tmp_path, capsys):
    assert main(["batch", "--patients", "4", "--days", "0.1", "--out", str(tmp_path)]) == 0
    for name in ("sim_patients.csv", "sim_vitals.csv", "sim_ground_truth.csv"):
        assert (tmp_path / name).stat().st_size > 0
    assert "status" in pd.read_csv(tmp_path / "sim_vitals.csv").columns
    assert "fault_type" not in pd.read_csv(tmp_path / "sim_vitals.csv").columns  # ground truth only


@pytest.mark.parametrize("mode", ["live", "scenario"])
def test_live_and_scenario_are_not_built_yet(mode):
    assert main([mode]) == 2
