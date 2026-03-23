#!/usr/bin/env python3
"""
Google Ads MCP Server — 42 tools

Analytics (26): gads_list_customers, gads_get_account_info, gads_campaign_performance,
  gads_adgroup_performance, gads_keyword_performance, gads_search_terms, gads_ad_performance,
  gads_demographic_breakdown, gads_geo_performance, gads_hourly_breakdown, gads_device_breakdown,
  gads_shopping_performance, gads_display_performance, gads_video_performance,
  gads_landing_page_performance, gads_audience_performance, gads_conversion_actions,
  gads_budget_pacing, gads_auction_insights, gads_change_history, gads_quality_score,
  gads_call_metrics, gads_extension_performance, gads_recommendations, gads_asset_report,
  gads_account_overview

Management (16): gads_create_campaign, gads_create_budget, gads_create_adgroup,
  gads_add_keywords, gads_add_negative_keywords, gads_update_campaign_status,
  gads_update_adgroup_status, gads_update_keyword_status, gads_update_keyword_bid,
  gads_update_campaign_budget, gads_create_responsive_search_ad,
  gads_pause_all_campaigns, gads_enable_campaign, gads_apply_recommendation,
  gads_dismiss_recommendation, gads_list_labels

Setup: pip install -r requirements.txt
       cp .env.example .env  # then fill in credentials
       python server.py
"""

import json
import os
from datetime import date, timedelta
from typing import Optional

import requests
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from mcp.server.fastmcp import FastMCP

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GADS_SCOPES = [
    "https://www.googleapis.com/auth/adwords",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]
GADS_API_VERSION = "v17"
GADS_BASE = f"https://googleads.googleapis.com/{GADS_API_VERSION}"

mcp = FastMCP("Google Ads")

_cached_creds: Optional[Credentials] = None


def _creds() -> Credentials:
    """Return valid OAuth2 credentials, refreshing when expired."""
    global _cached_creds
    if _cached_creds is None or not _cached_creds.valid:
        _cached_creds = Credentials(
            token=None,
            refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["GOOGLE_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
            scopes=GADS_SCOPES,
        )
        _cached_creds.refresh(Request())
    return _cached_creds


def _developer_token() -> str:
    t = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", "")
    if not t:
        raise ValueError("GOOGLE_ADS_DEVELOPER_TOKEN not set in environment.")
    return t


def _customer_id() -> str:
    cid = os.environ.get("GOOGLE_ADS_CUSTOMER_ID", "")
    if not cid:
        raise ValueError("GOOGLE_ADS_CUSTOMER_ID not set in environment.")
    return cid.replace("-", "")


def _login_customer_id() -> Optional[str]:
    lcid = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")
    return lcid.replace("-", "") if lcid else None


def _headers() -> dict:
    creds = _creds()
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "developer-token": _developer_token(),
        "Content-Type": "application/json",
    }
    lcid = _login_customer_id()
    if lcid:
        headers["login-customer-id"] = lcid
    return headers


def _resolve_customer(customer_id: str) -> str:
    return customer_id.replace("-", "") if customer_id else _customer_id()


def _search(gaql: str, customer_id: str = "") -> list:
    """Execute a GAQL query and return all result rows."""
    cid = _resolve_customer(customer_id)
    resp = requests.post(
        f"{GADS_BASE}/customers/{cid}/googleAds:search",
        headers=_headers(),
        json={"query": gaql},
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"Google Ads API error {resp.status_code}: {resp.text[:400]}")
    data = resp.json()
    results = []
    while True:
        results.extend(data.get("results", []))
        next_page = data.get("nextPageToken")
        if not next_page:
            break
        resp2 = requests.post(
            f"{GADS_BASE}/customers/{cid}/googleAds:search",
            headers=_headers(),
            json={"query": gaql, "pageToken": next_page},
            timeout=30,
        )
        data = resp2.json()
    return results


def _mutate(resource: str, operations: list, customer_id: str = "") -> dict:
    """Execute a mutation (create/update/remove) and return response."""
    cid = _resolve_customer(customer_id)
    resp = requests.post(
        f"{GADS_BASE}/customers/{cid}/{resource}:mutate",
        headers=_headers(),
        json={"operations": operations},
        timeout=30,
    )
    if not resp.ok:
        return {"error": resp.text[:500]}
    return resp.json()


def _date_range(start_date: str, end_date: str, default_days: int = 28) -> tuple[str, str]:
    ed = end_date or str(date.today())
    sd = start_date or str(date.today() - timedelta(days=default_days))
    return sd, ed


# ---------------------------------------------------------------------------
# Analytics Tools (read-only)
# ---------------------------------------------------------------------------

@mcp.tool()
def gads_list_customers() -> str:
    """List all Google Ads customer accounts accessible to the authenticated user."""
    creds = _creds()
    resp = requests.get(
        f"{GADS_BASE}/customers:listAccessibleCustomers",
        headers={
            "Authorization": f"Bearer {creds.token}",
            "developer-token": _developer_token(),
            "Content-Type": "application/json",
        },
        timeout=20,
    )
    if not resp.ok:
        return json.dumps({"error": resp.text[:300]})
    resource_names = resp.json().get("resourceNames", [])
    customer_ids = [rn.split("/")[-1] for rn in resource_names]
    return json.dumps({"customers": customer_ids, "total": len(customer_ids)})


@mcp.tool()
def gads_get_account_info(customer_id: str = "") -> str:
    """Get basic information about a Google Ads account: name, currency, timezone, status.

    Args:
        customer_id: Google Ads customer ID (10 digits). Leave blank to use GOOGLE_ADS_CUSTOMER_ID.
    """
    rows = _search("""
        SELECT customer.id, customer.descriptive_name, customer.currency_code,
               customer.time_zone, customer.status, customer.manager
        FROM customer
        LIMIT 1
    """, customer_id)
    if not rows:
        return json.dumps({"error": "No customer info returned."})
    c = rows[0].get("customer", {})
    return json.dumps({
        "id": c.get("id"),
        "name": c.get("descriptiveName"),
        "currency": c.get("currencyCode"),
        "timezone": c.get("timeZone"),
        "status": c.get("status"),
        "manager": c.get("manager", False),
    })


