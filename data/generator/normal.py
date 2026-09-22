"""Normal, innocent marketplace activity. Built with numpy for speed."""
import numpy as np
import pandas as pd

from . import text
from .common import (CATEGORIES, CATEGORY_POPULARITY, COUNTRIES, COUNTRY_WEIGHTS,
                     DAY, PAYMENT_METHODS, PAYMENT_WEIGHTS, bucket_up)

REFUND_REASONS = ["not_as_described", "item_not_received", "changed_mind", "damaged"]


def _dates(rng, lo, hi, n):
    lo, hi = pd.Timestamp(lo), pd.Timestamp(hi)
    return lo + (hi - lo) * rng.random(n)


def build(ctx):
    rng, d = ctx.rng, ctx.cfg
    S, B, N = d["n_sellers"], d["n_buyers"], d["n_transactions"]
    cats = list(CATEGORIES)
    typical = np.array([CATEGORIES[c] for c in cats])

    # ----- sellers -----
    seller_ids = ctx.reserve("U", S)
    is_biz = rng.random(S) < d["business_seller_share"]
    late = rng.random(S) < 0.10          # 10 percent join during the window
    signup = np.where(late,
                      _dates(rng, ctx.start, ctx.end - 60 * DAY, S),
                      _dates(rng, "2019-01-01", "2025-12-31", S))
    s_country = rng.choice(COUNTRIES, S, p=COUNTRY_WEIGHTS)
    activity = rng.lognormal(0, 1, S) * np.where(is_biz, 6, 1)
    exp_sales = activity / activity.sum() * N

    # each seller focuses on one to three categories
    n_cat = rng.integers(1, 4, S)
    seller_cats = [rng.choice(len(cats), k, replace=False, p=CATEGORY_POPULARITY) for k in n_cat]

    # declared volume roughly covers real volume, with 5 percent under declaring
    avg_price = np.array([typical[c].mean() for c in seller_cats])
    monthly = exp_sales / 6 * avg_price
    slack = np.where(rng.random(S) < 0.05, rng.uniform(0.3, 0.7, S), rng.uniform(1.0, 2.5, S))
    declared = [bucket_up(x) for x in monthly * slack]

    # ----- buyers -----
    buyer_ids = ctx.reserve("U", B)
    b_country = rng.choice(COUNTRIES, B, p=COUNTRY_WEIGHTS)
    hr = rng.random(B) < 0.003           # a few innocent buyers in high risk countries
    b_country[hr] = rng.choice(ctx.high_risk, hr.sum())
    b_signup = _dates(rng, "2019-01-01", "2025-12-31", B)
    b_weight = rng.lognormal(0, 1.2, B)

    # devices, IPs, banks: unique per user, but one percent of buyers share a device
    s_dev, b_dev = ctx.reserve("D", S), ctx.reserve("D", B)
    shared = np.where(rng.random(B) < 0.01)[0]
    b_dev[shared] = b_dev[rng.integers(0, B, len(shared))]
    s_bank = ctx.reserve("B", S)

    users = pd.DataFrame({
        "user_id": np.concatenate([seller_ids, buyer_ids]),
        "role": ["seller"] * S + ["buyer"] * B,
        "signup_date": np.concatenate([signup, b_signup]),
        "country": np.concatenate([s_country, b_country]),
        "device_id": np.concatenate([s_dev, b_dev]),
        "ip_address": [ctx.new_ip() for _ in range(S + B)],
        "bank_account_id": np.concatenate([s_bank, [None] * B]),
        "account_type": np.concatenate([np.where(is_biz, "business", "individual"), [None] * B]),
    })
    kyc = pd.DataFrame({
        "seller_id": seller_ids,
        "display_name": [ctx.fake.name() for _ in range(S)],
        "business_type": np.where(is_biz, "business", "individual"),
        "declared_monthly_volume": declared,
        "country": s_country,
        "verification_status": np.where(rng.random(S) < 0.01, "pending_review", "verified"),
        "verified_date": pd.to_datetime(signup) + pd.to_timedelta(rng.integers(0, 5, S), unit="D"),
    })

    # ----- listings -----
    n_list = np.maximum(1, np.round(exp_sales * np.where(is_biz, 0.12, 0.55)
                                    + rng.poisson(1, S))).astype(int)
    L = int(n_list.sum())
    l_seller = np.repeat(np.arange(S), n_list)
    l_start = np.concatenate([[0], np.cumsum(n_list)[:-1]])
    l_cat = np.array([seller_cats[s][rng.integers(0, len(seller_cats[s]))] for s in l_seller])
    l_price = np.round(np.maximum(typical[l_cat] * rng.lognormal(0, 0.45, L), 3), 2)
    lo = np.maximum(pd.to_datetime(signup[l_seller]), ctx.start - 60 * DAY)
    l_created = lo + (ctx.end - 3 * DAY - lo) * rng.random(L)
    listing_ids = ctx.reserve("L", L)
    listings = pd.DataFrame({
        "listing_id": listing_ids,
        "seller_id": seller_ids[l_seller],
        "created_at": l_created,
        "category": np.array(cats)[l_cat],
        "title": [text.title(rng, cats[c]) for c in l_cat],
        "description": [text.description(rng) for _ in range(L)],
        "price": l_price,
        "category_typical_price": typical[l_cat],
    })

    # ----- transactions -----
    t_seller = rng.choice(S, N, p=activity / activity.sum())
    t_list = l_start[t_seller] + (rng.random(N) * n_list[t_seller]).astype(int)
    t_lo = np.maximum(pd.to_datetime(l_created[t_list]), ctx.start)
    t_ts = t_lo + (ctx.end - t_lo) * rng.random(N)
    t_buyer = rng.choice(B, N, p=b_weight / b_weight.sum())
    t_amount = np.round(l_price[t_list] * rng.uniform(1.0, 1.06, N), 2)
    txn_ids = ctx.reserve("T", N)
    txns = pd.DataFrame({
        "txn_id": txn_ids,
        "listing_id": listing_ids[t_list],
        "buyer_id": buyer_ids[t_buyer],
        "seller_id": seller_ids[t_seller],
        "amount": t_amount,
        "ts": t_ts,
        "payment_method": rng.choice(PAYMENT_METHODS, N, p=PAYMENT_WEIGHTS),
        "tracking_uploaded": rng.random(N) < 0.97,
    }).sort_values("ts").reset_index(drop=True)

    payouts = _payouts(ctx, txns, users.set_index("user_id"), is_biz, seller_ids)
    refunds = _refunds(ctx, txns)

    # used later by decoys that buy normal items
    ctx.normal_buyers = buyer_ids
    ctx.normal_listings = list(zip(listing_ids, seller_ids[l_seller], l_price,
                                   pd.to_datetime(l_created)))
    return dict(users=users, kyc_profiles=kyc, listings=listings,
                transactions=txns, payouts=payouts, refunds=refunds)


