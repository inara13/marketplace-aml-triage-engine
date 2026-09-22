"""Shared building blocks for the synthetic marketplace generator.

The Ctx object holds the random generator, the time window, ID counters and
the rows for every table. Typologies and decoys use its helpers so every
listing, transaction, payout and refund is created the same way.
"""
import numpy as np
import pandas as pd
from faker import Faker

from . import text

DAY = pd.Timedelta(days=1)

# Typical price in USD for each category
CATEGORIES = {
    "tops": 22, "jeans": 35, "dresses": 40, "vintage_jackets": 75,
    "sneakers": 120, "accessories": 28, "luxury_bags": 850,
    "electronics": 260, "collectibles": 60,
}
CATEGORY_POPULARITY = [0.20, 0.14, 0.12, 0.09, 0.13, 0.12, 0.04, 0.08, 0.08]
CHEAP = ["tops", "jeans", "dresses", "accessories", "collectibles"]
PRICEY = ["luxury_bags", "electronics", "sneakers"]
LUXE = ["luxury_bags", "collectibles", "vintage_jackets"]

COUNTRIES = ["US", "GB", "CA", "AU", "DE", "FR", "IE", "NL", "IT", "ES"]
COUNTRY_WEIGHTS = [0.55, 0.20, 0.06, 0.05, 0.04, 0.03, 0.02, 0.02, 0.02, 0.01]

PAYMENT_METHODS = ["card", "wallet", "bank_transfer", "balance"]
PAYMENT_WEIGHTS = [0.68, 0.22, 0.05, 0.05]

VOLUME_BUCKETS = [250, 500, 1000, 2000, 5000, 10000, 25000, 50000, 100000]


def bucket_up(x):
    for b in VOLUME_BUCKETS:
        if x <= b:
            return b
    return VOLUME_BUCKETS[-1]


