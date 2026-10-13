#!/usr/bin/env python3
"""Read provider allowances without a model call or a credential write."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import stat
import time
import urllib.error
import urllib.request

MAX_BYTES = 262144


class StatusError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise StatusError("Quota endpoint redirected. Credentials were not forwarded.")


def read_providers(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return []
    except OSError:
        raise StatusError("Cannot read providers.json. Use a private regular file, not a symlink.") from None
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid():
            raise StatusError("providers.json must be owned by you with mode 0600.")
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise StatusError("providers.json exceeds the status reader size limit.")
    try:
        providers = json.loads(data)["providers"]
        if not isinstance(providers, list) or not all(isinstance(row, dict) for row in providers):
            raise ValueError()
        return providers
    except (ValueError, KeyError, TypeError, UnicodeError):
        raise StatusError("Cannot parse providers.json. Run yuke check.") from None


def read_json(url, headers):
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=10) as response:
            body = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        hints = {401: "Login expired or key rejected. Use /login for this provider.",
                 403: "The provider denied quota access.",
                 429: "The quota endpoint is rate limited. Try again later."}
        raise StatusError(hints.get(error.code, "Quota request failed.") + f" (HTTP {error.code})") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise StatusError("Cannot reach the quota endpoint. Try again later.") from None
    if len(body) > MAX_BYTES:
        raise StatusError("Quota response exceeds the status reader size limit.")
    try:
        result = json.loads(body)
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except (ValueError, UnicodeError):
        raise StatusError("The provider returned an invalid quota response.") from None


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def clean(value):
    if not isinstance(value, str):
        return ""
    return "".join(char if char.isprintable() else " " for char in value)[:160]


def codex_snapshot(data):
    windows = []
    groups = [("Codex", data.get("rate_limit"))]
    for item in data.get("additional_rate_limits") or []:
        if isinstance(item, dict):
            groups.append((clean(item.get("limit_name")) or clean(item.get("metered_feature")) or "Additional limit", item.get("rate_limit")))
    notes = ["Codex allowances and credits are not an exact remaining-token balance."]
    for group, limits in groups:
        if not isinstance(limits, dict):
            continue
        if limits.get("limit_reached") is True or limits.get("allowed") is False:
            notes.append(group + " reports that its allowance is exhausted or unavailable.")
        for field in ("primary_window", "secondary_window"):
            window = limits.get(field)
            if not isinstance(window, dict):
                continue
            used = window.get("used_percent")
            seconds = window.get("limit_window_seconds")
            reset = window.get("reset_at")
            if not finite(used) or not 0 <= used <= 100 or not finite(seconds) or seconds <= 0:
                notes.append(group + " returned an invalid quota window; its remaining allowance is unknown.")
                continue
            label = "5h limit" if seconds == 18000 else "Weekly limit" if seconds == 604800 else f"{seconds / 3600:g}h limit"
            windows.append(dict(label=group + " " + label, remainingPercent=100 - used,
                                windowSeconds=seconds, resetsAt=reset if finite(reset) and reset > 0 else None))
    credits = data.get("credits")
    balance = None
    unlimited = False
    if isinstance(credits, dict):
        unlimited = credits.get("unlimited") is True
        raw = credits.get("balance")
        try:
            value = float(raw) if not isinstance(raw, bool) else float("nan")
            if math.isfinite(value) and value >= 0:
                balance = value
        except (ValueError, TypeError, OverflowError):
            pass
    if not any(window["windowSeconds"] == 18000 for window in windows):
        notes.append("No separate 5h limit was reported.")
    if not any(window["windowSeconds"] == 604800 for window in windows):
        notes.append("No weekly limit was reported.")
    if not windows:
        notes.append("The provider did not report a timed allowance.")
    return dict(plan=clean(data.get("plan_type")), windows=windows, creditBalance=balance,
                unlimitedCredits=unlimited, keyRemaining=None, requestsRemaining=None, notes=notes)


def parse_time(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.timestamp()


def period_seconds(start, end):
    if start is None or end is None or end <= start:
        return None
    seconds = end - start
    if seconds < 60 or seconds > 366 * 24 * 3600:
        return None
    return int(round(seconds))


def xai_bounds(config):
    period = config.get("currentPeriod") if isinstance(config.get("currentPeriod"), dict) else {}
    current_end = period.get("end") if isinstance(period.get("end"), str) and period.get("end") else None
    if current_end:
        start = parse_time(period.get("start"))
        end = parse_time(current_end)
        return period_seconds(start, end), end if end and end > 0 else parse_time(config.get("billingPeriodEnd")), clean(period.get("type"))
    start = parse_time(config.get("billingPeriodStart"))
    end = parse_time(config.get("billingPeriodEnd"))
    return period_seconds(start, end), end if end and end > 0 else None, ""


def xai_label(kind, seconds):
    if kind == "USAGE_PERIOD_TYPE_WEEKLY" or seconds == 604800:
        return "Weekly limit"
    if seconds == 18000:
        return "5h limit"
    if seconds:
        return f"{seconds / 3600:g}h limit"
    return "Usage pool"


def xai_used_percent(config):
    raw = config.get("creditUsagePercent")
    if finite(raw) and 0 <= raw <= 100:
        return raw
    if raw is not None:
        return "invalid"
    cap = config.get("onDemandCap")
    used = config.get("onDemandUsed")
    cap_val = cap.get("val") if isinstance(cap, dict) else None
    used_val = used.get("val") if isinstance(used, dict) else None
    if not finite(cap_val) or cap_val <= 0 or not finite(used_val) or used_val < 0:
        return None
    percent = used_val / cap_val * 100
    return percent if 0 <= percent <= 100 else "invalid"


def xai_snapshot(data):
    config = data.get("config")
    if not isinstance(config, dict):
        raise StatusError("xAI returned no usage pool.")
    notes = ["xAI reports a share of the usage pool, not an exact remaining-token balance."]
    used = xai_used_percent(config)
    seconds, reset, kind = xai_bounds(config)
    windows = []
    if used == "invalid":
        notes.append("xAI returned an invalid quota window; its remaining allowance is unknown.")
    elif used is None:
        notes.append("xAI did not report a usage percentage. Remaining allowance is unknown.")
    else:
        if used >= 100:
            notes.append("xAI reports that its allowance is exhausted.")
        windows.append(dict(label=xai_label(kind, seconds), remainingPercent=100 - used,
                            windowSeconds=seconds, resetsAt=int(round(reset)) if reset else None))
        if not seconds:
            notes.append("No timed window length was reported.")
    for item in config.get("productUsage") or []:
        if not isinstance(item, dict):
            continue
        name = clean(item.get("product"))
        share = item.get("usagePercent")
        if not name:
            continue
        if finite(share) and 0 <= share <= 100:
            notes.append(name + f" accounts for {share:g}% of reported pool usage.")
        else:
            notes.append(name + " returned an invalid usage share.")
    tier = clean(config.get("subscriptionTier") or data.get("subscriptionTier"))
    return dict(plan=tier, windows=windows, creditBalance=None, unlimitedCredits=False,
                keyRemaining=None, requestsRemaining=None, notes=notes)


def openrouter_snapshot(data):
    key = data.get("data")
    if not isinstance(key, dict):
        raise StatusError("OpenRouter returned no key limits.")
    remaining = key.get("limit_remaining")
    requests = key.get("free_model_daily_requests")
    requests = requests.get("remaining") if isinstance(requests, dict) else None
    return dict(plan="Free tier" if key.get("is_free_tier") is True else "", windows=[],
                creditBalance=None, unlimitedCredits=False,
                keyRemaining=remaining if finite(remaining) else None,
                requestsRemaining=requests if finite(requests) and requests >= 0 else None,
                notes=["Key spending cap, not account credit balance. No cap does not mean unlimited account funds.",
                       "OpenRouter does not report an exact remaining-token balance."])


def snapshot(provider, config):
    result = dict(provider=provider, asOf=datetime.now(timezone.utc).isoformat(), state="unavailable",
                  error="", plan="", windows=[], creditBalance=None, unlimitedCredits=False,
                  keyRemaining=None, requestsRemaining=None, notes=[])
    expected = {"openai-codex": "https://chatgpt.com/backend-api/codex",
                "openrouter": "https://openrouter.ai/api/v1", "xai-grok": "https://api.x.ai/v1"}
    if provider not in expected:
        result["notes"] = ["This provider has no supported account-quota reader. Remaining tokens and credits are unknown."]
        return result
    try:
        rows = read_providers(Path(config) / "providers.json")
        row = next((row for row in rows if row.get("id") == provider), {})
        base = row.get("base_url")
        if base is not None and (not isinstance(base, str) or base.rstrip("/") != expected[provider]):
            result["notes"] = ["Custom provider route. The status reader does not send its credentials to the public quota endpoint."]
            return result
        auth = row.get("auth") or {}
        if provider == "openai-codex":
            grant = auth.get("oauth") or {}
            token = grant.get("access_token")
            account = grant.get("account_id")
            if not isinstance(token, str) or not token or not isinstance(account, str) or not account:
                raise StatusError("Codex account login is missing. Use /login openai-codex.")
            expires = grant.get("expires_at_ms")
            if finite(expires) and expires <= time.time() * 1000:
                raise StatusError("Codex login expired. Let Yuke refresh it, or use /login openai-codex.")
            data = read_json("https://chatgpt.com/backend-api/wham/usage",
                             {"Authorization": "Bearer " + token, "ChatGPT-Account-Id": account, "User-Agent": "yuke-status"})
            result.update(codex_snapshot(data))
        elif provider == "xai-grok":
            grant = auth.get("oauth") or {}
            token = grant.get("access_token")
            if not isinstance(token, str) or not token:
                raise StatusError("xAI account login is missing. Use /login xai-grok.")
            expires = grant.get("expires_at_ms")
            if finite(expires) and expires <= time.time() * 1000:
                raise StatusError("xAI login expired. Let Yuke refresh it, or use /login xai-grok.")
            data = read_json("https://cli-chat-proxy.grok.com/v1/billing?format=credits",
                             {"Authorization": "Bearer " + token, "x-xai-token-auth": "xai-grok-cli",
                              "Accept": "application/json", "User-Agent": "yuke-status"})
            result.update(xai_snapshot(data))
        else:
            source = (auth.get("api_key") or {}).get("source") or {}
            if "api_key" in row:
                token = row["api_key"]
            elif "auth" in row:
                token = source.get("literal") if "literal" in source else os.environ.get(source["env"]) if "env" in source else None
            else:
                token = os.environ.get("OPENROUTER_API_KEY")
            if not isinstance(token, str) or not token:
                raise StatusError("OpenRouter API key is missing. Use /login openrouter.")
            data = read_json("https://openrouter.ai/api/v1/key", {"Authorization": "Bearer " + token, "User-Agent": "yuke-status"})
            result.update(openrouter_snapshot(data))
        result["state"] = "reported"
        result["asOf"] = datetime.now(timezone.utc).isoformat()
    except StatusError as error:
        result.update(state="error", error=str(error))
    except (ValueError, TypeError, KeyError, AttributeError):
        result.update(state="error", error="Invalid provider configuration or quota response. Run yuke check.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    print(json.dumps(snapshot(args.provider, args.config), allow_nan=False))


if __name__ == "__main__":
    main()
