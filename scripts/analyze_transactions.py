import json
import sys
from collections import defaultdict

def analyze_transactions(transactions_file: str, expected_recipients: list, non_recipients: list):
    """
    Analyzes the transactions.json file to verify distribution.
    """
    try:
        with open(transactions_file, 'r') as f:
            transactions = json.load(f)
    except FileNotFoundError:
        print(f"Error: Transactions file not found at {transactions_file}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {transactions_file}")
        sys.exit(1)

    print(f"Total transactions recorded: {len(transactions)}")

    recipient_counts = defaultdict(int)
    recipient_amounts = defaultdict(float)
    all_recipients_in_transactions = set()

    for tx in transactions:
        recipient_id = tx.get("recipient_id")
        amount = tx.get("amount", 0.0)

        if recipient_id:
            recipient_counts[recipient_id] += 1
            recipient_amounts[recipient_id] += amount
            all_recipients_in_transactions.add(recipient_id)
        else:
            print(f"Warning: Transaction {tx.get('tx_hash')} has no recipient_id.")

    print("\n--- Transaction Summary ---")
    for recipient_id in sorted(recipient_amounts.keys()):
        print(f"Recipient {recipient_id}: {recipient_counts[recipient_id]} transactions, Total amount: {recipient_amounts[recipient_id]:.4f} XMR")

    print("\n--- Verification ---")
    # 1. Verify that only the 10 designated recipients received transactions.
    unexpected_recipients = all_recipients_in_transactions - set(expected_recipients)
    if not unexpected_recipients:
        print(f"PASS: No unexpected recipients found. All {len(all_recipients_in_transactions)} recipients are from the expected list.")
    else:
        print(f"FAIL: Unexpected recipients found: {unexpected_recipients}")

    # 2. Confirm that the 5 non-recipient non-miners did not receive any distributions.
    non_recipients_who_received = all_recipients_in_transactions.intersection(set(non_recipients))
    if not non_recipients_who_received:
        print(f"PASS: None of the designated non-recipients ({', '.join(non_recipients)}) received any transactions.")
    else:
        print(f"FAIL: The following non-recipients received transactions: {non_recipients_who_received}")

    # 3. Verify all expected recipients received at least one transaction
    missing_expected_recipients = set(expected_recipients) - all_recipients_in_transactions
    if not missing_expected_recipients:
        print(f"PASS: All expected recipients ({', '.join(expected_recipients)}) received at least one transaction.")
    else:
        print(f"FAIL: The following expected recipients did NOT receive any transactions: {missing_expected_recipients}")

if __name__ == "__main__":
    transactions_file = "/tmp/monerosim_shared/transactions.json"
    
    # Define expected recipients (user005-user014)
    expected_recipients = [f"user{i:03d}" for i in range(5, 15)]
    
    # Define non-recipients (user015-user019)
    non_recipients = [f"user{i:03d}" for i in range(15, 20)]

    analyze_transactions(transactions_file, expected_recipients, non_recipients)