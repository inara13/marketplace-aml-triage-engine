"""The 8 laundering typologies.

Each function plants one case. Difficulty controls how loud the signals are:
easy cases should be caught, hard cases are built to slip through.
"""
import pandas as pd

from . import text
from .common import CATEGORIES, CHEAP, COUNTRIES, COUNTRY_WEIGHTS, DAY, PRICEY


def _n(rng, lo_hi):
    return int(rng.integers(lo_hi[0], lo_hi[1] + 1))


def _before(a, lo_days, hi_days):
    """Signup range that ends a few days before activity starts."""
    return a - hi_days * DAY, a - lo_days * DAY


def collusive_loop(ctx, cid, diff):
    """Linked accounts buy each other's listings to move money around."""
    rng = ctx.rng
    P = {"easy":   dict(k=(3, 5), n=(40, 70), dur=(14, 28), mult=(3, 6), share="device_ip",
                        track=0.3, lag=(0, 2), p_out=0.8),
         "medium": dict(k=(3, 6), n=(20, 35), dur=(42, 70), mult=(1.8, 3), share="subnet",
                        track=0.7, lag=(1, 5), p_out=0.5),
         "hard":   dict(k=(4, 6), n=(10, 18), dur=(110, 150), mult=(1.2, 1.8), share="none",
                        track=0.95, lag=(3, 10), p_out=0.3)}[diff]
    a, b = ctx.window(_n(rng, P["dur"]))
    ring = ctx.new_accounts(cid, ["both"] * _n(rng, P["k"]), _before(a, 5, 180), share=P["share"])
    cat = str(rng.choice(list(CATEGORIES)))
    sales = {u: [] for u in ring}
    for ts in ctx.times(a, b, _n(rng, P["n"])):
        s, bu = (str(x) for x in rng.choice(ring, 2, replace=False))
        _, amt = ctx.sell(cid, s, bu, cat, ctx.price(cat, rng.uniform(*P["mult"])), ts,
                          track_p=P["track"])
        sales[s].append((ts, amt))
    for u in ring:
        if sales[u]:
            ctx.cash_out(cid, u, sales[u], P["lag"], P["p_out"])


def trade_based(ctx, cid, diff):
    """Ordinary cheap items sold at extreme prices to a controlled buyer."""
    rng = ctx.rng
    P = {"easy":   dict(mult=(20, 40), n=(8, 15), dur=(14, 24), buyers=1, cover=0, vague=True,
                        track=0.5, lag=(1, 3)),
         "medium": dict(mult=(6, 12), n=(6, 10), dur=(45, 70), buyers=2, cover=5, vague=True,
                        track=0.8, lag=(2, 7)),
         "hard":   dict(mult=(2.5, 4), n=(5, 8), dur=(100, 140), buyers=3, cover=15, vague=False,
                        track=0.95, lag=(5, 12))}[diff]
    a, b = ctx.window(_n(rng, P["dur"]))
    seller = ctx.new_accounts(cid, ["seller"], _before(a, 30, 365))[0]
    buyers = ctx.new_accounts(cid, ["buyer"] * P["buyers"], _before(a, 1, 60))
    cat = str(rng.choice(CHEAP))
    sales = []
    for ts in ctx.times(a, b, _n(rng, P["n"])):
        desc = text.vague(rng) if P["vague"] else None
        _, amt = ctx.sell(cid, seller, str(rng.choice(buyers)), cat,
                          ctx.price(cat, rng.uniform(*P["mult"])), ts, desc=desc, track_p=P["track"])
        sales.append((ts, amt))
    # cover sales: normal items at normal prices to real buyers, to look like a real shop
    for ts in ctx.times(a, b, P["cover"]):
        _, amt = ctx.sell(cid, seller, str(rng.choice(ctx.normal_buyers)), cat, ctx.price(cat),
                          ts, mark=False)
        sales.append((ts, amt))
    ctx.cash_out(cid, seller, sales, P["lag"], 0.5)


def structuring(ctx, cid, diff):
    """Payouts kept just under the review threshold."""
    rng = ctx.rng
    T = ctx.cfg["payout_review_threshold"]
    P = {"easy":   dict(n_pay=(8, 14), lo=0.93, hi=0.998, dur=(10, 20), banks=1, round_to=10),
         "medium": dict(n_pay=(6, 10), lo=0.80, hi=0.997, dur=(35, 50), banks=1, round_to=1),
         "hard":   dict(n_pay=(6, 9), lo=0.50, hi=0.93, dur=(80, 110), banks=2, round_to=0.01)}[diff]
    a, b = ctx.window(_n(rng, P["dur"]))
    seller = ctx.new_accounts(cid, ["seller"], _before(a, 20, 200))[0]
    buyers = ctx.new_accounts(cid, ["buyer"] * _n(rng, (3, 6)), _before(a, 1, 90))
    amounts = [round(T * rng.uniform(P["lo"], P["hi"]) / P["round_to"]) * P["round_to"]
               for _ in range(_n(rng, P["n_pay"]))]
    # enough sales to fund the payouts, in the first half of the window
    needed, got = sum(amounts) / ctx.fee, 0.0
    mid = a + (b - a) * 0.55
    sale_times = []
    while got < needed:
        cat = str(rng.choice(PRICEY))
        ts = a + (mid - a) * rng.random()
        _, amt = ctx.sell(cid, seller, str(rng.choice(buyers)), cat,
                          ctx.price(cat, rng.uniform(1.0, 1.6)), ts)
        got += amt
        sale_times.append(ts)
    user = ctx._user(seller)
    banks = [user["bank_account_id"]] + [ctx.next_id("B") for _ in range(P["banks"] - 1)]
    for i, ts in enumerate(ctx.times(a + (b - a) * 0.5, b, len(amounts))):
        ctx.payout(cid, seller, amounts[i], ts, banks[i % len(banks)], user["country"])


