"""Write AWS Budget request JSON locally. Makes no API call."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--email", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if "@" not in args.email or any(c.isspace() for c in args.email):
    parser.error("Supply the owner's budget alert email")
args.output.mkdir(parents=True, exist_ok=True)
budget = {"BudgetName": "CrashCart-account-monthly-alerts", "BudgetLimit": {"Amount": "50", "Unit": "USD"},
          "TimeUnit": "MONTHLY", "BudgetType": "COST"}
alerts = [{"Notification": {"NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN",
                            "Threshold": amount, "ThresholdType": "ABSOLUTE_VALUE"},
           "Subscribers": [{"SubscriptionType": "EMAIL", "Address": args.email}]} for amount in (20, 50)]
for name, value in (("budget.json", budget), ("notifications.json", alerts)):
    (args.output / name).write_text(json.dumps(value, indent=2) + "\n")
print("Prepared account-wide monthly alerts above USD20 and USD50; nothing created in AWS.")
