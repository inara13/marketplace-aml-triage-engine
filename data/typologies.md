# Synthetic Marketplace Data

A fake peer to peer resale marketplace, inspired by platforms like eBay and Depop. Six months of activity, January to June 2026. **No real people, companies or transactions.** Names are generated, IPs use the IPv6 documentation range `2001:db8::/32`, and high risk countries use the ISO user assigned codes XA, XB and XC.

Build it with:

```bash
python -m data.generator.generate
```

This takes about 20 seconds and uses a fixed seed, so every run produces the same data.

## Output files

| File | Who reads it |
|---|---|
| `data/raw/marketplace.duckdb` | The monitoring system: detection, triage and the agent |
| `data/raw/ground_truth.duckdb` | Evaluation only. Detection code must never read it |
| `docs/data_summary.md` | Row counts and case counts from the latest run |

## Tables in marketplace.duckdb

| Table | Key columns |
|---|---|
| users | user_id, role, signup_date, country, device_id, ip_address, bank_account_id, account_type |
| kyc_profiles | seller_id, display_name, business_type, declared_monthly_volume, country, verification_status |
| listings | listing_id, seller_id, created_at, category, title, description, price, category_typical_price |
| transactions | txn_id, listing_id, buyer_id, seller_id, amount, ts, payment_method, tracking_uploaded |
| payouts | payout_id, seller_id, amount, ts, bank_account_id, destination_country |
| refunds | refund_id, txn_id, amount, ts, reason, refund_method |

KYC profiles exist for sellers only, since buyers get much lighter checks on real marketplaces.

## Tables in ground_truth.duckdb

| Table | What it holds |
|---|---|
| cases | case_id, kind of laundering or decoy, typology, difficulty, note |
| case_members | case_id, entity_type, entity_id: every user, listing, sale, payout and refund in each case |

## Laundering typologies

8 typologies, 20 cases each: 10 easy, 6 medium, 4 hard.

| Typology | Easy | Hard |
|---|---|---|
| **Collusive loop:** linked accounts buy each other's listings | 3 to 5 accounts on one device, 40 to 70 sales in weeks, prices 3 to 6x typical, few shipments tracked | Nothing shared, 10 to 18 sales over 4 to 5 months, prices 1.2 to 1.8x |
| **Trade based:** cheap items sold at extreme prices | One buyer, prices 20 to 40x, vague descriptions | Three buyers, prices 2.5 to 4x, normal descriptions, cover sales at normal prices |
| **Structuring:** payouts kept under the $3,000 review threshold | 8 to 14 round payouts at $2,790 to $2,990 within days | Payouts from $1,500 to $2,800 over months, split across two bank accounts |
| **Dormant reactivation:** old quiet account spikes, then cashes out | 30 to 50 sales in a week from a few buyers, cashed out within two days | 10 to 15 sales over six weeks, half from ordinary buyers, slower cash out |
| **Mule network:** many sellers controlled by one party | 6 to 10 sellers sharing a device and one bank account | 5 to 7 sellers sharing only an IP range, low volume |
| **Refund laundering:** money cycled through refunds | 70 to 90 percent of sales refunded within days, mostly to store balance | 30 to 45 percent refunded, partial, mostly to the original card |
| **High risk geography:** flows tied to high risk jurisdictions | All buyers in XA or XB, payouts to a bank in XC | 30 percent of buyers high risk, payouts stay domestic |
| **Coded listing:** front listings for off platform deals | "Message me on telegram", almost nothing shipped, prices 5 to 15x | "Digital download, no shipping needed" on a physical item, prices 1.3 to 2x |

Medium cases sit between the two. Hard cases are built to slip past simple rules, so recall should land well below 100 percent.

## Decoys: innocent users who look suspicious

6 types, 40 each. Each one trips a flag or two but is clean everywhere else.

| Decoy | Looks like | Why it's innocent |
|---|---|---|
| Viral seller | Dormant reactivation | The spike comes from many different buyers at normal prices, all shipped |
| Luxury collector | Trade based laundering | High prices only in categories where rare items are real, with detailed descriptions |
| Shared household | Mule network or collusion | Mostly sells to strangers, only one or two sales inside the family |
| Seasonal clearance | Volume spike and a big payout | Lots of cheap items to many buyers |
| Bulk business | Structuring | Declared as a business, payouts vary and follow sales volume |
| Frequent traveler | High risk geography | Payouts to two normal countries, only a rare one off high risk buyer |

## Noise

Applied to everyone, including cases:
- About 2 percent of declared KYC volumes missing, and 1 percent of business types
- About 1.5 percent of listing descriptions missing, and 3 percent with typos
- About 1 percent of payment methods and 0.5 percent of user countries missing
- One percent of normal buyers share a device, and 0.3 percent are in high risk countries
- About 5 percent of normal sellers sell more than they declared

## Evaluation rules

- Detection, triage and the agent read only `marketplace.duckdb`
- The ML model trains on January to April and is tested on May and June
- Recall is measured per typology and difficulty, and false positives per decoy type