@mcp.tool()
def gads_account_overview(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
) -> str:
    """Get high-level account metrics: total spend, impressions, clicks, conversions, CTR, avg CPC, ROAS.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    sd, ed = _date_range(start_date, end_date)
    rows = _search(f"""
        SELECT metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.ctr, metrics.average_cpc, metrics.conversions,
               metrics.conversions_value, metrics.cost_per_conversion
        FROM customer
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
    """, customer_id)
    if not rows:
        return json.dumps({"date_range": f"{sd} to {ed}", "metrics": {}})
    m = rows[0].get("metrics", {})
    spend = round(int(m.get("costMicros", 0)) / 1_000_000, 2)
    return json.dumps({
        "date_range": f"{sd} to {ed}",
        "impressions": m.get("impressions"),
        "clicks": m.get("clicks"),
        "spend": spend,
        "ctr": m.get("ctr"),
        "avg_cpc": round(int(m.get("averageCpc", 0)) / 1_000_000, 4),
        "conversions": m.get("conversions"),
        "conversion_value": m.get("conversionsValue"),
        "cost_per_conversion": round(int(m.get("costPerConversion", 0)) / 1_000_000, 4),
        "roas": round(float(m.get("conversionsValue", 0)) / max(spend, 0.01), 2),
    })


@mcp.tool()
def gads_campaign_performance(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
    status_filter: str = "ENABLED",
    row_limit: int = 25,
) -> str:
    """Get Google Ads campaign-level performance: spend, impressions, clicks, conversions, CTR per campaign.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
        status_filter: Filter by campaign status: ENABLED, PAUSED, REMOVED, or ALL. Default ENABLED.
        row_limit: Max campaigns. Default 25.
    """
    sd, ed = _date_range(start_date, end_date)
    where_status = "" if status_filter == "ALL" else f"AND campaign.status = '{status_filter}'"
    rows = _search(f"""
        SELECT campaign.id, campaign.name, campaign.status, campaign.bidding_strategy_type,
               metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.ctr,
               metrics.average_cpc, metrics.conversions, metrics.conversions_value
        FROM campaign
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        {where_status}
        ORDER BY metrics.cost_micros DESC
        LIMIT {row_limit}
    """, customer_id)
    results = []
    for row in rows:
        c = row.get("campaign", {})
        m = row.get("metrics", {})
        results.append({
            "id": c.get("id"),
            "name": c.get("name"),
            "status": c.get("status"),
            "bidding_strategy": c.get("biddingStrategyType"),
            "spend": round(int(m.get("costMicros", 0)) / 1_000_000, 2),
            "impressions": m.get("impressions"),
            "clicks": m.get("clicks"),
            "ctr": m.get("ctr"),
            "avg_cpc": round(int(m.get("averageCpc", 0)) / 1_000_000, 4),
            "conversions": m.get("conversions"),
            "conversion_value": m.get("conversionsValue"),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "campaigns": results})


@mcp.tool()
def gads_adgroup_performance(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
    campaign_id: str = "",
    row_limit: int = 25,
) -> str:
    """Get Google Ads ad group performance: spend, clicks, conversions for each ad group.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
        campaign_id: Filter by campaign ID. Leave blank for all.
        row_limit: Max ad groups. Default 25.
    """
    sd, ed = _date_range(start_date, end_date)
    where_campaign = f"AND campaign.id = '{campaign_id}'" if campaign_id else ""
    rows = _search(f"""
        SELECT campaign.name, ad_group.id, ad_group.name, ad_group.status,
               metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.ctr, metrics.average_cpc, metrics.conversions
        FROM ad_group
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        AND ad_group.status != 'REMOVED'
        {where_campaign}
        ORDER BY metrics.cost_micros DESC
        LIMIT {row_limit}
    """, customer_id)
    results = []
    for row in rows:
        ag = row.get("adGroup", {})
        c = row.get("campaign", {})
        m = row.get("metrics", {})
        results.append({
            "id": ag.get("id"),
            "name": ag.get("name"),
            "status": ag.get("status"),
            "campaign": c.get("name"),
            "spend": round(int(m.get("costMicros", 0)) / 1_000_000, 2),
            "impressions": m.get("impressions"),
            "clicks": m.get("clicks"),
            "ctr": m.get("ctr"),
            "avg_cpc": round(int(m.get("averageCpc", 0)) / 1_000_000, 4),
            "conversions": m.get("conversions"),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "ad_groups": results})


@mcp.tool()
def gads_keyword_performance(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
    campaign_id: str = "",
    row_limit: int = 50,
    sort_by: str = "cost",
) -> str:
    """Get Google Ads keyword-level performance: clicks, impressions, spend, quality score, match type.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
        campaign_id: Filter by campaign ID. Leave blank for all.
        row_limit: Max keywords. Default 50.
        sort_by: Sort by cost, clicks, or conversions. Default cost.
    """
    sd, ed = _date_range(start_date, end_date)
    sort_field = {"cost": "metrics.cost_micros", "clicks": "metrics.clicks", "conversions": "metrics.conversions"}.get(sort_by, "metrics.cost_micros")
    where_campaign = f"AND campaign.id = '{campaign_id}'" if campaign_id else ""
    rows = _search(f"""
        SELECT campaign.name, ad_group.name,
               ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type,
               ad_group_criterion.status, ad_group_criterion.quality_info.quality_score,
               metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.ctr, metrics.average_cpc, metrics.conversions,
               metrics.search_impression_share
        FROM keyword_view
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        AND ad_group_criterion.status != 'REMOVED'
        {where_campaign}
        ORDER BY {sort_field} DESC
        LIMIT {row_limit}
    """, customer_id)
    results = []
    for row in rows:
        kw = row.get("adGroupCriterion", {}).get("keyword", {})
        m = row.get("metrics", {})
        qi = row.get("adGroupCriterion", {}).get("qualityInfo", {})
        results.append({
            "keyword": kw.get("text"),
            "match_type": kw.get("matchType"),
            "status": row.get("adGroupCriterion", {}).get("status"),
            "quality_score": qi.get("qualityScore"),
            "campaign": row.get("campaign", {}).get("name"),
            "ad_group": row.get("adGroup", {}).get("name"),
            "spend": round(int(m.get("costMicros", 0)) / 1_000_000, 2),
            "impressions": m.get("impressions"),
            "clicks": m.get("clicks"),
            "ctr": m.get("ctr"),
            "avg_cpc": round(int(m.get("averageCpc", 0)) / 1_000_000, 4),
            "conversions": m.get("conversions"),
            "search_impression_share": m.get("searchImpressionShare"),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "keywords": results})


@mcp.tool()
def gads_search_terms(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
    campaign_id: str = "",
    row_limit: int = 50,
) -> str:
    """Get Google Ads search terms report — the actual queries that triggered ads, with clicks and conversions.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
        campaign_id: Filter by campaign ID. Leave blank for all.
        row_limit: Max terms. Default 50.
    """
    sd, ed = _date_range(start_date, end_date)
    where_campaign = f"AND campaign.id = '{campaign_id}'" if campaign_id else ""
    rows = _search(f"""
        SELECT search_term_view.search_term, search_term_view.status,
               campaign.name, ad_group.name,
               metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.ctr, metrics.average_cpc, metrics.conversions
        FROM search_term_view
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        {where_campaign}
        ORDER BY metrics.clicks DESC
        LIMIT {row_limit}
    """, customer_id)
    results = []
    for row in rows:
        stv = row.get("searchTermView", {})
        m = row.get("metrics", {})
        results.append({
            "search_term": stv.get("searchTerm"),
            "status": stv.get("status"),
            "campaign": row.get("campaign", {}).get("name"),
            "ad_group": row.get("adGroup", {}).get("name"),
            "impressions": m.get("impressions"),
            "clicks": m.get("clicks"),
            "spend": round(int(m.get("costMicros", 0)) / 1_000_000, 2),
            "ctr": m.get("ctr"),
            "avg_cpc": round(int(m.get("averageCpc", 0)) / 1_000_000, 4),
            "conversions": m.get("conversions"),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "search_terms": results})


@mcp.tool()
def gads_ad_performance(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
    campaign_id: str = "",
    row_limit: int = 25,
) -> str:
    """Get Google Ads individual ad performance: clicks, impressions, CTR, conversions per ad.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
        campaign_id: Filter by campaign ID. Leave blank for all.
        row_limit: Max ads. Default 25.
    """
    sd, ed = _date_range(start_date, end_date)
    where_campaign = f"AND campaign.id = '{campaign_id}'" if campaign_id else ""
    rows = _search(f"""
        SELECT campaign.name, ad_group.name, ad_group_ad.ad.id,
               ad_group_ad.ad.name, ad_group_ad.ad.type, ad_group_ad.status,
               metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.ctr, metrics.average_cpc, metrics.conversions
        FROM ad_group_ad
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        AND ad_group_ad.status != 'REMOVED'
        {where_campaign}
        ORDER BY metrics.cost_micros DESC
        LIMIT {row_limit}
    """, customer_id)
    results = []
    for row in rows:
        ad = row.get("adGroupAd", {}).get("ad", {})
        m = row.get("metrics", {})
        results.append({
            "id": ad.get("id"),
            "name": ad.get("name"),
            "type": ad.get("type"),
            "status": row.get("adGroupAd", {}).get("status"),
            "campaign": row.get("campaign", {}).get("name"),
            "ad_group": row.get("adGroup", {}).get("name"),
            "spend": round(int(m.get("costMicros", 0)) / 1_000_000, 2),
            "impressions": m.get("impressions"),
            "clicks": m.get("clicks"),
            "ctr": m.get("ctr"),
            "conversions": m.get("conversions"),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "ads": results})


@mcp.tool()
def gads_demographic_breakdown(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
    campaign_id: str = "",
) -> str:
    """Get Google Ads performance broken down by age range and gender demographics.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
        campaign_id: Filter by campaign ID. Leave blank for all.
    """
    sd, ed = _date_range(start_date, end_date)
    where_campaign = f"AND campaign.id = '{campaign_id}'" if campaign_id else ""

    age_rows = _search(f"""
        SELECT ad_group_criterion.age_range.type,
               metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
        FROM age_range_view
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        {where_campaign}
        ORDER BY metrics.cost_micros DESC
    """, customer_id)

    gender_rows = _search(f"""
        SELECT ad_group_criterion.gender.type,
               metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
        FROM gender_view
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        {where_campaign}
        ORDER BY metrics.cost_micros DESC
    """, customer_id)

    def _parse(rows, key_path):
        results = {}
        for row in rows:
            obj = row
            for k in key_path:
                obj = obj.get(k, {})
            label = obj if isinstance(obj, str) else str(obj)
            m = row.get("metrics", {})
            if label not in results:
                results[label] = {"spend": 0, "impressions": 0, "clicks": 0, "conversions": 0}
            results[label]["spend"] += int(m.get("costMicros", 0)) / 1_000_000
            results[label]["impressions"] = results[label]["impressions"] + int(m.get("impressions", 0) or 0)
            results[label]["clicks"] = results[label]["clicks"] + int(m.get("clicks", 0) or 0)
            results[label]["conversions"] = results[label]["conversions"] + float(m.get("conversions", 0) or 0)
        return [{"label": k, **v} for k, v in results.items()]

    return json.dumps({
        "date_range": f"{sd} to {ed}",
        "by_age": _parse(age_rows, ["adGroupCriterion", "ageRange", "type"]),
        "by_gender": _parse(gender_rows, ["adGroupCriterion", "gender", "type"]),
    })


@mcp.tool()
def gads_geo_performance(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
    row_limit: int = 25,
) -> str:
    """Get Google Ads performance broken down by geographic location (country/region/city).

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
        row_limit: Max locations. Default 25.
    """
    sd, ed = _date_range(start_date, end_date)
    rows = _search(f"""
        SELECT geographic_view.country_criterion_id, geographic_view.location_type,
               segments.geo_target_city, segments.geo_target_country, segments.geo_target_region,
               metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
        FROM geographic_view
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        ORDER BY metrics.cost_micros DESC
        LIMIT {row_limit}
    """, customer_id)
    results = []
    for row in rows:
        segs = row.get("segments", {})
        m = row.get("metrics", {})
        results.append({
            "country": segs.get("geoTargetCountry"),
            "region": segs.get("geoTargetRegion"),
            "city": segs.get("geoTargetCity"),
            "spend": round(int(m.get("costMicros", 0)) / 1_000_000, 2),
            "impressions": m.get("impressions"),
            "clicks": m.get("clicks"),
            "conversions": m.get("conversions"),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "locations": results})


@mcp.tool()
def gads_hourly_breakdown(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
) -> str:
    """Get Google Ads performance by hour of day to identify peak performing times.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 7 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    sd, ed = _date_range(start_date, end_date, default_days=7)
    rows = _search(f"""
        SELECT segments.hour, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
        FROM campaign
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        ORDER BY segments.hour
    """, customer_id)
    hourly: dict[int, dict] = {}
    for row in rows:
        hour = row.get("segments", {}).get("hour", 0)
        m = row.get("metrics", {})
        if hour not in hourly:
            hourly[hour] = {"hour": hour, "spend": 0.0, "impressions": 0, "clicks": 0, "conversions": 0.0}
        hourly[hour]["spend"] += int(m.get("costMicros", 0)) / 1_000_000
        hourly[hour]["impressions"] += int(m.get("impressions", 0) or 0)
        hourly[hour]["clicks"] += int(m.get("clicks", 0) or 0)
        hourly[hour]["conversions"] += float(m.get("conversions", 0) or 0)
    return json.dumps({"date_range": f"{sd} to {ed}", "hourly": sorted(hourly.values(), key=lambda x: x["hour"])})