def dormant_reactivation(ctx, cid, diff):
    """An old quiet account suddenly sells a lot, then cashes out fast."""
    rng = ctx.rng
    P = {"easy":   dict(n=(30, 50), dur=(5, 10), buyers=(2, 4), mult=(2, 3), lag=(0, 2),
                        p_out=0.9, normal_share=0.0),
         "medium": dict(n=(15, 25), dur=(18, 25), buyers=(4, 8), mult=(1.5, 2), lag=(1, 5),
                        p_out=0.5, normal_share=0.0),
         "hard":   dict(n=(10, 15), dur=(35, 45), buyers=(8, 12), mult=(1.1, 1.4), lag=(3, 8),
                        p_out=0.3, normal_share=0.5)}[diff]
    # activity starts at least 45 days in, so the quiet period is visible
    a, b = ctx.window(_n(rng, P["dur"]), min_start=ctx.start + 45 * DAY)
    seller = ctx.new_accounts(cid, ["seller"],
                              (pd.Timestamp("2022-01-01"), pd.Timestamp("2024-06-30")),
                              declared=250)[0]
    buyers = ctx.new_accounts(cid, ["buyer"] * _n(rng, P["buyers"]), _before(a, 1, 60))
    cat = str(rng.choice(list(CATEGORIES)))
    sales = []
    for ts in ctx.times(a, b, _n(rng, P["n"])):
        buyer = (str(rng.choice(ctx.normal_buyers)) if rng.random() < P["normal_share"]
                 else str(rng.choice(buyers)))
        _, amt = ctx.sell(cid, seller, buyer, cat, ctx.price(cat, rng.uniform(*P["mult"])), ts)
        sales.append((ts, amt))
    ctx.cash_out(cid, seller, sales, P["lag"], P["p_out"])


def mule_network(ctx, cid, diff):
    """Many seller accounts controlled by one party."""
    rng = ctx.rng
    P = {"easy":   dict(m=(6, 10), share="device_bank", sales=(8, 15), dur=(25, 35),
                        mult=(1.5, 3), buyers=(3, 5)),
         "medium": dict(m=(5, 8), share="device", sales=(6, 10), dur=(50, 70),
                        mult=(1.2, 2), buyers=(4, 6)),
         "hard":   dict(m=(5, 7), share="subnet", sales=(4, 7), dur=(100, 130),
                        mult=(1.0, 1.4), buyers=(5, 8))}[diff]
    a, b = ctx.window(_n(rng, P["dur"]))
    mules = ctx.new_accounts(cid, ["seller"] * _n(rng, P["m"]), _before(a, 2, 40), share=P["share"])
    buyers = ctx.new_accounts(cid, ["buyer"] * _n(rng, P["buyers"]), _before(a, 1, 60))
    cat = str(rng.choice(list(CATEGORIES)))
    for m in mules:
        sales = []
        for ts in ctx.times(a, b, _n(rng, P["sales"])):
            _, amt = ctx.sell(cid, m, str(rng.choice(buyers)), cat,
                              ctx.price(cat, rng.uniform(*P["mult"])), ts)
            sales.append((ts, amt))
        ctx.cash_out(cid, m, sales, (1, 4), 0.4)


