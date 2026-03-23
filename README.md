# Google Ads MCP Server

A standalone MCP server that exposes **42 Google Ads tools** for use with Claude Desktop, Cursor, or any MCP-compatible AI client.

## Tools

### Analytics (read)

| Tool | Description |
|------|-------------|
| `get_gads_overview` | Account-level metrics summary |
| `get_gads_campaigns` | Campaign performance list |
| `get_gads_keywords` | Top keywords with bids and QS |
| `get_gads_search_terms` | Actual search terms triggering ads |
| `get_gads_ad_groups` | Ad group performance |
| `get_gads_daily_trend` | Day-by-day spend, clicks, conversions |
| `get_gads_ads` | Individual ad creative performance |
| `get_gads_geo` | Geographic performance |
| `get_gads_device_breakdown` | Desktop vs mobile vs tablet |
| `get_gads_hourly_trend` | Hour and day-of-week performance |
| `get_gads_audiences` | Audience segment performance |
| `get_gads_extensions` | Sitelink, callout, call extension performance |
| `get_gads_shopping` | Shopping product performance |
| `get_gads_pmax` | Performance Max asset group results |
| `get_keyword_ideas` | Keyword Planner — volume, competition, bids |
| `gads_get_demographics` | Performance by gender and age range |
| `gads_get_landing_pages` | Landing page performance |
| `gads_get_paid_organic` | Paid vs organic overlap |
| `gads_get_bidding_strategies` | List portfolio bidding strategies |
| `gads_get_asset_report` | PMax asset performance labels |
| `gads_list_customer_accounts` | List all MCC accessible accounts |
| `gads_get_billing_info` | Account billing status |
| `gads_get_change_history` | Recent account change events |
| `gads_get_recommendations` | Google's optimization suggestions |
| `gads_get_conversion_actions` | List all tracked conversions |
| `gads_get_label_performance` | Performance grouped by label |

### Management (write)

| Tool | Description |
|------|-------------|
| `gads_update_status` | Pause or enable a campaign/ad group |
| `gads_update_budget` | Change campaign budget |
| `gads_create_campaign` | Create a Search campaign with budget |
| `gads_create_ad_group` | Create an ad group |
| `gads_add_keywords` | Add keywords to an ad group |
| `gads_add_negative_keywords` | Add negative keywords |
| `gads_create_responsive_search_ad` | Create a Responsive Search Ad |
| `gads_update_keyword_bid` | Update CPC bid on a keyword |
| `gads_apply_recommendation` | Apply a recommendation |
| `gads_update_ad` | Pause/enable/remove an individual ad |
| `gads_create_sitelink` | Add a sitelink asset to a campaign |
| `gads_create_conversion_action` | Create a new conversion action |
| `gads_create_label` | Create a label |
| `gads_apply_label` | Apply a label to a campaign/ad group |
| `gads_duplicate_campaign` | Duplicate an existing campaign |
| `gads_get_keyword_forecast` | Forecast impressions/clicks/cost |

## Setup

### Step 1 — Install dependencies

```bash
pip install -r requirements.txt
```

---

### Step 2 — Get a Google Ads Developer Token

The developer token identifies your app to the Google Ads API. It is **separate from OAuth credentials**.