@mcp.tool()
def gads_device_breakdown(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
) -> str:
    """Get Google Ads performance broken down by device type: desktop, mobile, tablet.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    sd, ed = _date_range(start_date, end_date)
    rows = _search(f"""
        SELECT segments.device, metrics.impressions, metrics.clicks,
               metrics.cost_micros, metrics.ctr, metrics.average_cpc, metrics.conversions
        FROM campaign
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        ORDER BY metrics.cost_micros DESC
    """, customer_id)
    devices: dict[str, dict] = {}
    for row in rows:
        device = row.get("segments", {}).get("device", "UNKNOWN")
        m = row.get("metrics", {})
        if device not in devices:
            devices[device] = {"device": device, "spend": 0.0, "impressions": 0, "clicks": 0, "conversions": 0.0}
        devices[device]["spend"] += int(m.get("costMicros", 0)) / 1_000_000
        devices[device]["impressions"] += int(m.get("impressions", 0) or 0)
        devices[device]["clicks"] += int(m.get("clicks", 0) or 0)
        devices[device]["conversions"] += float(m.get("conversions", 0) or 0)
    return json.dumps({"date_range": f"{sd} to {ed}", "devices": list(devices.values())})


@mcp.tool()
def gads_shopping_performance(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
    row_limit: int = 25,
) -> str:
    """Get Google Shopping campaign performance by product: clicks, impressions, spend, ROAS.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
        row_limit: Max products. Default 25.
    """
    sd, ed = _date_range(start_date, end_date)
    rows = _search(f"""
        SELECT segments.product_title, segments.product_item_id, segments.product_brand,
               metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.conversions, metrics.conversions_value
        FROM shopping_performance_view
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        ORDER BY metrics.cost_micros DESC
        LIMIT {row_limit}
    """, customer_id)
    results = []
    for row in rows:
        segs = row.get("segments", {})
        m = row.get("metrics", {})
        spend = int(m.get("costMicros", 0)) / 1_000_000
        conv_value = float(m.get("conversionsValue", 0) or 0)
        results.append({
            "title": segs.get("productTitle"),
            "item_id": segs.get("productItemId"),
            "brand": segs.get("productBrand"),
            "spend": round(spend, 2),
            "impressions": m.get("impressions"),
            "clicks": m.get("clicks"),
            "conversions": m.get("conversions"),
            "conversion_value": conv_value,
            "roas": round(conv_value / max(spend, 0.01), 2),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "products": results})


@mcp.tool()
def gads_display_performance(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
    row_limit: int = 25,
) -> str:
    """Get Google Display Network campaign performance: impressions, clicks, viewable rate, conversions.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
        row_limit: Max campaigns. Default 25.
    """
    sd, ed = _date_range(start_date, end_date)
    rows = _search(f"""
        SELECT campaign.name, campaign.advertising_channel_type,
               metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.ctr, metrics.average_cpc, metrics.conversions,
               metrics.active_view_viewability
        FROM campaign
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        AND campaign.advertising_channel_type = 'DISPLAY'
        AND campaign.status = 'ENABLED'
        ORDER BY metrics.cost_micros DESC
        LIMIT {row_limit}
    """, customer_id)
    results = []
    for row in rows:
        c = row.get("campaign", {})
        m = row.get("metrics", {})
        results.append({
            "name": c.get("name"),
            "spend": round(int(m.get("costMicros", 0)) / 1_000_000, 2),
            "impressions": m.get("impressions"),
            "clicks": m.get("clicks"),
            "ctr": m.get("ctr"),
            "conversions": m.get("conversions"),
            "viewability_rate": m.get("activeViewViewability"),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "display_campaigns": results})


@mcp.tool()
def gads_video_performance(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
    row_limit: int = 25,
) -> str:
    """Get Google Video (YouTube) campaign performance: views, view rate, CPV, conversions.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
        row_limit: Max campaigns. Default 25.
    """
    sd, ed = _date_range(start_date, end_date)
    rows = _search(f"""
        SELECT campaign.name,
               metrics.impressions, metrics.video_views, metrics.video_view_rate,
               metrics.average_cpv, metrics.cost_micros, metrics.conversions
        FROM campaign
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        AND campaign.advertising_channel_type = 'VIDEO'
        ORDER BY metrics.cost_micros DESC
        LIMIT {row_limit}
    """, customer_id)
    results = []
    for row in rows:
        c = row.get("campaign", {})
        m = row.get("metrics", {})
        results.append({
            "name": c.get("name"),
            "spend": round(int(m.get("costMicros", 0)) / 1_000_000, 2),
            "impressions": m.get("impressions"),
            "video_views": m.get("videoViews"),
            "view_rate": m.get("videoViewRate"),
            "avg_cpv": round(int(m.get("averageCpv", 0)) / 1_000_000, 6),
            "conversions": m.get("conversions"),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "video_campaigns": results})


@mcp.tool()
def gads_landing_page_performance(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
    row_limit: int = 25,
) -> str:
    """Get Google Ads landing page performance: clicks, conversions, mobile-friendliness, speed score.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
        row_limit: Max landing pages. Default 25.
    """
    sd, ed = _date_range(start_date, end_date)
    rows = _search(f"""
        SELECT landing_page_view.unexpanded_final_url,
               metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.conversions, metrics.mobile_friendly_clicks_percentage,
               metrics.speed_score
        FROM landing_page_view
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        ORDER BY metrics.clicks DESC
        LIMIT {row_limit}
    """, customer_id)
    results = []
    for row in rows:
        lp = row.get("landingPageView", {})
        m = row.get("metrics", {})
        results.append({
            "url": lp.get("unexpandedFinalUrl"),
            "spend": round(int(m.get("costMicros", 0)) / 1_000_000, 2),
            "impressions": m.get("impressions"),
            "clicks": m.get("clicks"),
            "conversions": m.get("conversions"),
            "mobile_friendly_rate": m.get("mobileFriendlyClicksPercentage"),
            "speed_score": m.get("speedScore"),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "landing_pages": results})


@mcp.tool()
def gads_audience_performance(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
    row_limit: int = 25,
) -> str:
    """Get Google Ads performance for each audience segment or user list.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
        row_limit: Max audiences. Default 25.
    """
    sd, ed = _date_range(start_date, end_date)
    rows = _search(f"""
        SELECT user_list.name, campaign.name,
               metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
        FROM campaign_audience_view
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        ORDER BY metrics.cost_micros DESC
        LIMIT {row_limit}
    """, customer_id)
    results = []
    for row in rows:
        ul = row.get("userList", {})
        m = row.get("metrics", {})
        results.append({
            "audience": ul.get("name"),
            "campaign": row.get("campaign", {}).get("name"),
            "spend": round(int(m.get("costMicros", 0)) / 1_000_000, 2),
            "impressions": m.get("impressions"),
            "clicks": m.get("clicks"),
            "conversions": m.get("conversions"),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "audiences": results})


@mcp.tool()
def gads_conversion_actions(customer_id: str = "") -> str:
    """List all conversion actions configured in the Google Ads account.

    Args:
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    rows = _search("""
        SELECT conversion_action.id, conversion_action.name, conversion_action.status,
               conversion_action.type, conversion_action.category,
               conversion_action.value_settings.default_value
        FROM conversion_action
        WHERE conversion_action.status = 'ENABLED'
    """, customer_id)
    results = []
    for row in rows:
        ca = row.get("conversionAction", {})
        results.append({
            "id": ca.get("id"),
            "name": ca.get("name"),
            "type": ca.get("type"),
            "category": ca.get("category"),
            "default_value": ca.get("valueSettings", {}).get("defaultValue"),
        })
    return json.dumps({"conversion_actions": results, "total": len(results)})