def refund_laundering(ctx, cid, diff):
    """Money moved through purchases that get refunded, often to store balance."""
    rng = ctx.rng
    P = {"easy":   dict(n=(12, 20), dur=(20, 30), rr=(0.7, 0.9), rlag=(1, 3), bal=0.8,
                        share="device", buyers=(2, 3), partial=False),
         "medium": dict(n=(10, 16), dur=(40, 60), rr=(0.5, 0.65), rlag=(3, 7), bal=0.5,
                        share="subnet", buyers=(2, 4), partial=False),
         "hard":   dict(n=(8, 14), dur=(80, 110), rr=(0.3, 0.45), rlag=(5, 15), bal=0.15,
                        share="none", buyers=(3, 4), partial=True)}[diff]
    a, b = ctx.window(_n(rng, P["dur"]))
    group = ctx.new_accounts(cid, ["seller"] + ["buyer"] * _n(rng, P["buyers"]),
                             _before(a, 5, 120), share=P["share"])
    seller, buyers = group[0], group[1:]
    rate = rng.uniform(*P["rr"])
    kept = []
    for ts in ctx.times(a, b, _n(rng, P["n"])):
        cat = str(rng.choice(PRICEY))
        tid, amt = ctx.sell(cid, seller, str(rng.choice(buyers)), cat,
                            ctx.price(cat, rng.uniform(1.0, 2.0)), ts)
        if rng.random() < rate:
            share = rng.uniform(0.5, 0.9) if P["partial"] else 1.0
            method = "store_balance" if rng.random() < P["bal"] else "original"
            rid = ctx.refund(cid, tid, amt * share, ts + rng.uniform(*P["rlag"]) * DAY,
                             str(rng.choice(["changed_mind", "not_as_described"])), method)
            if rid and share < 1:
                kept.append((ts, amt * (1 - share)))
        else:
            kept.append((ts, amt))
    if kept:
        ctx.cash_out(cid, seller, kept, (1, 5), 0.4)


def high_risk_geo(ctx, cid, diff):
    """Cross border flows tied to high risk jurisdictions."""
    rng = ctx.rng
    P = {"easy":   dict(n=(15, 25), dur=(25, 35), hr=1.0, pay_hr=1.0, mult=(1.5, 3), buyers=(4, 7)),
         "medium": dict(n=(10, 18), dur=(50, 70), hr=0.6, pay_hr=0.5, mult=(1.2, 2), buyers=(5, 8)),
         "hard":   dict(n=(8, 12), dur=(100, 130), hr=0.3, pay_hr=0.0, mult=(1.0, 1.3), buyers=(6, 10))}[diff]
    a, b = ctx.window(_n(rng, P["dur"]))
    seller = ctx.new_accounts(cid, ["seller"], _before(a, 10, 200),
                              country=str(rng.choice(["US", "GB"])))[0]
    nb = _n(rng, P["buyers"])
    countries = [str(rng.choice(ctx.high_risk[:2])) if rng.random() < P["hr"]
                 else str(rng.choice(COUNTRIES, p=COUNTRY_WEIGHTS)) for _ in range(nb)]
    buyers = ctx.new_accounts(cid, ["buyer"] * nb, _before(a, 1, 60), countries=countries)
    cat = str(rng.choice(list(CATEGORIES)))
    sales = []
    for ts in ctx.times(a, b, _n(rng, P["n"])):
        _, amt = ctx.sell(cid, seller, str(rng.choice(buyers)), cat,
                          ctx.price(cat, rng.uniform(*P["mult"])), ts)
        sales.append((ts, amt))
    user = ctx._user(seller)
    offshore = ctx.next_id("B")

    def route():
        if rng.random() < P["pay_hr"]:
            return offshore, ctx.high_risk[2]
        return user["bank_account_id"], user["country"]
    ctx.cash_out(cid, seller, sales, (1, 5), 0.4, route=route)


def coded_listing(ctx, cid, diff):
    """Listings that are fronts for off platform deals, often never shipped."""
    rng = ctx.rng
    P = {"easy":   dict(n=(10, 15), dur=(25, 35), mult=(5, 15), track=0.05, buyers=(2, 3)),
         "medium": dict(n=(8, 12), dur=(50, 70), mult=(2, 5), track=0.4, buyers=(2, 4)),
         "hard":   dict(n=(6, 10), dur=(80, 110), mult=(1.3, 2), track=0.7, buyers=(3, 5))}[diff]
    a, b = ctx.window(_n(rng, P["dur"]))
    seller = ctx.new_accounts(cid, ["seller"], _before(a, 5, 150))[0]
    buyers = ctx.new_accounts(cid, ["buyer"] * _n(rng, P["buyers"]), _before(a, 1, 60))
    cat = str(rng.choice(list(CATEGORIES)))
    sales = []
    for ts in ctx.times(a, b, _n(rng, P["n"])):
        _, amt = ctx.sell(cid, seller, str(rng.choice(buyers)), cat,
                          ctx.price(cat, rng.uniform(*P["mult"])), ts,
                          desc=text.coded(rng, diff), track_p=P["track"])
        sales.append((ts, amt))
    ctx.cash_out(cid, seller, sales, (1, 5), 0.5)


TYPOLOGIES = {
    "collusive_loop": (collusive_loop, "Linked accounts trading fake listings with each other"),
    "trade_based": (trade_based, "Cheap items sold at extreme prices"),
    "structuring": (structuring, "Payouts kept just under the review threshold"),
    "dormant_reactivation": (dormant_reactivation, "Old quiet account spikes then cashes out"),
    "mule_network": (mule_network, "Many sellers controlled by one party"),
    "refund_laundering": (refund_laundering, "Money cycled through purchases and refunds"),
    "high_risk_geo": (high_risk_geo, "Flows tied to high risk jurisdictions"),
    "coded_listing": (coded_listing, "Front listings for off platform deals"),
}
