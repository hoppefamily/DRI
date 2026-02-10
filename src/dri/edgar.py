"""SEC EDGAR 13F filing fetcher and parser."""
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

import requests
from lxml import etree

logger = logging.getLogger(__name__)


@dataclass
class Holding:
    """A single holding from a 13F filing."""
    cusip: str
    name: str
    value: float       # USD (in thousands as reported)
    shares: int
    type: str         # e.g., "SH" for shares, "PRN" for principal amount


@dataclass
class Filing:
    """A complete 13F-HR filing."""
    cik: str
    filing_date: date
    report_date: date  # Quarter-end date
    total_value: float  # Total USD value of all holdings
    holdings_count: int
    holdings: List[Holding]


class EDGARFetcher:
    """Fetch and parse 13F-HR filings from SEC EDGAR."""

    def __init__(self, config: dict):
        """Initialize with configuration."""
        self.config = config["edgar"]
        self.base_url = self.config["base_url"]
        self.user_agent = self.config["user_agent"]
        self.rate_limit = self.config["rate_limit_per_sec"]
        self.retry_attempts = self.config["retry_attempts"]
        self.retry_delay = self.config["retry_delay_sec"]
        self.last_request_time = 0

        if not self.user_agent:
            raise ValueError("SEC User-Agent is required")

    def _rate_limit_sleep(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        min_interval = 1.0 / self.rate_limit
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, url: str) -> requests.Response:
        """Make HTTP request with rate limiting and retries."""
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

        for attempt in range(self.retry_attempts):
            try:
                self._rate_limit_sleep()
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.retry_attempts}): {e}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise

    def fetch_13f_filings(
        self,
        cik: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        quarters: Optional[int] = None,
    ) -> List[Filing]:
        """
        Fetch 13F-HR filings for a CIK.

        Args:
            cik: Central Index Key (10-digit with leading zeros)
            start_date: Earliest filing date to fetch
            end_date: Latest filing date to fetch
            quarters: Number of recent quarters to fetch (alternative to date range)

        Returns:
            List of Filing objects sorted by report_date (oldest first)
        """
        # Pad CIK to 10 digits
        cik_padded = cik.zfill(10)

        # Get filing index
        filings_metadata = self._get_filings_metadata(cik_padded, start_date, end_date, quarters)

        # Fetch and parse each filing
        filings = []
        for metadata in filings_metadata:
            try:
                filing = self._fetch_and_parse_filing(cik_padded, metadata)
                filings.append(filing)
                logger.info(f"Fetched: filing {metadata['accession']} for {metadata['report_date']}")
            except Exception as e:
                logger.error(f"Failed to parse filing {metadata['accession']}: {e}")
                continue

        # Sort by report date
        filings.sort(key=lambda f: f.report_date)
        return filings

    def _get_filings_metadata(
        self,
        cik: str,
        start_date: Optional[date],
        end_date: Optional[date],
        quarters: Optional[int],
    ) -> List[dict]:
        """Get list of 13F filing metadata from SEC submissions endpoint."""
        url = f"{self.base_url}/cgi-bin/browse-edgar"
        params = {
            "action": "getcompany",
            "CIK": cik,
            "type": "13F-HR",
            "dateb": "",
            "owner": "exclude",
            "count": quarters * 2 if quarters else 100,  # Get extra in case of amendments
            "output": "atom",
        }

        response = self._make_request(url + "?" + "&".join(f"{k}={v}" for k, v in params.items()))

        # Parse Atom feed
        root = etree.fromstring(response.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        filings = []
        for entry in root.findall("atom:entry", ns):
            # Extract filing metadata
            filing_href = entry.find("atom:link[@type='text/html']", ns)
            if filing_href is None:
                continue

            link = filing_href.get("href")
            accession = link.split("accession-number=")[-1] if "accession-number=" in link else ""

            # Extract filing date from updated field
            updated = entry.find("atom:updated", ns)
            if updated is not None:
                filing_date_str = updated.text.split("T")[0]
                filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d").date()
            else:
                continue

            # For 13F-HR, report date must be extracted from document (done later)
            filings.append({
                "accession": accession,
                "filing_date": filing_date,
                "link": link,
            })

        # Filter by date range if specified
        if start_date:
            filings = [f for f in filings if f["filing_date"] >= start_date]
        if end_date:
            filings = [f for f in filings if f["filing_date"] <= end_date]

        # Limit to requested quarters
        if quarters:
            # Keep only non-amendments (one per quarter)
            seen_quarters = set()
            unique_filings = []
            for f in sorted(filings, key=lambda x: x["filing_date"], reverse=True):
                # Heuristic: skip if accession contains "/A" (amendment)
                if "/A" in f["accession"]:
                    continue
                quarter_key = (f["filing_date"].year, (f["filing_date"].month - 1) // 3)
                if quarter_key not in seen_quarters:
                    seen_quarters.add(quarter_key)
                    unique_filings.append(f)
                if len(unique_filings) >= quarters:
                    break
            filings = unique_filings

        return filings

    def _fetch_and_parse_filing(self, cik: str, metadata: dict) -> Filing:
        """Fetch and parse a single 13F-HR filing."""
        # Get filing documents page
        accession_clean = metadata["accession"].replace("-", "")
        filing_url = f"{self.base_url}/cgi-bin/viewer?action=view&cik={cik}&accession_number={metadata['accession']}"

        # Alternative: construct direct URL to primary document
        # Most 13F-HRs have primary doc as form13fInfoTable.xml or similar
        doc_url = f"{self.base_url}/Archives/edgar/data/{cik.lstrip('0')}/{accession_clean}/primary_doc.xml"

        # Try to fetch primary document
        try:
            response = self._make_request(doc_url)
            xml_content = response.content
        except:
            # Fallback: try to find information table XML in index
            logger.warning(f"Primary doc not found, using filing page: {filing_url}")
            # For MVP, use simplified approach: look for first XML with "informationTable"
            # (Full implementation would parse the index page)
            raise NotImplementedError("Fallback parsing not yet implemented")

        # Parse XML
        filing = self._parse_13f_xml(cik, metadata["filing_date"], xml_content)
        return filing

    def _parse_13f_xml(self, cik: str, filing_date: date, xml_content: bytes) -> Filing:
        """Parse 13F-HR XML and extract holdings."""
        root = etree.fromstring(xml_content)

        # Extract report period (cover page)
        # This varies by XML schema version
        report_date_elem = root.find(".//reportCalendarOrQuarter")
        if report_date_elem is not None:
            report_date_str = report_date_elem.text.strip()
            report_date = datetime.strptime(report_date_str, "%m-%d-%Y").date()
        else:
            # Fallback: infer from filing date (13F due 45 days after quarter end)
            # Estimate quarter end as ~45 days before filing
            report_date = filing_date  # Simplified for MVP

        # Extract holdings from informationTable
        holdings = []
        info_tables = root.findall(".//infoTable")

        for info_table in info_tables:
            # Extract fields
            name_elem = info_table.find(".//nameOfIssuer")
            cusip_elem = info_table.find(".//cusip")
            value_elem = info_table.find(".//value")
            shares_elem = info_table.find(".//shrsOrPrnAmt/sshPrnamt")
            type_elem = info_table.find(".//shrsOrPrnAmt/sshPrnamtType")

            if None in [name_elem, cusip_elem, value_elem, shares_elem]:
                logger.warning("Incomplete holding entry, skipping")
                continue

            holding = Holding(
                cusip=cusip_elem.text.strip(),
                name=name_elem.text.strip(),
                value=float(value_elem.text.strip()),  # In thousands
                shares=int(shares_elem.text.strip()),
                type=type_elem.text.strip() if type_elem is not None else "SH",
            )
            holdings.append(holding)

        # Compute total value
        total_value = sum(h.value for h in holdings)

        return Filing(
            cik=cik,
            filing_date=filing_date,
            report_date=report_date,
            total_value=total_value,
            holdings_count=len(holdings),
            holdings=holdings,
        )