@mcp.tool()
def gads_budget_pacing(customer_id: str = "") -> str:
    """Get budget pacing for all active campaigns — daily budget, amount spent, and percentage used.

    Args:
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    today = str(date.today())
    rows = _search(f"""
        SELECT campaign.name, campaign.status, campaign_budget.amount_micros,
               metrics.cost_micros
        FROM campaign
        WHERE segments.date = '{today}'
        AND campaign.status = 'ENABLED'
        ORDER BY metrics.cost_micros DESC
    """, customer_id)
    results = []
    for row in rows:
        c = row.get("campaign", {})
        cb = row.get("campaignBudget", {})
        m = row.get("metrics", {})
        budget = int(cb.get("amountMicros", 0)) / 1_000_000
        spent = int(m.get("costMicros", 0)) / 1_000_000
        pct = round(spent / max(budget, 0.01) * 100, 1)
        results.append({
            "campaign": c.get("name"),
            "daily_budget": round(budget, 2),
            "spent_today": round(spent, 2),
            "pacing_pct": f"{pct}%",
        })
    return json.dumps({"date": today, "campaigns": results})


@mcp.tool()
def gads_auction_insights(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
    campaign_id: str = "",
) -> str:
    """Get Google Ads auction insights: impression share, overlap rate, outranking share vs competitors.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
        campaign_id: Filter by campaign ID. Leave blank for all.
    """
    sd, ed = _date_range(start_date, end_date)
    where_campaign = f"AND campaign.id = '{campaign_id}'" if campaign_id else ""
    rows = _search(f"""
        SELECT auction_insight.domain,
               metrics.search_impression_share, metrics.search_overlap_rate,
               metrics.search_outranking_share, metrics.search_top_impression_share,
               metrics.search_absolute_top_impression_share
        FROM auction_insight
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        {where_campaign}
        ORDER BY metrics.search_impression_share DESC
    """, customer_id)
    results = []
    for row in rows:
        ai = row.get("auctionInsight", {})
        m = row.get("metrics", {})
        results.append({
            "domain": ai.get("domain"),
            "impression_share": m.get("searchImpressionShare"),
            "overlap_rate": m.get("searchOverlapRate"),
            "outranking_share": m.get("searchOutrankingShare"),
            "top_impression_share": m.get("searchTopImpressionShare"),
            "absolute_top_impression_share": m.get("searchAbsoluteTopImpressionShare"),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "competitors": results})


@mcp.tool()
def gads_change_history(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
    row_limit: int = 25,
) -> str:
    """Get recent change history in the Google Ads account: what was changed, when, and by whom.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 7 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
        row_limit: Max changes. Default 25.
    """
    sd, ed = _date_range(start_date, end_date, default_days=7)
    rows = _search(f"""
        SELECT change_event.change_date_time, change_event.changed_fields,
               change_event.resource_type, change_event.change_resource_name,
               change_event.user_email
        FROM change_event
        WHERE change_event.change_date_time BETWEEN '{sd} 00:00:00' AND '{ed} 23:59:59'
        ORDER BY change_event.change_date_time DESC
        LIMIT {row_limit}
    """, customer_id)
    results = []
    for row in rows:
        ce = row.get("changeEvent", {})
        results.append({
            "date_time": ce.get("changeDateTimeYear"),
            "resource_type": ce.get("resourceType"),
            "resource": ce.get("changeResourceName"),
            "changed_fields": ce.get("changedFields"),
            "user": ce.get("userEmail"),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "changes": results})


@mcp.tool()
def gads_quality_score(
    customer_id: str = "",
    campaign_id: str = "",
    row_limit: int = 50,
) -> str:
    """Get quality scores for all keywords: overall score, landing page experience, expected CTR, ad relevance.

    Args:
        customer_id: Google Ads customer ID. Leave blank to use default.
        campaign_id: Filter by campaign ID. Leave blank for all.
        row_limit: Max keywords. Default 50.
    """
    where_campaign = f"AND campaign.id = '{campaign_id}'" if campaign_id else ""
    rows = _search(f"""
        SELECT ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type,
               ad_group_criterion.quality_info.quality_score,
               ad_group_criterion.quality_info.creative_quality_score,
               ad_group_criterion.quality_info.post_click_quality_score,
               ad_group_criterion.quality_info.search_predicted_ctr,
               campaign.name, ad_group.name
        FROM keyword_view
        WHERE ad_group_criterion.status != 'REMOVED'
        AND ad_group_criterion.quality_info.quality_score > 0
        {where_campaign}
        ORDER BY ad_group_criterion.quality_info.quality_score ASC
        LIMIT {row_limit}
    """, customer_id)
    results = []
    for row in rows:
        kw = row.get("adGroupCriterion", {})
        qi = kw.get("qualityInfo", {})
        results.append({
            "keyword": kw.get("keyword", {}).get("text"),
            "match_type": kw.get("keyword", {}).get("matchType"),
            "quality_score": qi.get("qualityScore"),
            "ad_relevance": qi.get("creativeQualityScore"),
            "landing_page_exp": qi.get("postClickQualityScore"),
            "expected_ctr": qi.get("searchPredictedCtr"),
            "campaign": row.get("campaign", {}).get("name"),
            "ad_group": row.get("adGroup", {}).get("name"),
        })
    return json.dumps({"keywords": results, "total": len(results)})


@mcp.tool()
def gads_call_metrics(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
) -> str:
    """Get Google Ads call extension metrics: calls, call conversions, average call duration.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    sd, ed = _date_range(start_date, end_date)
    rows = _search(f"""
        SELECT campaign.name, metrics.phone_calls, metrics.phone_impressions,
               metrics.phone_through_rate, metrics.average_cost
        FROM campaign
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        AND metrics.phone_calls > 0
        ORDER BY metrics.phone_calls DESC
    """, customer_id)
    results = []
    for row in rows:
        m = row.get("metrics", {})
        results.append({
            "campaign": row.get("campaign", {}).get("name"),
            "phone_calls": m.get("phoneCalls"),
            "phone_impressions": m.get("phoneImpressions"),
            "phone_through_rate": m.get("phoneThroughRate"),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "call_metrics": results})


