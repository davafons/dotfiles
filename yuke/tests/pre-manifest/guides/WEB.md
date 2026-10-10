# Web search

The profile's `tools/web.js` registers `web_search` and `web_fetch`, backed by
Monid's Tinyfish `/search` and `/fetch` endpoints.

## Credentials

The tools use the first available credential:

1. `MONID_API_KEY` in Yuke's environment.
2. A plain-text `monid.key` file in the active profile directory, normally
   `~/.config/yuke/monid.key`. `XDG_CONFIG_HOME` and `YUKE_APPNAME` are respected.

Keep the key file outside this repository, as a regular local file (not a Stow
symlink), with permissions `0600`. Do not paste the key into tracked JavaScript,
documentation, or test fixtures. The tools read it on each request, so rotating
its contents does not require restarting Yuke. An environment override still
wins until it is unset in the launching environment.

Restart Yuke after installing tool-code changes. This profile also has a custom
`/reload` command that reloads `profile.js`, its tools, and plugins.

## Checks

```sh
node yuke/.config/yuke/tests/check-web.mjs
yuke check
```

The Node checks use fake credentials and mocked network responses; they do not
contact Monid. A live `web_search` or `web_fetch` call also checks authentication
and the remote API, and may incur normal Monid usage charges.