1. Sign in to [ads.google.com](https://ads.google.com) — you need a **Manager (MCC) account**
   - If you only have a regular advertiser account, go to [ads.google.com/intl/en_us/home/tools/manager-accounts/](https://ads.google.com/intl/en_us/home/tools/manager-accounts/) to create a free manager account
2. In the top navigation click **Tools & Settings** (wrench icon)
3. Under **Setup**, click **API Center**
4. Accept the Google Ads API Terms of Service
5. Your **Developer Token** is displayed — copy it

> Initial access level is **Test account** — you can make API calls but only against test accounts. To use the API against real accounts, click **Apply for Basic Access** and fill out the form. Google usually approves within a few days.

```env
GOOGLE_ADS_DEVELOPER_TOKEN=AbCdEfGhIjKlMnOp12345678
```

---

### Step 3 — Create a Google Cloud project & OAuth 2.0 credentials

This gives you `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.

1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Click the project dropdown at the top → **New Project** → give it a name → **Create**
3. With your new project selected, go to **APIs & Services → Library**
4. Search **Google Ads API** — if you see it, you can optionally enable it (the REST API used here doesn't strictly require this, but it enables quota tracking in the console)
5. Go to **APIs & Services → OAuth consent screen**
   - User Type: **External** → **Create**
   - Fill in *App name* (e.g. `Ads MCP`), *support email*, *developer email* → **Save and Continue**
   - On the Scopes step, click **Add or Remove Scopes** → search `adwords` → select `https://www.googleapis.com/auth/adwords` → **Update** → **Save and Continue**
   - On the Test Users step, add your own Google email → **Save and Continue**
6. Go to **APIs & Services → Credentials**
7. Click **+ Create Credentials → OAuth 2.0 Client ID**
   - Application type: **Desktop app**
   - Name: anything (e.g. `Ads MCP client`)
   - Click **Create**
8. Copy the **Client ID** and **Client Secret** shown in the dialog

```env
GOOGLE_CLIENT_ID=123456789-abc.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxxxxxx
```

---

### Step 4 — Get a refresh token

Run the included helper script. It opens a browser, you sign in with the Google account that has access to your Google Ads account, and it prints your refresh token.

```bash
python get_token.py
```

> If the browser does not open automatically, copy the URL printed in the terminal and paste it manually.  
> Make sure you sign in with the **same Google account** that is linked to your Google Ads account.

Copy the printed value:

```env
GOOGLE_REFRESH_TOKEN=1//0gxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

### Step 5 — Find your Customer ID(s)

**`GOOGLE_ADS_CUSTOMER_ID`** — the advertiser account you want to query:
1. Sign in to [ads.google.com](https://ads.google.com)
2. Your 10-digit customer ID is shown in the **top-right corner**, formatted as `123-456-7890`
3. Remove the dashes: `1234567890`

```env
GOOGLE_ADS_CUSTOMER_ID=1234567890
```

**`GOOGLE_ADS_LOGIN_CUSTOMER_ID`** — only needed if you access client accounts through a Manager (MCC) account:
- If you manage multiple client accounts via an MCC, set this to your **manager account's customer ID** (same format — top-right corner when logged into the manager account)
- If you are directly logged into a single advertiser account with no MCC, **leave this blank**

```env
GOOGLE_ADS_LOGIN_CUSTOMER_ID=   # leave blank if not using MCC
```

---

### Step 6 — Fill in your .env file

```bash
cp .env.example .env
```

Open `.env` and paste all values:

```env
GOOGLE_CLIENT_ID=123456789-abc.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxxxxxx
GOOGLE_REFRESH_TOKEN=1//0gxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GOOGLE_ADS_DEVELOPER_TOKEN=AbCdEfGhIjKlMnOp12345678
GOOGLE_ADS_CUSTOMER_ID=1234567890
GOOGLE_ADS_LOGIN_CUSTOMER_ID=   # optional — only for MCC users
```

---

### Step 7 — Test the server

```bash
python server.py
```

You should see the server start with no errors. Press `Ctrl+C` to stop.

---

### Step 8 — Add to Claude Desktop

Config file location:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "google-ads": {
      "command": "python",
      "args": ["C:/absolute/path/to/mcp-google-ads/server.py"],
      "env": {
        "GOOGLE_CLIENT_ID": "123456789-abc.apps.googleusercontent.com",
        "GOOGLE_CLIENT_SECRET": "GOCSPX-xxxxxxxxxxxxxxxxxxxx",
        "GOOGLE_REFRESH_TOKEN": "1//0gxxxxxxxxxx",
        "GOOGLE_ADS_DEVELOPER_TOKEN": "AbCdEfGhIjKlMnOp12345678",
        "GOOGLE_ADS_CUSTOMER_ID": "1234567890",
        "GOOGLE_ADS_LOGIN_CUSTOMER_ID": ""
      }
    }
  }
}
```

Restart Claude Desktop after saving. You should see "google-ads" in the MCP servers list.

---

## Campaign creation flow

```
gads_create_budget → gads_create_campaign → gads_create_adgroup → gads_add_keywords → gads_create_responsive_search_ad
```

## Example prompts

- "Create a Search campaign called 'Brand' with a $20/day budget"
- "What are my top keywords by spend this month?"
- "Add negative keyword 'free' to my main campaign"
- "Show me keyword ideas for 'running shoes'"
- "Forecast clicks for keywords: ['buy shoes online', 'running shoes']"
- "Apply all pending recommendations"