@mcp.tool()
def gads_extension_performance(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
) -> str:
    """Get Google Ads ad extension performance: sitelinks, callouts, structured snippets.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    sd, ed = _date_range(start_date, end_date)
    rows = _search(f"""
        SELECT extension_feed_item.extension_type, extension_feed_item.status,
               campaign.name, metrics.impressions, metrics.clicks, metrics.cost_micros
        FROM extension_feed_item
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        AND extension_feed_item.status = 'ENABLED'
        ORDER BY metrics.clicks DESC
        LIMIT 50
    """, customer_id)
    results = []
    for row in rows:
        efi = row.get("extensionFeedItem", {})
        m = row.get("metrics", {})
        results.append({
            "type": efi.get("extensionType"),
            "status": efi.get("status"),
            "campaign": row.get("campaign", {}).get("name"),
            "impressions": m.get("impressions"),
            "clicks": m.get("clicks"),
            "spend": round(int(m.get("costMicros", 0)) / 1_000_000, 2),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "extensions": results})


@mcp.tool()
def gads_recommendations(customer_id: str = "") -> str:
    """Get Google Ads optimization recommendations for the account.

    Args:
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    rows = _search("""
        SELECT recommendation.type, recommendation.impact.base_metrics.impressions,
               recommendation.impact.potential_metrics.impressions,
               recommendation.campaign, recommendation.dismissed
        FROM recommendation
        WHERE recommendation.dismissed = FALSE
        LIMIT 25
    """, customer_id)
    results = []
    for row in rows:
        rec = row.get("recommendation", {})
        impact = rec.get("impact", {})
        base = impact.get("baseMetrics", {})
        potential = impact.get("potentialMetrics", {})
        results.append({
            "type": rec.get("type"),
            "campaign": rec.get("campaign"),
            "base_impressions": base.get("impressions"),
            "potential_impressions": potential.get("impressions"),
        })
    return json.dumps({"recommendations": results, "total": len(results)})


