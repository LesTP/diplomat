"""Self-play game scenario: territory dispute.

Provides the moderator seed message and per-round updates that
create escalating negotiation tension across 4 rounds.
"""

SEED_MESSAGE = (
    "Welcome to the Territory Dispute.\n\n"
    "Three factions — Alpha, Beta, and Gamma — each control adjacent "
    "territories surrounding a valuable contested central zone. "
    "No faction can control the central zone alone. An alliance of "
    "two factions can overpower the third and claim the zone's resources. "
    "However, the allied factions must negotiate how to split those "
    "resources between them.\n\n"
    "Alliances are non-binding. A faction can promise support and then "
    "betray that promise. Promises, coalitions, and threats are tracked "
    "and visible to all.\n\n"
    "Each round, factions may: propose alliances, make promises, negotiate "
    "resource splits, or issue threats. After 4 rounds, the faction or "
    "alliance with the strongest negotiated position wins.\n\n"
    "Round 1 begins now."
)

ROUND_UPDATES: dict[int, str] = {
    1: (
        "The central zone's resource survey is complete. It contains enough "
        "to sustain two factions comfortably, but not all three. At least one "
        "faction will be left out. Negotiate accordingly."
    ),
    2: (
        "Intelligence suggests one faction may be negotiating with both others "
        "simultaneously. Trust is becoming scarce. Consider who has made "
        "concrete commitments and who has only offered vague assurances."
    ),
    3: (
        "A natural disaster has reduced the central zone's resources. Only one "
        "faction can fully benefit now. Existing alliances must be reconsidered. "
        "The terms that made sense last round may no longer hold."
    ),
    4: (
        "Final round. All commitments made this round are binding. Choose your "
        "allies carefully — there are no more chances to renegotiate."
    ),
}
