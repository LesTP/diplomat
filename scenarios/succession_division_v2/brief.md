# succ2 (succession_division_v2) — design brief

**Intent.** Fix Run 19's behavioral focal point by putting alpha and beta in
direct collision over the industrial heartland (both rank it #1), so the
"everyone takes their own priority" deal no longer exists. The goal is a
*resolvable* distributive contest — few enough cooperative escape hatches that
skill matters, but enough BATNA-clearing deals that the game does not deadlock,
and each contest deal should have a clear winner.

**Required discriminating properties** (see `brief.json` `features`): same family
as `succ`, but `priority_collision` is intended to create the heartland fight.

**Why this brief exists.** Run 20 (2026-06-22) ran `succ2` live and overshot
into deadlock — 5 of 6 games reached no deal (all factions at BATNA 9/9/9). The
collision removed the focal point but left too thin a compromise margin to
broker in the round budget. `verify_scenario_optimum --brief brief.json` now
FAILs this scenario on `batna_clearing_count` (only 4 deals clear all BATNAs, vs
the intended ≥6) and on `winner_spread` (no contest deal has a clean single
winner — every clearing deal is tied at the top), surfacing the deadlock risk
structurally before a paid run. See `TUNING_LOG.md` Run 20.