@mcp.tool()
def gads_asset_report(
    start_date: str = "",
    end_date: str = "",
    customer_id: str = "",
    row_limit: int = 25,
) -> str:
    """Get Google Ads asset performance (headlines and descriptions for responsive ads): clicks, impressions, performance rating.

    Args:
        start_date: Start date YYYY-MM-DD. Defaults to 28 days ago.
        end_date: End date YYYY-MM-DD. Defaults to today.
        customer_id: Google Ads customer ID. Leave blank to use default.
        row_limit: Max assets. Default 25.
    """
    sd, ed = _date_range(start_date, end_date)
    rows = _search(f"""
        SELECT ad_group_ad_asset_view.field_type, ad_group_ad_asset_view.performance_label,
               asset.text_asset.text, asset.type,
               campaign.name, metrics.impressions, metrics.clicks
        FROM ad_group_ad_asset_view
        WHERE segments.date BETWEEN '{sd}' AND '{ed}'
        AND ad_group_ad_asset_view.enabled = TRUE
        ORDER BY metrics.impressions DESC
        LIMIT {row_limit}
    """, customer_id)
    results = []
    for row in rows:
        av = row.get("adGroupAdAssetView", {})
        a = row.get("asset", {})
        m = row.get("metrics", {})
        results.append({
            "text": a.get("textAsset", {}).get("text"),
            "field_type": av.get("fieldType"),
            "performance": av.get("performanceLabel"),
            "campaign": row.get("campaign", {}).get("name"),
            "impressions": m.get("impressions"),
            "clicks": m.get("clicks"),
        })
    return json.dumps({"date_range": f"{sd} to {ed}", "assets": results})


@mcp.tool()
def gads_list_labels(customer_id: str = "") -> str:
    """List all labels defined in the Google Ads account.

    Args:
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    rows = _search("""
        SELECT label.id, label.name, label.status, label.text_label.background_color
        FROM label
    """, customer_id)
    results = []
    for row in rows:
        lbl = row.get("label", {})
        results.append({
            "id": lbl.get("id"),
            "name": lbl.get("name"),
            "status": lbl.get("status"),
            "color": lbl.get("textLabel", {}).get("backgroundColor"),
        })
    return json.dumps({"labels": results, "total": len(results)})


# ---------------------------------------------------------------------------
# Management Tools (write)
# ---------------------------------------------------------------------------

@mcp.tool()
def gads_create_budget(
    name: str,
    amount_per_day: float,
    delivery_method: str = "STANDARD",
    customer_id: str = "",
) -> str:
    """Create a new shared campaign budget in Google Ads.

    Args:
        name: Budget name (required).
        amount_per_day: Daily budget amount in the account's currency, e.g. 50.00 for $50 (required).
        delivery_method: STANDARD or ACCELERATED. Default STANDARD.
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    cid = _resolve_customer(customer_id)
    amount_micros = int(amount_per_day * 1_000_000)
    result = _mutate("campaignBudgets", [{
        "create": {
            "name": name,
            "amountMicros": str(amount_micros),
            "deliveryMethod": delivery_method,
        }
    }], customer_id)
    return json.dumps(result)


