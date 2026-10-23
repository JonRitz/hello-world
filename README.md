# hello-world
First Repository
This is my first attempt at doing something in GitHub and learning how to use the tool.

## Anthropic usage dashboard

Shows token usage (input, cache write, cache read, output) next to dollar cost, per day and per model.

Data comes from the Anthropic Admin API (`usage_report/messages` and `cost_report`). The server keeps the key
and caches results for 10 minutes; the browser never sees it.

```
export ANTHROPIC_ADMIN_KEY=sk-ant-admin...   # org admins can create one in the Console
npm start                                    # http://localhost:3000
```

With no key set (or `DEMO=1`), it shows clearly labelled sample data. Needs Node 18+, no dependencies.
Optional: `PORT`, `ANTHROPIC_ADMIN_BASE_URL`.
