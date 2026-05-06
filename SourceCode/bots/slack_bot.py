"""
Slack bot integration — deferred.

When implemented, this should use Slack Socket Mode via the `slack-bolt` SDK
so no inbound HTTP endpoint is required (works behind a home router/Tailscale):

    pip install slack-bolt

Architecture notes:
- Use `slack_bolt.App` with `SocketModeHandler` from `slack_bolt.adapter.socket_mode`
- The app token (xapp-...) enables Socket Mode; the bot token (xoxb-...) handles API calls
- Run `SocketModeHandler(app, app_token).start()` in this thread
- Handle `@app.message()` events exactly like TelegramBot._handle_update()
- Map Slack user IDs (U...) to Oathweaver profiles via BotUserStore
- Discord message limit is 40,000 chars so chunking is rarely needed

Config keys in Runtime/config/bot_config.json:
    slack.enabled          — bool
    slack.bot_token        — xoxb-... (Bot User OAuth Token)
    slack.app_token        — xapp-... (App-Level Token, for Socket Mode)
    slack.signing_secret   — for request verification (optional in Socket Mode)
"""
