import json
import os
from pathlib import Path

# Define the path where you want to save the file
dialog_dir = Path(r"back_end\test_codes\test_dialogue")
dialog_dir.mkdir(parents=True, exist_ok=True)

# Define the number of turns you want
num_turns = 20

# Create test dialog with configurable number of turns
test_dialog = {
    "name": "License Obligations Flow",
    "description": "To test the ability of generating obligations for a system",
    "initial_state": "obligations",
    "turns": []
}

# First turn with different input
# first_turn = {
#     "user_input": "OK, show me the first subtitle",
#     "expected_status": "obligations",
#     "check_keys": ["generated_obligations"],
#     "verify_response_contains": ["license", "obligation"]
# }
# test_dialog["turns"].append(first_turn)

# Generate remaining turns with "ok, I am satisfied with it"
for i in range(1, num_turns):
    turn = {
        "user_input": "ok, let's move forward.",
        "expected_status": "obligations",
        "follow_up_if_continue": "Here's additional information about distribution"
    }
    test_dialog["turns"].append(turn)

# Save to file
dialog_path = dialog_dir / "test_obligations.json"
with open(dialog_path, 'w', encoding='utf-8') as f:
    json.dump(test_dialog, f, indent=2)

print(f"Test dialog file created with {num_turns} turns")
print(f"The file is saved in the path: {dialog_path}")