# Follow one paid order, from checkout to the answer

The public demo needs no keys. A new checkout and investigation uses your own accounts. Allow about five minutes once the accounts and keys are ready; checkout approval and model response times can take longer.

## No-account path

Open [CrashCart](https://crashcart.52.202.25.181.sslip.io/), choose **Follow a recorded case**, and switch between **Missed order** and **Recovered order (replay)**. These are saved PayPal Sandbox records. The repair uses the same payment and the same 60-second rule. No payment or model request happens on this public page.

For an executable local comparison, follow the README's clone and `./scripts/judge.sh` commands. Before this draft PR is merged, select its branch when cloning:

```sh
git clone --branch ship/devpost --single-branch https://github.com/himanshu748/crashcart.git
cd crashcart
./scripts/judge.sh
```

The normal README clone command targets the default branch after merge. It opens `http://127.0.0.1:8766/demo.html#investigation`. Press Ctrl+C to stop. Use `./scripts/judge.sh --no-open --port 8767` if that port is busy or there is no desktop browser. Python 3.11+ is required; Python 3.13.15 is tested.

## New Sandbox checkout and AI investigation

### 1. Prepare your accounts

In [PayPal Developer](https://developer.paypal.com/), create or use a **Sandbox Business** account and Sandbox app. Keep its client ID and secret private. Use a separate **Sandbox Personal** test buyer for approval; never use your real-money account. You also need an API key and enabled model supporting the OpenAI Responses API with JSON-schema output. The existing Modal/DeepSeek option is documented in [the investigator guide](investigator.md#authorization-and-configuration).

The core workspace needs Python 3.13.15 with SQLite and no package installation. Optional AG Studio/timing views are separate; their licence and Node build are not prerequisites for this checkout.

### 2. Configure privately

```sh
python3 -m crashcart setup
```

This creates a private `.env` and a local workspace access key. Edit these settings in that file; the placeholders below are not usable credentials:

```dotenv
PAYPAL_CLIENT_ID=<your-sandbox-app-client-id>
PAYPAL_CLIENT_SECRET=<your-sandbox-app-secret>
CRASHCART_MODEL_PROVIDER=openai
OPENAI_API_KEY=<your-own-api-key>
OPENAI_MODEL=<your-enabled-structured-output-model>
CRASHCART_ALLOW_SANDBOX=1
CRASHCART_ALLOW_MODEL=1
CRASHCART_PUBLIC_URL=http://127.0.0.1:8765
```

Keep the generated `CRASHCART_OPERATOR_TOKEN` in place. Never commit `.env`, buyer credentials or model keys. Model requests use your account; turn model access on only within your own allowance. This guide does not supply a shared paid service. Local checkout return URLs work on the same computer as the buyer's browser. Remote browsers need a separately configured reachable address.

### 3. Start both processes

```sh
python3 -m crashcart migrate
python3 -m crashcart serve
```

In a second terminal, from the same directory:

```sh
python3 -m crashcart worker
```

Open <http://127.0.0.1:8765>. Enter the generated workspace access key from `.env` into **Access key**, then choose **Sign in**. Both processes must use the same database; the default is `var/crashcart.sqlite3`.

### 4. Follow the order

1. Choose **New check**. Use the promise “One USD 29 workshop ticket within 60 seconds of confirmed payment.” Select the faulty merchant and the lost-payment-reply test. Use PayPal test mode.
2. Choose **Start test checkout**, open the PayPal approval link and approve with your Sandbox Personal buyer.
3. Return to CrashCart and explicitly confirm the approved payment. Do not start another checkout if a reply is lost.
4. Use **Check payment and delivery**. For the faulty store, check after the 60-second promise has elapsed: PayPal confirms the payment, while the store has no ticket.
5. Choose **Ask the assistant**. Watch the background investigation and its cited payment/ticket observations. The assistant proposes where to look; the fixed payment/delivery check decides the outcome. You can stop the case.
6. Compare the repair through the account-free recorded example. That comparison does not make a second payment.

Webhook registration, KERNEL and commercial Studio access are optional setup paths, not requirements for this core sequence. The submission video uses the existing 8 November execution and labels it recorded; producing that video makes no new payment or AI call.

## If something is missing

A key being saved does not prove connectivity. A missing or failed service stays unavailable; CrashCart must not substitute a successful payment or delivery. Keep the existing order and inspect its state before retrying an ambiguous operation. Stop both terminals with Ctrl+C when finished.
