# Empty-target experiment arm B

Experiment arm, not a published dataset. Keeps every v3 command row and a
random.Random(20261014) subsample of empty targets, in original order and
byte-identical. Empty count is floor(command_count * 85 / 915), so the
result is at most 8.5% empty. The manifest records every kept/dropped ID.
