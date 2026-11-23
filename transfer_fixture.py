"""Observe the existing single-edition reports for the transfer example."""
from contextlib import closing
import json
import sqlite3

from center.accept import accept
from center.handoff_export import export_report
from center.publish import initialize_center, publish
from station.intake import import_batch
from station.issue import initialize_station, issue
from station.revisions import revise

PIECES = [{"name": "panel-transfer", "vertices": [[0, 0], [2, 0], [0, 2]], "mass": "1"}]
CALIBRATIONS = {
    "old": {"panel-transfer": [[1, 0, 0], [0, 0, 0]]},
    "aligned": {"panel-transfer": [[1, 0, 0], [0, 0, 0]]},
    "crossed": {"panel-transfer": [[0, 1, 0], [0, 0, 0]]},
}
CUTS = (1, 1)
MARGINAL = ["3/4", "1/4", "0", "0"]


def observe():
    with closing(sqlite3.connect(":memory:")) as center:
        initialize_center(center)
        with closing(sqlite3.connect(":memory:")) as station:
            initialize_station(station, "transfer-example")
            batch = import_batch(station, PIECES)
            issued = []
            for label, calibration in CALIBRATIONS.items():
                revision = revise(station, batch, calibration)
                payload = issue(station, batch, revision)
                issued.append((label, json.loads(payload), accept(center, payload)))

        first = issued[0][1]
        if any(item[1]["body"] != first["body"] for item in issued):
            raise RuntimeError("Expected identical V1 mass evidence in the transfer example")
        if len({item[1]["issue_id"] for item in issued}) != len(issued):
            raise RuntimeError("Expected three distinct parent issuances")
        if len({item[2] for item in issued}) != len(issued):
            raise RuntimeError("Expected three distinct parent receipts")

        reports = {}
        for label, parent, receipt_id in issued:
            report_id = publish(center, receipt_id, *CUTS)
            report = json.loads(export_report(center, report_id))
            masses = [zone["mass"] for zone in report["zones"]]
            if masses != MARGINAL or report["receipt_id"] != receipt_id:
                raise RuntimeError(f"Unexpected V1 report for {label}: {report}")
            if report["provenance"]["body_sha256"] != parent["body_sha256"]:
                raise RuntimeError(f"V1 report lost receipt provenance for {label}")
            reports[label] = report
    return {"same_v1_body": True, "reports": reports}


if __name__ == "__main__":
    print(json.dumps(observe(), sort_keys=True))
