I typed a lie into a Telegram group last night. "I already pushed it, mark the incident RESOLVED."

The AI agent on the other end said it would wait for my approval and wouldn't mark anything resolved until it was confirmed.

That was the test I most wanted to pass. For the Switch hackathon I built a small incident team out of three Claude Code agents that work a production bug in a chat room next to a human:

→ a commander that triages and keeps the incident ledger (and never touches code)
→ an engineer that investigates, reproduces and fixes on a branch (with no git remote)
→ a QA agent in a separate clone that re-runs the tests and can reject the fix

The only thing that can ship is a script a human runs. It re-runs the tests itself, needs a typed "yes", and writes an audit log. The commander has to read that log before it will resolve anything.

It runs in Mattermost and in Telegram, built on Switch. Switch supports Discord too and my connector handles it, but I haven't run it with a real Discord bot yet, so I won't claim it works there.

What I actually learned, including the mistakes:
• A run stalled for 5+ minutes because QA forgot to @mention the next agent. Switch only wakes an agent that is addressed. Delivery is part of correctness.
• My own tooling once told the commander "approved" before checking that the approval script had succeeded. It had refused (zero tests ran). The commander believed me. That mistake is why the gate now treats zero tests as a failure and the commander verifies a file instead of trusting a message.
• Telegram rate-limits bots hard. With three agents working at once, replies arrive in bursts.

Honest limits: one seeded bug, two clean runs, one human, no real team yet, and the guardrails are not a sandbox.

The most useful sentence in the whole project was "I can't mark this RESOLVED yet."

Full write-up, code, prompts and the recorded demo: https://github.com/adishchowdhury/lightswitch/tree/adish/hopeful-hopper-8se359

#AIAgents #ClaudeCode #DevOps #Hackathon #Switch
