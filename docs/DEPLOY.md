# Deploying to AgentCore Runtime

`src/karachi_agent/runtime.py` already speaks the runtime's HTTP contract, so deploying is mostly plumbing. The `KarachiAgent/` directory is the AgentCore CLI project, generated once with `agentcore create` and committed.

## Before you start

You need AWS credentials, `bun`, and Claude Sonnet 4.6 enabled in your target region. The AgentCore CLI is run with `bunx @aws/agentcore`, never installed globally, so there is nothing to keep updated.

CDK has to be bootstrapped once per account and region, because the CLI deploys through CloudFormation:

```bash
bunx cdk bootstrap aws://<account>/<region>
```

Check the target it will use before you deploy. The CLI writes `KarachiAgent/agentcore/aws-targets.json` with your account id and region, and that file is gitignored on purpose: an account id does not belong in a public repo.

## Check it locally first

This runs the same entrypoint AgentCore will call, on the same port.

```bash
make serve
curl -s localhost:8080/ping
curl -s -N localhost:8080/invocations -H 'content-type: application/json' -d '{"prompt": "when is Maghrib in Karachi?"}'
```

You should get a health check and then a stream of `data:` lines. If that works, the deployed version will almost certainly work too.

## Deploy

```bash
make dry-run
make deploy
```

Both targets run `make package` first, which copies `src/karachi_agent` into the app directory. That copy is generated and gitignored, so `src/` stays the only source of truth.

The vendoring is not stylistic. The build resolves dependencies with `uv pip install --only-binary :all:`, which means wheels only, with source builds disabled. A `git+https://` dependency is always a source distribution, so it cannot work here. Declaring the deps as plain pinned wheels in `KarachiAgent/app/KarachiAgent/pyproject.toml` and shipping our own code as files is the way through. Keep those pins in step with the root `pyproject.toml`.

The first build is slow. It cross compiles for Graviton (`aarch64-manylinux2014`), so none of your macOS wheels are reusable and it fetches about 40 MB of Linux ARM64 wheels. Most of that wait is grpcio, pulled in by the OpenTelemetry distro. uv caches it, so every build after the first is quick.

## Invoke

```bash
make invoke Q="Can I walk at Seaview after Maghrib?"
```

That prints the answer and then a session id. Reuse it for follow-ups, because the runtime keeps one agent per session and that is what gives you conversation history:

```bash
cd KarachiAgent
bunx @aws/agentcore invoke --stream "and tomorrow evening?" --session-id <id>
bunx @aws/agentcore invoke   # no prompt opens an interactive chat
```

From Python, three things matter: the payload key is `prompt`, `runtimeSessionId` needs at least 33 characters, and the response is a `text/event-stream` rather than JSON, so concatenate the `data:` lines instead of parsing the whole body.

```python
import json, uuid, boto3

client = boto3.client("bedrock-agentcore", region_name="us-west-2")
resp = client.invoke_agent_runtime(
    agentRuntimeArn="<arn from: bunx @aws/agentcore status>",
    runtimeSessionId="demo-" + uuid.uuid4().hex,
    payload=json.dumps({"prompt": "when is Maghrib?"}).encode(),
    qualifier="DEFAULT",
)
for chunk in resp["response"]:
    for line in chunk.decode().splitlines():
        if line.startswith("data: "):
            print(json.loads(line[6:]), end="", flush=True)
```

## What it costs

Bedrock tokens are effectively the whole bill. A compound question that hits all three tools runs about three cents; a single tool question is closer to one. AgentCore compute is a rounding error next to that, because idle and I/O wait are free and this agent spends most of its time waiting on APIs.

There is no hourly charge for a deployed runtime that nobody is calling. Leaving it up between rehearsal and the talk costs close to nothing, so tear it down for tidiness rather than to save money.

## Cleanup

Deleting the CloudFormation stack takes the runtime, its IAM role, and the policy with it. The log group and the uploaded code zip are not part of the stack, so remove those separately.

```bash
aws cloudformation delete-stack --region <region> --stack-name AgentCore-KarachiAgent-default
aws cloudformation wait stack-delete-complete --region <region> --stack-name AgentCore-KarachiAgent-default

# the code zip, around 40 MB
aws s3 rm s3://cdk-hnb659fds-assets-<account>-<region>/ --recursive

# log group, which defaults to never expiring
aws logs delete-log-group --region <region> \
  --log-group-name /aws/bedrock-agentcore/runtimes/<runtime-id>-DEFAULT
```

Then confirm nothing survived:

```bash
aws bedrock-agentcore-control list-agent-runtimes --region <region>
```

Leave the `CDKToolkit` stack alone unless you are certain you own it. In a shared account other people deploy through the same bootstrap, and removing it breaks them. It costs nothing to keep: the assets bucket is empty once you clear the zip, the ECR repository stays empty because CodeZip builds never push an image, and the IAM roles and SSM parameter are free.

Redeploying later is just `make deploy` again. The wheel cache survives, so it will be much faster than the first time.
