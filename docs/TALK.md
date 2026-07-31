# Stage runbook

The demo is three tools and one idea: a model that can only talk is a search box, and a model with hands is an assistant.

```bash
make install
make run Q="how's the air in Karachi right now?"
```

If geocoding is unreachable the agent falls back to built-in coordinates for Karachi, Lahore and Islamabad, so the demo survives, but the two open-meteo endpoints and aladhan still need to be reachable.

## the tool is just a function

Open `src/karachi_agent/tools/weather.py`. It is one decorated function with a docstring. Then:

```bash
make tools
```

That prints the JSON schema the model sees. The description is the docstring; the `city` property with its default came from the type hint. Nobody wrote that JSON.

## one tool, one answer

```bash
make run Q="how's the air in Karachi right now?"
```

`--trace` shows the tool call on stderr as it happens. Point out that the tool returns a banded category and guidance, not just a number, and that the banding is a table in `tools/scales.py`, not the model's opinion.

## the compound question

This is the demo. Everything before it was setup.

```bash
make run Q="Can I take the kids to Seaview after Maghrib? Consider the air too."
```

Three tools, one turn, one joined-up recommendation. Nobody wrote an orchestration graph: the model read three descriptions and worked out that this question needs all three. `agent.py` is about forty lines, and most of them are the docstring.

## it has a clock now, and it speaks Urdu

```bash
make run Q="Maghrib mein kitna time hai?"
```

Two points. It answers in Roman Urdu because the prompt says to match the user's language. And it can answer "how long until" at all only because `get_prayer_times` returns `local_time`: the model has no clock, so you have to hand it one. Without that field it invents a plausible number.

## what happens when an API is down

Every tool returns `{"ok": false, "error": {...}}` rather than raising, so a failure is something the model can reason about. Break it on purpose:

```bash
KARACHI_AGENT_HTTP_TIMEOUT=0.001 uv run karachi-agent --trace \
  "what's the weather and air quality in Karachi?"
```

The agent reports what is unavailable instead of dying or inventing numbers.

## same code, hosted

```bash
make serve
```

Deploy with `make deploy`, which is `bunx @aws/agentcore deploy`.

## Closing point

The interesting work in an agent is not the model call. It is the tool layer:
shaping payloads so you are not paying for eight pollutants you will not mention, encoding the published tables so the model is not guessing what AQI 165 means, returning failures instead of raising, and telling the model what time it is. The model is the easy part now. The hands are the engineering.

## Questions I've seen surface

**Why not one tool that returns everything?** Because then the model cannot choose. A prayer times question would pay for an air quality call every time, and the model loses the ability to tell the user which single thing is unavailable.

**What does it cost?** Three tool calls and a couple of model turns per compound question, on Sonnet. The data APIs are free and keyless. The largest cost lever is payload size, which is why the tools return trimmed dictionaries.

**How do you stop it hallucinating a prayer time?** You cannot stop it, you can only remove the incentive: the tool always supplies the value, the prompt forbids answering from memory, and the failure path gives it something honest to say when the tool is down.

**Why Strands rather than LangGraph?** For this shape of problem there is no graph worth drawing. Three independent tools and a model that picks among them is exactly what the model-driven loop is good at. A graph earns its keep when you need deterministic control flow, and here that would be a constraint, not a feature.
