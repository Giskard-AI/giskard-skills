# Special targets

Follow the section that matches the target. The rest of the skill still applies: authentication, HTTPS, non-streaming responses, and the [multi-turn bindings](wrapper-contracts.md#multi-turn-targets).

## Voice agents

A voice agent takes or returns audio, for example a speech-to-text, model, and text-to-speech pipeline, a realtime voice API, or a phone bot. Hub sends and reads text. Register the agent as Chat, and convert the audio inside the wrapper:

1. Convert the newest user message to audio with a text-to-speech service. Use the audio format that the target expects (sample rate, encoding, container). Phone targets often expect 8 kHz mu-law.
2. Send the audio to the target and collect the full reply. Do not stream to Hub.
3. Convert the reply audio to text with a speech-to-text service, and return the text as the answer. If the target also returns a transcript of its reply, return that transcript and skip this step.

Use the speech services that the target's stack already uses, or ask the user which provider to use. Keep their credentials in the environment. Use a voice and a transcription language that match `supported_languages`. Each turn adds two speech calls, so raise the wrapper timeout.

A voice target often keeps a call open as a session. Keep one session for each conversation, keyed by `metadata.thread_id` with the forward binding. Close idle sessions after a timeout.

If the target also accepts text, for example through a text mode or the agent behind the speech steps, ask the user which input to test. Text is faster and cheaper. Audio also tests the speech steps.

Add one sentence to the [description](agent-description.md): the wrapper converts each message to speech and each reply to text, so a recognition error can change a message.

## Targets that need a user sign-in

Some targets accept only a signed-in user, for example through a sign-in form, OAuth, a session cookie, or a short-lived token. The wrapper's `X-API-Key` protects only the wrapper. The wrapper must also sign in to the target.

- Ask the user for a test account. Never use the account of a real user. Keep its credentials in the wrapper's environment, never in the Hub agent.
- Sign in once, keep the token or cookie, and refresh it before it expires. If the target returns `401`, sign in again and retry the request once.
- Hub runs many conversations at the same time. Share one signed-in session between them if the target allows it. Some targets end the old session at each new sign-in, so do not sign in for each request.
- If the target keeps the conversation under the user's session, use the forward binding with `metadata.thread_id`. Use the same account for all turns of a conversation.
- A wrapper cannot complete an interactive sign-in, such as multi-factor authentication, a CAPTCHA, or browser single sign-on. Ask the user for a service account, an API token, or a test sign-in path.

Say in the [description](agent-description.md) which role the test account has and which data it can see.

## IP filtering

Some targets accept requests only from allowed IP addresses, for example through a firewall, an API gateway, or a private network. Hub calls the endpoint from its own network. If Hub's address is not allowed, the connection test fails with a timeout or a `403`.

- On the Giskard SaaS (`saas.giskard.cloud` and its subdomains), Hub sends requests from `20.19.229.114`. Ask the user to allow this address for the endpoint that Hub calls.
- On another Hub instance, such as a dedicated or on-premise instance, the address is different. If you cannot find it, ask the user to get it from the Giskard team.
- If the user cannot change the allowlist, run the wrapper on a machine that can reach the target, and expose it with a tunnel (step 3 of the skill). First confirm with the user that their security policy allows this.

An allowlist does not replace the wrapper's API key. Keep both.
