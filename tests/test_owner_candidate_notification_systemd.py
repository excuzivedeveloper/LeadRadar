from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = (
    ROOT / "deploy/systemd/leadradar-owner-candidate-notifications.service"
)
TIMER_PATH = ROOT / "deploy/systemd/leadradar-owner-candidate-notifications.timer"


def _read_unit(path: Path) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = sections.setdefault(line[1:-1], {})
            continue
        if current is None or "=" not in line:
            continue
        key, value = line.split("=", 1)
        current[key] = value
    return sections


class OwnerCandidateNotificationSystemdTest(unittest.TestCase):
    def test_service_contract(self):
        service = _read_unit(SERVICE_PATH)
        unit = service["Unit"]
        service_section = service["Service"]

        self.assertEqual(
            unit["Description"], "LeadRadar bounded Owner candidate notifications"
        )
        self.assertEqual(service_section["Type"], "oneshot")
        self.assertEqual(
            service_section["WorkingDirectory"], "/opt/leadradar/LeadRadar"
        )
        self.assertEqual(
            service_section["EnvironmentFile"], "/opt/leadradar/runtime/.env"
        )
        self.assertEqual(service_section["TimeoutStartSec"], "30min")
        self.assertEqual(service_section["Restart"], "no")
        self.assertEqual(service_section["UMask"], "0077")

        exec_start = service_section["ExecStart"]
        self.assertEqual(
            exec_start,
            "/opt/leadradar/LeadRadar/.venv/bin/python "
            "-m freelancer_bot "
            "--owner-candidate-notifications "
            "--owner-candidate-notification-limit 5",
        )
        self.assertTrue(
            exec_start.startswith("/opt/leadradar/LeadRadar/.venv/bin/python ")
        )
        self.assertIn(" -m freelancer_bot ", exec_start)
        self.assertIn("--owner-candidate-notifications", exec_start)
        self.assertIn("--owner-candidate-notification-limit 5", exec_start)

    def test_service_excludes_unsafe_modes(self):
        text = SERVICE_PATH.read_text(encoding="utf-8")
        forbidden = (
            "--run",
            "--collector-only",
            "--bot-only",
            "freelancer_bot.operator_cli",
            "profile-discovery",
            "source-discovery",
            "telegram-discovery",
            "source-audit",
            "SOURCE_DISCOVERY_ENABLED",
            "SOURCE_AUDIT_ENABLED",
            "TELEGRAM_GLOBAL_DISCOVERY_ENABLED",
            "TELEGRAM_CHAT_DISCOVERY_ENABLED",
            "OPPORTUNITY_ANALYSIS",
            "AI_REPLY_ENABLED",
            "TELEGRAM_ALLOWED_USER_IDS",
            "DATABASE_URL=",
            "BOT_TOKEN",
            "API_HASH",
            "OPENROUTER_API_KEY",
        )
        for value in forbidden:
            self.assertNotIn(value, text)
        self.assertNotIn("EnvironmentFile=-", text)
        self.assertNotIn("python3", text)
        self.assertNotIn("uv run", text)
        self.assertNotIn("docker compose", text)
        self.assertNotIn("Restart=on-failure", text)
        self.assertNotIn("Restart=always", text)
        self.assertNotIn("RetrySec", text)

    def test_timer_contract(self):
        timer = _read_unit(TIMER_PATH)
        unit = timer["Unit"]
        timer_section = timer["Timer"]
        install = timer["Install"]

        self.assertEqual(
            unit["Description"],
            "Run LeadRadar Owner candidate notifications every 3 hours",
        )
        self.assertEqual(timer_section["OnCalendar"], "*-*-* 00/3:00:00 UTC")
        self.assertEqual(timer_section["Persistent"], "false")
        self.assertEqual(
            timer_section["Unit"],
            "leadradar-owner-candidate-notifications.service",
        )
        self.assertEqual(install["WantedBy"], "timers.target")

    def test_timer_has_single_calendar_authority(self):
        text = TIMER_PATH.read_text(encoding="utf-8")
        self.assertEqual(text.count("OnCalendar="), 1)
        self.assertNotIn("OnBootSec", text)
        self.assertNotIn("OnStartupSec", text)
        self.assertNotIn("OnUnitActiveSec", text)
        self.assertNotIn("Persistent=true", text)


if __name__ == "__main__":
    unittest.main()