def _payouts(ctx, txns, users, is_biz, seller_ids):
    """Weekly balance sweeps: businesses almost every week, individuals now and then."""
    rng = ctx.rng
    biz = dict(zip(seller_ids, is_biz))
    t = txns[["seller_id", "ts", "amount"]].copy()
    t["week"] = ((t["ts"] - ctx.start) / (7 * DAY)).astype(int)
    weekly = t.groupby(["seller_id", "week"])["amount"].sum()
    rows = []
    for seller, grp in weekly.groupby(level=0):
        p = 0.9 if biz[seller] else 0.5
        bal = 0.0
        for (_, week), amt in grp.items():
            bal += amt * ctx.fee
            if rng.random() < p:
                ts = ctx.start + (week + 1) * 7 * DAY + rng.uniform(0, 3) * DAY
                if ts <= ctx.end:
                    rows.append((seller, round(bal, 2), ts))
                    bal = 0.0
    out = pd.DataFrame(rows, columns=["seller_id", "amount", "ts"])
    out.insert(0, "payout_id", ctx.reserve("P", len(out)))
    out["bank_account_id"] = users.loc[out["seller_id"], "bank_account_id"].values
    out["destination_country"] = users.loc[out["seller_id"], "country"].values
    return out


def _refunds(ctx, txns):
    rng = ctx.rng
    pick = txns.sample(frac=ctx.cfg["refund_rate"], random_state=int(rng.integers(1e9)))
    ts = pick["ts"] + pd.to_timedelta(rng.uniform(1, 20, len(pick)), unit="D")
    keep = (ts <= ctx.end).values
    pick, ts = pick[keep], ts[keep]
    partial = rng.random(len(pick)) < 0.10
    amount = np.where(partial, pick["amount"] * rng.uniform(0.2, 0.6, len(pick)), pick["amount"])
    out = pd.DataFrame({
        "txn_id": pick["txn_id"].values,
        "amount": np.round(amount, 2),
        "ts": ts.values,
        "reason": rng.choice(REFUND_REASONS, len(pick), p=[0.35, 0.25, 0.3, 0.1]),
        "refund_method": np.where(rng.random(len(pick)) < 0.01, "store_balance", "original"),
    })
    out.insert(0, "refund_id", ctx.reserve("R", len(out)))
    return out