@mcp.tool()
def gads_create_campaign(
    name: str,
    budget_id: str,
    advertising_channel_type: str = "SEARCH",
    status: str = "PAUSED",
    bidding_strategy: str = "MANUAL_CPC",
    customer_id: str = "",
) -> str:
    """Create a new Google Ads campaign.

    Args:
        name: Campaign name (required).
        budget_id: Campaign budget resource name or ID, e.g. '1234567890' (required).
        advertising_channel_type: SEARCH, DISPLAY, VIDEO, SHOPPING, or PERFORMANCE_MAX. Default SEARCH.
        status: ENABLED or PAUSED. Default PAUSED.
        bidding_strategy: MANUAL_CPC, TARGET_CPA, TARGET_ROAS, or MAXIMIZE_CONVERSIONS. Default MANUAL_CPC.
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    cid = _resolve_customer(customer_id)
    budget_rn = budget_id if budget_id.startswith("customers/") else f"customers/{cid}/campaignBudgets/{budget_id}"
    campaign_obj = {
        "name": name,
        "campaignBudget": budget_rn,
        "advertisingChannelType": advertising_channel_type,
        "status": status,
    }
    # Set bidding strategy
    if bidding_strategy == "MANUAL_CPC":
        campaign_obj["manualCpc"] = {}
    elif bidding_strategy == "TARGET_CPA":
        campaign_obj["targetCpa"] = {}
    elif bidding_strategy == "TARGET_ROAS":
        campaign_obj["targetRoas"] = {}
    elif bidding_strategy == "MAXIMIZE_CONVERSIONS":
        campaign_obj["maximizeConversions"] = {}

    result = _mutate("campaigns", [{"create": campaign_obj}], customer_id)
    return json.dumps(result)


@mcp.tool()
def gads_create_adgroup(
    name: str,
    campaign_id: str,
    cpc_bid_micros: int = 1000000,
    status: str = "PAUSED",
    customer_id: str = "",
) -> str:
    """Create a new ad group within a Google Ads campaign.

    Args:
        name: Ad group name (required).
        campaign_id: Parent campaign ID (required).
        cpc_bid_micros: Default CPC bid in micros, e.g. 1000000 for $1.00. Default 1000000.
        status: ENABLED or PAUSED. Default PAUSED.
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    cid = _resolve_customer(customer_id)
    campaign_rn = f"customers/{cid}/campaigns/{campaign_id}"
    result = _mutate("adGroups", [{
        "create": {
            "name": name,
            "campaign": campaign_rn,
            "cpcBidMicros": str(cpc_bid_micros),
            "status": status,
        }
    }], customer_id)
    return json.dumps(result)


@mcp.tool()
def gads_add_keywords(
    adgroup_id: str,
    keywords_json: str,
    campaign_id: str,
    customer_id: str = "",
) -> str:
    """Add keywords to a Google Ads ad group.

    Args:
        adgroup_id: Ad group ID to add keywords to (required).
        keywords_json: JSON array of keyword objects, e.g. '[{"text": "running shoes", "match_type": "BROAD", "cpc_bid_micros": 800000}]' (required).
            match_type options: BROAD, PHRASE, EXACT.
        campaign_id: Parent campaign ID (required).
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    cid = _resolve_customer(customer_id)
    adgroup_rn = f"customers/{cid}/adGroups/{adgroup_id}"
    keywords = json.loads(keywords_json)
    operations = []
    for kw in keywords:
        op = {
            "create": {
                "adGroup": adgroup_rn,
                "status": "ENABLED",
                "keyword": {
                    "text": kw["text"],
                    "matchType": kw.get("match_type", "BROAD"),
                },
            }
        }
        if kw.get("cpc_bid_micros"):
            op["create"]["cpcBidMicros"] = str(kw["cpc_bid_micros"])
        operations.append(op)
    result = _mutate("adGroupCriteria", operations, customer_id)
    return json.dumps(result)


@mcp.tool()
def gads_add_negative_keywords(
    campaign_id: str,
    keywords_json: str,
    customer_id: str = "",
) -> str:
    """Add negative keywords at the campaign level to exclude irrelevant traffic.

    Args:
        campaign_id: Campaign ID to add negative keywords to (required).
        keywords_json: JSON array of objects, e.g. '[{"text": "free", "match_type": "BROAD"}, {"text": "cheap shoes", "match_type": "EXACT"}]' (required).
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    cid = _resolve_customer(customer_id)
    campaign_rn = f"customers/{cid}/campaigns/{campaign_id}"
    keywords = json.loads(keywords_json)
    operations = []
    for kw in keywords:
        operations.append({
            "create": {
                "campaign": campaign_rn,
                "keyword": {
                    "text": kw["text"],
                    "matchType": kw.get("match_type", "BROAD"),
                },
                "negative": True,
            }
        })
    result = _mutate("campaignCriteria", operations, customer_id)
    return json.dumps(result)


@mcp.tool()
def gads_update_campaign_status(
    campaign_id: str,
    status: str,
    customer_id: str = "",
) -> str:
    """Update the status of a Google Ads campaign: enable, pause, or remove it.

    Args:
        campaign_id: Campaign ID to update (required).
        status: New status: ENABLED, PAUSED, or REMOVED (required).
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    cid = _resolve_customer(customer_id)
    campaign_rn = f"customers/{cid}/campaigns/{campaign_id}"
    result = _mutate("campaigns", [{
        "update": {"resourceName": campaign_rn, "status": status},
        "updateMask": "status",
    }], customer_id)
    return json.dumps(result)


@mcp.tool()
def gads_update_adgroup_status(
    adgroup_id: str,
    campaign_id: str,
    status: str,
    customer_id: str = "",
) -> str:
    """Update the status of a Google Ads ad group: enable, pause, or remove it.

    Args:
        adgroup_id: Ad group ID to update (required).
        campaign_id: Parent campaign ID (required).
        status: New status: ENABLED, PAUSED, or REMOVED (required).
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    cid = _resolve_customer(customer_id)
    adgroup_rn = f"customers/{cid}/adGroups/{adgroup_id}"
    result = _mutate("adGroups", [{
        "update": {"resourceName": adgroup_rn, "status": status},
        "updateMask": "status",
    }], customer_id)
    return json.dumps(result)


