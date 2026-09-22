"""Innocent users who look suspicious. They create the false positives.

Each decoy trips one or two red flags but is clean on everything else, the
way real false positives do.
"""
import pandas as pd

from . import text
from .common import CATEGORIES, DAY, LUXE, PRICEY


def _n(rng, lo, hi):
    return int(rng.integers(lo, hi + 1))


def _old_signup(ctx):
    return ctx.start - 700 * DAY, ctx.start - 30 * DAY


def _buyer(ctx):
    return str(ctx.rng.choice(ctx.normal_buyers))


def viral_seller(ctx, cid):
    """A listing blows up on social media: big spike, many different buyers."""
    rng = ctx.rng
    seller = ctx.new_accounts(cid, ["seller"], _old_signup(ctx), declared=500)[0]
    cat = str(rng.choice(["tops", "dresses", "sneakers", "accessories"]))
    sales = []
    weeks = int((ctx.end - ctx.start) / (7 * DAY))
    for ts in ctx.times(ctx.start, ctx.end, weeks * _n(rng, 2, 5)):
        sales.append((ts, ctx.sell(cid, seller, _buyer(ctx), cat, ctx.price(cat), ts)[1]))
    a, b = ctx.window(_n(rng, 7, 14))
    for ts in ctx.times(a, b, _n(rng, 40, 120)):
        sales.append((ts, ctx.sell(cid, seller, _buyer(ctx), cat, ctx.price(cat), ts,
                                   track_p=0.99)[1]))
    ctx.cash_out(cid, seller, sales, (1, 4), 0.15)


def luxury_collector(ctx, cid):
    """Real collector selling rare pieces at high prices, fully documented."""
    rng = ctx.rng
    seller = ctx.new_accounts(cid, ["seller"], _old_signup(ctx), declared=2000)[0]
    sales = []
    for ts in ctx.times(ctx.start, ctx.end, _n(rng, 10, 20)):
        cat = str(rng.choice(LUXE))
        sales.append((ts, ctx.sell(cid, seller, _buyer(ctx), cat,
                                   ctx.price(cat, rng.uniform(3, 8)), ts,
                                   desc=text.detailed(rng), track_p=1.0)[1]))
    ctx.cash_out(cid, seller, sales, (1, 5), 0.4)


def shared_household(ctx, cid):
    """Family or roommates on one device and network. Occasionally buy from each other."""
    rng = ctx.rng
    group = ctx.new_accounts(cid, ["seller"] + ["buyer"] * _n(rng, 1, 3), _old_signup(ctx),
                             share="device_ip", declared=500)
    seller, buyers = group[0], group[1:]
    cat = str(rng.choice(list(CATEGORIES)))
    sales = []
    for ts in ctx.times(ctx.start, ctx.end, _n(rng, 15, 40)):
        sales.append((ts, ctx.sell(cid, seller, _buyer(ctx), cat, ctx.price(cat), ts)[1]))
    for ts in ctx.times(ctx.start, ctx.end, _n(rng, 1, 2)):
        sales.append((ts, ctx.sell(cid, seller, str(rng.choice(buyers)), cat,
                                   ctx.price(cat), ts)[1]))
    for bu in buyers:
        for ts in ctx.times(ctx.start, ctx.end, _n(rng, 3, 12)):
            ctx.buy_existing(cid, bu, ts)
    ctx.cash_out(cid, seller, sales, (1, 5), 0.3)


def seasonal_clearance(ctx, cid):
    """Spring clear out: a burst of cheap items and one large payout."""
    rng = ctx.rng
    seller = ctx.new_accounts(cid, ["seller"], _old_signup(ctx), declared=500)[0]
    cat = str(rng.choice(["tops", "jeans", "dresses", "accessories"]))
    sales = []
    weeks = int((ctx.end - ctx.start) / (7 * DAY))
    for ts in ctx.times(ctx.start, ctx.end, weeks * _n(rng, 1, 3)):
        sales.append((ts, ctx.sell(cid, seller, _buyer(ctx), cat, ctx.price(cat), ts)[1]))
    a, b = ctx.window(_n(rng, 10, 20), min_start=pd.Timestamp("2026-03-01"))
    for ts in ctx.times(a, b, _n(rng, 30, 80)):
        sales.append((ts, ctx.sell(cid, seller, _buyer(ctx), cat,
                                   ctx.price(cat, rng.uniform(0.3, 0.7)), ts)[1]))
    ctx.cash_out(cid, seller, sales, (1, 4), 0.05)


def bulk_business(ctx, cid):
    """Busy small business. Frequent payouts, some naturally near the threshold."""
    rng = ctx.rng
    seller = ctx.new_accounts(cid, ["seller"], _old_signup(ctx), account_type="business",
                              declared=25000)[0]
    cat = str(rng.choice(["electronics", "sneakers"]))
    sales = []
    for ts in ctx.times(ctx.start, ctx.end, _n(rng, 200, 350)):
        sales.append((ts, ctx.sell(cid, seller, _buyer(ctx), cat, ctx.price(cat), ts)[1]))
    ctx.cash_out(cid, seller, sales, (0, 1), 0.12)


def frequent_traveler(ctx, cid):
    """Legit seller who moved abroad: buyers everywhere, payouts to two countries."""
    rng = ctx.rng
    seller = ctx.new_accounts(cid, ["seller"], _old_signup(ctx), country="GB", declared=1000)[0]
    # one or two genuine one off buyers from a high risk country
    hr_buyers = ctx.new_accounts(cid, ["buyer"] * _n(rng, 1, 2), _old_signup(ctx),
                                 countries=[ctx.high_risk[0], ctx.high_risk[1]])
    cat = str(rng.choice(list(CATEGORIES)))
    sales = []
    for ts in ctx.times(ctx.start, ctx.end, _n(rng, 20, 40)):
        buyer = str(rng.choice(hr_buyers)) if rng.random() < 0.05 else _buyer(ctx)
        sales.append((ts, ctx.sell(cid, seller, buyer, cat, ctx.price(cat), ts)[1]))
    home = ctx._user(seller)["bank_account_id"]
    abroad = ctx.next_id("B")
    ctx.cash_out(cid, seller, sales, (1, 5), 0.3,
                 route=lambda: (home, "GB") if rng.random() < 0.5 else (abroad, "IE"))


DECOYS = {
    "viral_seller": (viral_seller, "Sudden spike from a viral listing"),
    "luxury_collector": (luxury_collector, "Real collector selling rare items at high prices"),
    "shared_household": (shared_household, "Family sharing one device and network"),
    "seasonal_clearance": (seasonal_clearance, "Spring clear out burst and one big payout"),
    "bulk_business": (bulk_business, "Busy business with frequent payouts"),
    "frequent_traveler": (frequent_traveler, "Seller with payouts in two countries"),
}
