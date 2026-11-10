"""Record the backup demo video (Output 6): the same story as the live demo, with captions.

Needs the system running and prepared (sh tools/prepare_demo.sh), Playwright (pip install playwright) and
Chrome. Run from the project folder:

    python tools/record_demo.py --out docs/report/demo

It logs in as C01, starts P001's scripted deterioration in the background, and shows: readings arriving, the
Critical alert to the assigned clinician, acknowledging it, a refused look at another clinician's patient,
setting a personal limit, and the admin's audit log. Passwords come from .env.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

URL = "http://localhost:8080"


def caption(page: Page, text: str, seconds: float = 3.0) -> None:
    """Show a caption bar at the bottom of the page, then wait."""
    page.evaluate(
        """text => {
            let bar = document.getElementById('demo-caption');
            if (!bar) {
                bar = document.createElement('div');
                bar.id = 'demo-caption';
                bar.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:9999;padding:14px 24px;' +
                  'background:rgba(11,11,11,.86);color:#fff;font:600 18px system-ui,sans-serif';
                document.body.appendChild(bar);
            }
            bar.textContent = text;
        }""",
        text,
    )
    page.wait_for_timeout(int(seconds * 1000))


def log_in(page: Page, user: str, password: str) -> None:
    page.goto(URL)
    page.get_by_label("Clinician ID").fill(user)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()
    page.get_by_text("Open alerts").wait_for()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/report/demo")
    args = parser.parse_args()
    load_dotenv()
    clinician_pw, admin_pw = os.environ["DEMO_CLINICIAN_PASSWORD"], os.environ["DEMO_ADMIN_PASSWORD"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw = out / "raw"

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=str(raw),
            record_video_size={"width": 1280, "height": 800},
        )
        page = context.new_page()

        page.goto(URL)
        caption(page, "Smart Vitals: simulated patients, monitored every minute. Prototype, not a medical device.", 4)
        log_in(page, "C01", clinician_pw)
        caption(page, "Clinician C01 signs in and sees only their own 10 patients, most urgent first.", 5)

        story_log = (out / "story.log").open("w")
        story = subprocess.Popen(
            ["sh", "tools/prepare_demo.sh", "story"],  # noqa: S607 (the project's own script)
            stdin=subprocess.DEVNULL,
            stdout=story_log,
            stderr=subprocess.STDOUT,
        )
        page.goto(f"{URL}/#/patients/P001")
        page.get_by_text("Patient P001").wait_for()
        page.get_by_role("button", name="1 h").click()
        caption(page, "Patient P001: one chart per vital. New readings arrive over MQTT every few seconds.", 6)
        caption(page, "A sensor dropout and an impossible heart rate (250) arrive: flagged, no alert.", 8)
        story_alert = page.locator(".alert-card", has_text="2026-01-05 03:1")  # the story's Critical minutes
        story_alert.first.wait_for(timeout=120000)
        caption(
            page, "SpO2 falls into the red band: ONE alert to C01, with the patient ID, the vitals and the time.", 7
        )
        story_alert.first.evaluate("el => el.scrollIntoView({block: 'center'})")
        caption(page, "The duplicate and the late message in the same story raised no second alert.", 5)
        story_alert.first.get_by_role("button", name="Acknowledge").click()
        caption(page, "C01 acknowledges the alert: reminders stop; it stays on record.", 5)
        story.wait(timeout=180)

        page.goto(f"{URL}/#/patients/P002")
        page.get_by_text("Not your patient").wait_for()
        caption(page, "P002 belongs to another clinician: the API refuses (403) and records the attempt.", 6)

        page.goto(f"{URL}/#/patients/P001")
        page.get_by_text("Alert limits for P001").scroll_into_view_if_needed()
        page.get_by_label("Vital").select_option("heart_rate")
        page.get_by_label("High limit").fill("110")
        page.get_by_label("Reason (required)").fill("post-op tachycardia watch")
        page.get_by_role("button", name="Save limits").click()
        page.get_by_role("cell", name="post-op tachycardia watch").wait_for()
        caption(page, "A personal alert limit for P001 only (R10): audited, with a reason.", 6)

        page.get_by_role("button", name="Sign out").click()
        log_in(page, "admin", admin_pw)
        page.goto(f"{URL}/#/audit")
        page.get_by_text("Audit log").first.wait_for()
        caption(page, "The admin's audit log: every login, view, change and refused access.", 7)
        caption(page, "End of demo. Code, tests and evidence: github.com/masudrana7609-sketch/Smart-Vitals", 4)

        video = page.video.path()
        context.close()
        browser.close()

    target = out / "smart-vitals-demo.webm"
    shutil.move(video, target)
    shutil.rmtree(raw, ignore_errors=True)
    print(f"saved {target} ({target.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