@mcp.tool()
def gads_update_keyword_status(
    adgroup_id: str,
    criterion_id: str,
    status: str,
    customer_id: str = "",
) -> str:
    """Update the status of a keyword in a Google Ads ad group.

    Args:
        adgroup_id: Ad group ID containing the keyword (required).
        criterion_id: Keyword criterion ID to update (required).
        status: New status: ENABLED, PAUSED, or REMOVED (required).
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    cid = _resolve_customer(customer_id)
    criterion_rn = f"customers/{cid}/adGroupCriteria/{adgroup_id}~{criterion_id}"
    result = _mutate("adGroupCriteria", [{
        "update": {"resourceName": criterion_rn, "status": status},
        "updateMask": "status",
    }], customer_id)
    return json.dumps(result)


@mcp.tool()
def gads_update_keyword_bid(
    adgroup_id: str,
    criterion_id: str,
    cpc_bid_micros: int,
    customer_id: str = "",
) -> str:
    """Update the CPC bid for a specific keyword in Google Ads.

    Args:
        adgroup_id: Ad group ID containing the keyword (required).
        criterion_id: Keyword criterion ID to update (required).
        cpc_bid_micros: New CPC bid in micros, e.g. 2000000 for $2.00 (required).
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    cid = _resolve_customer(customer_id)
    criterion_rn = f"customers/{cid}/adGroupCriteria/{adgroup_id}~{criterion_id}"
    result = _mutate("adGroupCriteria", [{
        "update": {"resourceName": criterion_rn, "cpcBidMicros": str(cpc_bid_micros)},
        "updateMask": "cpc_bid_micros",
    }], customer_id)
    return json.dumps(result)


@mcp.tool()
def gads_update_campaign_budget(
    budget_id: str,
    amount_per_day: float,
    customer_id: str = "",
) -> str:
    """Update the daily budget amount for a Google Ads campaign budget.

    Args:
        budget_id: Campaign budget ID to update (required).
        amount_per_day: New daily budget in the account's currency, e.g. 100.00 for $100 (required).
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    cid = _resolve_customer(customer_id)
    budget_rn = f"customers/{cid}/campaignBudgets/{budget_id}"
    amount_micros = int(amount_per_day * 1_000_000)
    result = _mutate("campaignBudgets", [{
        "update": {"resourceName": budget_rn, "amountMicros": str(amount_micros)},
        "updateMask": "amount_micros",
    }], customer_id)
    return json.dumps(result)


@mcp.tool()
def gads_create_responsive_search_ad(
    adgroup_id: str,
    campaign_id: str,
    final_url: str,
    headlines: list[str],
    descriptions: list[str],
    path1: str = "",
    path2: str = "",
    status: str = "PAUSED",
    customer_id: str = "",
) -> str:
    """Create a Responsive Search Ad (RSA) in a Google Ads ad group.

    Args:
        adgroup_id: Ad group ID to add the ad to (required).
        campaign_id: Parent campaign ID (required).
        final_url: The destination URL for the ad (required).
        headlines: List of 3–15 headline strings, max 30 characters each (required).
        descriptions: List of 2–4 description strings, max 90 characters each (required).
        path1: First URL display path, max 15 chars. Optional.
        path2: Second URL display path, max 15 chars. Optional.
        status: ENABLED or PAUSED. Default PAUSED.
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    cid = _resolve_customer(customer_id)
    adgroup_rn = f"customers/{cid}/adGroups/{adgroup_id}"
    ad_obj = {
        "adGroup": adgroup_rn,
        "status": status,
        "ad": {
            "finalUrls": [final_url],
            "responsiveSearchAd": {
                "headlines": [{"text": h} for h in headlines],
                "descriptions": [{"text": d} for d in descriptions],
            },
        },
    }
    if path1:
        ad_obj["ad"]["responsiveSearchAd"]["path1"] = path1
    if path2:
        ad_obj["ad"]["responsiveSearchAd"]["path2"] = path2
    result = _mutate("adGroupAds", [{"create": ad_obj}], customer_id)
    return json.dumps(result)


@mcp.tool()
def gads_pause_all_campaigns(customer_id: str = "") -> str:
    """Pause ALL active campaigns in the Google Ads account. Use with caution — this will pause all spending.

    Args:
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    rows = _search("""
        SELECT campaign.id, campaign.name
        FROM campaign
        WHERE campaign.status = 'ENABLED'
    """, customer_id)
    cid = _resolve_customer(customer_id)
    if not rows:
        return json.dumps({"message": "No enabled campaigns found.", "paused": 0})
    operations = []
    for row in rows:
        campaign_id = row.get("campaign", {}).get("id")
        campaign_rn = f"customers/{cid}/campaigns/{campaign_id}"
        operations.append({
            "update": {"resourceName": campaign_rn, "status": "PAUSED"},
            "updateMask": "status",
        })
    result = _mutate("campaigns", operations, customer_id)
    return json.dumps({"paused_count": len(operations), "result": result})


@mcp.tool()
def gads_enable_campaign(
    campaign_id: str,
    customer_id: str = "",
) -> str:
    """Enable (un-pause) a specific Google Ads campaign.

    Args:
        campaign_id: Campaign ID to enable (required).
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    cid = _resolve_customer(customer_id)
    campaign_rn = f"customers/{cid}/campaigns/{campaign_id}"
    result = _mutate("campaigns", [{
        "update": {"resourceName": campaign_rn, "status": "ENABLED"},
        "updateMask": "status",
    }], customer_id)
    return json.dumps(result)


@mcp.tool()
def gads_apply_recommendation(
    recommendation_resource_name: str,
    customer_id: str = "",
) -> str:
    """Apply a Google Ads optimization recommendation.

    Args:
        recommendation_resource_name: Full resource name of the recommendation, e.g. 'customers/123/recommendations/456' (required).
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    cid = _resolve_customer(customer_id)
    resp = requests.post(
        f"{GADS_BASE}/customers/{cid}/recommendations:apply",
        headers=_headers(),
        json={"operations": [{"resourceName": recommendation_resource_name}]},
        timeout=30,
    )
    if not resp.ok:
        return json.dumps({"error": resp.text[:400]})
    return json.dumps(resp.json())


@mcp.tool()
def gads_dismiss_recommendation(
    recommendation_resource_name: str,
    customer_id: str = "",
) -> str:
    """Dismiss a Google Ads optimization recommendation so it no longer appears.

    Args:
        recommendation_resource_name: Full resource name of the recommendation, e.g. 'customers/123/recommendations/456' (required).
        customer_id: Google Ads customer ID. Leave blank to use default.
    """
    cid = _resolve_customer(customer_id)
    resp = requests.post(
        f"{GADS_BASE}/customers/{cid}/recommendations:dismiss",
        headers=_headers(),
        json={"operations": [{"resourceName": recommendation_resource_name}]},
        timeout=30,
    )
    if not resp.ok:
        return json.dumps({"error": resp.text[:400]})
    return json.dumps(resp.json())


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