class Ctx:
    def __init__(self, cfg):
        d = cfg["data"]
        self.cfg = d
        self.rng = np.random.default_rng(d["seed"])
        Faker.seed(d["seed"])
        self.fake = Faker()
        self.start = pd.Timestamp(d["start_date"])
        self.end = pd.Timestamp(d["end_date"]) + pd.Timedelta(hours=23, minutes=59)
        self.fee = 1 - d["platform_fee"]
        self.high_risk = list(d["high_risk_countries"])
        self.rows = {t: [] for t in
                     ["users", "kyc_profiles", "listings", "transactions", "payouts", "refunds"]}
        self.cases, self.members = [], []
        self.n = {k: 0 for k in ["U", "L", "T", "P", "R", "D", "B", "C"]}
        self.width = {"U": 6, "L": 7, "T": 7, "P": 6, "R": 6, "D": 6, "B": 6, "C": 4}
        # filled in by the normal activity step
        self.normal_buyers = None
        self.normal_listings = None

    # ---------- ids and small helpers ----------
    def next_id(self, prefix):
        self.n[prefix] += 1
        return f"{prefix}{self.n[prefix]:0{self.width[prefix]}d}"

    def reserve(self, prefix, count):
        """Hand out a block of ids at once, used by the vectorized normal step."""
        first = self.n[prefix] + 1
        self.n[prefix] += count
        w = self.width[prefix]
        return np.array([f"{prefix}{i:0{w}d}" for i in range(first, first + count)])

    def new_ip_subnet(self):
        # 2001:db8::/32 is the IPv6 documentation range, so no real address is ever used
        a, b = self.rng.integers(0, 65536, 2)
        return f"2001:db8:{a:04x}:{b:04x}"

    def new_ip(self, subnet=None):
        subnet = subnet or self.new_ip_subnet()
        return f"{subnet}::{int(self.rng.integers(1, 65535)):x}"

    def clip(self, ts):
        return min(ts, self.end)

    def window(self, days, min_start=None):
        """Random [a, b] period of the given length inside the data window."""
        lo = min_start or self.start
        latest = self.end - days * DAY
        a = lo + (latest - lo) * self.rng.random()
        return a, a + days * DAY

    def times(self, a, b, n):
        offsets = np.sort(self.rng.random(n))
        return [a + (b - a) * o for o in offsets]

    def price(self, category, mult=1.0):
        base = CATEGORIES[category] * mult * self.rng.lognormal(0, 0.1)
        return round(max(base, 3.0), 2)

    # ---------- entity creation ----------
    def add_user(self, role, signup, country, device=None, ip=None, bank=None,
                 account_type="individual", declared=None):
        uid = self.next_id("U")
        is_seller = role in ("seller", "both")
        if is_seller and bank is None:
            bank = self.next_id("B")
        self.rows["users"].append(dict(
            user_id=uid, role=role, signup_date=signup, country=country,
            device_id=device or self.next_id("D"), ip_address=ip or self.new_ip(),
            bank_account_id=bank if is_seller else None,
            account_type=account_type if is_seller else None))
        if is_seller:
            self.rows["kyc_profiles"].append(dict(
                seller_id=uid, display_name=self.fake.name(), business_type=account_type,
                declared_monthly_volume=declared or 500, country=country,
                verification_status="verified",
                verified_date=signup + int(self.rng.integers(0, 5)) * DAY))
        return uid

    def new_accounts(self, cid, roles, signup, share="none", country=None,
                     countries=None, account_type="individual", declared=None):
        """Create a group of linked accounts for one case or decoy.

        share: none, device, subnet, device_ip, device_bank
        """
        device = self.next_id("D") if share.startswith("device") else None
        subnet = self.new_ip_subnet() if share in ("subnet", "device_ip") else None
        ip = self.new_ip(subnet) if share == "device_ip" else None
        bank = self.next_id("B") if share == "device_bank" else None
        lo, hi = signup
        ids = []
        for i, role in enumerate(roles):
            c = countries[i] if countries else (country or self.rng.choice(COUNTRIES, p=COUNTRY_WEIGHTS))
            uid = self.add_user(
                role, lo + (hi - lo) * self.rng.random(), str(c),
                device=device,
                ip=ip or (self.new_ip(subnet) if subnet else None),
                bank=bank, account_type=account_type,
                declared=declared or int(self.rng.choice([250, 500, 1000])))
            self.member(cid, "user", uid)
            ids.append(uid)
        return ids

    def sell(self, cid, seller, buyer, category, price, ts, desc=None, title=None,
             track_p=0.97, pm=None, mark=True):
        """One listing plus its sale. Returns (txn_id, amount)."""
        lid = self.next_id("L")
        created = ts - self.rng.uniform(0.1, 3) * DAY
        self.rows["listings"].append(dict(
            listing_id=lid, seller_id=seller, created_at=created, category=category,
            title=title or text.title(self.rng, category),
            description=desc if desc is not None else text.description(self.rng),
            price=price, category_typical_price=CATEGORIES[category]))
        amount = round(price * self.rng.uniform(1.0, 1.06), 2)
        tid = self.add_txn(lid, buyer, seller, amount, ts, pm=pm, track_p=track_p)
        if mark:
            self.member(cid, "listing", lid)
            self.member(cid, "transaction", tid)
        return tid, amount

    def add_txn(self, listing, buyer, seller, amount, ts, pm=None, track_p=0.97):
        tid = self.next_id("T")
        self.rows["transactions"].append(dict(
            txn_id=tid, listing_id=listing, buyer_id=buyer, seller_id=seller,
            amount=amount, ts=ts,
            payment_method=pm or str(self.rng.choice(PAYMENT_METHODS, p=PAYMENT_WEIGHTS)),
            tracking_uploaded=bool(self.rng.random() < track_p)))
        return tid

    def buy_existing(self, cid, buyer, ts):
        """A case or decoy account buying a normal listing from a normal seller."""
        for _ in range(50):
            i = int(self.rng.integers(0, len(self.normal_listings)))
            lid, seller, price, created = self.normal_listings[i]
            if created < ts:
                break
        else:
            return None
        tid = self.add_txn(lid, buyer, seller, round(price * self.rng.uniform(1.0, 1.06), 2), ts)
        self.member(cid, "transaction", tid)
        return tid

    def payout(self, cid, seller, amount, ts, bank, dest):
        pid = self.next_id("P")
        self.rows["payouts"].append(dict(
            payout_id=pid, seller_id=seller, amount=round(amount, 2),
            ts=self.clip(ts), bank_account_id=bank, destination_country=dest))
        self.member(cid, "payout", pid)
        return pid

    def cash_out(self, cid, seller, sales, lag, p_out, route=None):
        """Turn a seller's sales into payouts.

        After each sale the seller withdraws the balance with probability p_out,
        lag days later. Whatever is left is withdrawn after the last sale.
        route() returns (bank, country) per payout, defaulting to the seller's own.
        """
        user = self._user(seller)
        route = route or (lambda: (user["bank_account_id"], user["country"]))
        bal = 0.0
        for i, (ts, amt) in enumerate(sorted(sales)):
            bal += amt * self.fee
            if self.rng.random() < p_out or i == len(sales) - 1:
                bank, dest = route()
                self.payout(cid, seller, bal, ts + self.rng.uniform(*lag) * DAY, bank, dest)
                bal = 0.0

    def refund(self, cid, txn, amount, ts, reason, method="original"):
        if ts > self.end:
            return None
        rid = self.next_id("R")
        self.rows["refunds"].append(dict(
            refund_id=rid, txn_id=txn, amount=round(amount, 2), ts=ts,
            reason=reason, refund_method=method))
        self.member(cid, "refund", rid)
        return rid

    def _user(self, uid):
        for u in reversed(self.rows["users"]):
            if u["user_id"] == uid:
                return u
        raise KeyError(uid)

    # ---------- ground truth ----------
    def new_case(self, kind, typology, difficulty, note):
        cid = self.next_id("C")
        self.cases.append(dict(case_id=cid, kind=kind, typology=typology,
                               difficulty=difficulty, note=note))
        return cid

    def member(self, cid, entity_type, entity_id):
        self.members.append(dict(case_id=cid, entity_type=entity_type, entity_id=entity_id))
