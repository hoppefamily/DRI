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

    def _make_request(self, url: str, retry_on_404: bool = True) -> requests.Response:
        """Make HTTP request with rate limiting and retries.

        Args:
            url: URL to fetch
            retry_on_404: If False, don't retry on 404 errors (useful when checking if file exists)
        """
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
            except requests.HTTPError as e:
                # Don't retry on 404 if requested (file doesn't exist)
                if not retry_on_404 and e.response.status_code == 404:
                    raise
                # Don't retry on other 4xx client errors either
                if 400 <= e.response.status_code < 500:
                    raise
                # Retry on 5xx server errors
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.retry_attempts}): {e}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise
            except requests.RequestException as e:
                # Retry on network errors
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
        """Get list of 13F filing metadata from SEC JSON submissions API."""
        # Use SEC data.sec.gov endpoint
        json_url = f"https://data.sec.gov/submissions/CIK{cik}.json"

        response = self._make_request(json_url)
        data = response.json()

        # Extract filings from JSON
        recent_filings = data.get("filings", {}).get("recent", {})

        filings = []
        for i in range(len(recent_filings.get("form", []))):
            form = recent_filings["form"][i]

            # Filter for 13F-HR forms only (skip amendments initially)
            if form != "13F-HR":
                continue

            accession = recent_filings["accessionNumber"][i]
            filing_date_str = recent_filings["filingDate"][i]
            filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d").date()

            report_date_str = recent_filings.get("reportDate", [])[i]
            report_date = None
            if report_date_str:
                report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date()

            primary_doc = recent_filings.get("primaryDocument", [])[i]

            filings.append({
                "accession": accession,
                "filing_date": filing_date,
                "report_date": report_date,
                "primary_document": primary_doc,
            })

        # Filter by date range if specified
        if start_date:
            filings = [f for f in filings if f["filing_date"] >= start_date]
        if end_date:
            filings = [f for f in filings if f["filing_date"] <= end_date]

        # Limit to requested quarters
        if quarters:
            # Sort by filing date descending and take first N
            filings = sorted(filings, key=lambda x: x["filing_date"], reverse=True)[:quarters]

        return filings

    def _fetch_and_parse_filing(self, cik: str, metadata: dict) -> Filing:
        """Fetch and parse a single 13F-HR filing."""
        # Get filing documents using SEC Archives endpoint
        accession_clean = metadata["accession"].replace("-", "")
        base_url = f"{self.base_url}/Archives/edgar/data/{cik.lstrip('0')}/{accession_clean}"

        # First, fetch the index.json to see what files are available
        index_url = f"{base_url}/index.json"
        try:
            response = self._make_request(index_url)
            index_data = response.json()
            available_files = [item["name"] for item in index_data.get("directory", {}).get("item", [])]
        except Exception as e:
            logger.warning(f"Could not fetch index.json, falling back to filename guessing: {e}")
            available_files = []

        # Build priority list of filenames to try
        potential_filenames = []

        # Pattern 1: form13f_<report_date>.xml (Duquesne style)
        if metadata.get("report_date"):
            report_date_str = metadata["report_date"].strftime("%Y%m%d")
            potential_filenames.append(f"form13f_{report_date_str}.xml")

        # Pattern 2: Common filenames (case variations)
        potential_filenames.extend([
            "infotable.xml",           # Lowercase - Pershing Square, Bridgewater
            "informationTable.xml",    # Mixed case
            "form13fInfoTable.xml",
            "13fInfoTable.xml",
        ])

        # Filter to only files that actually exist (if we got the index)
        if available_files:
            xml_files = [f for f in available_files if f.lower().endswith('.xml') and 'primary' not in f.lower()]
            # Match our potential filenames against what's actually there
            matched = [f for f in potential_filenames if f in available_files]
            if matched:
                potential_filenames = matched
            elif xml_files:
                # If no match, use any XML file that's not primary_doc
                potential_filenames = xml_files
                logger.info(f"Using available XML files: {xml_files}")

        # Try each filename (should now be just one if index check worked)
        xml_content = None
        successful_filename = None

        for filename in potential_filenames:
            doc_url = f"{base_url}/{filename}"
            try:
                # Don't retry on 404 when trying multiple filenames
                response = self._make_request(doc_url, retry_on_404=False)
                # Check if it's actually XML (not HTML)
                content = response.content
                if content.strip().startswith(b'<?xml') or b'<informationTable' in content[:1000]:
                    xml_content = content
                    successful_filename = filename
                    logger.info(f"Found holdings data in: {filename}")
                    break
                else:
                    logger.debug(f"Skipping non-XML file: {filename}")
            except Exception:
                # Only log if we're actually trying multiple files (fallback mode)
                if len(potential_filenames) > 1:
                    logger.debug(f"File not found: {filename}")
                continue

        if xml_content is None:
            raise ValueError(
                f"Could not find holdings XML for filing {metadata['accession']}. "
                f"Tried: {', '.join(potential_filenames)}"
            )

        # Parse XML
        filing = self._parse_13f_xml(
            cik=cik,
            filing_date=metadata["filing_date"],
            report_date=metadata.get("report_date"),  # May be None
            xml_content=xml_content
        )
        return filing

    def _parse_13f_xml(self, cik: str, filing_date: date, report_date: Optional[date], xml_content: bytes) -> Filing:
        """Parse 13F-HR XML and extract holdings."""
        root = etree.fromstring(xml_content)

        # Register namespace for XPath queries (13F information table schema)
        nsmap = root.nsmap if root.nsmap else {}
        # Handle default namespace
        if None in nsmap:
            nsmap['n1'] = nsmap.pop(None)

        # Use provided report date if available, otherwise try to extract from XML
        if report_date is None:
            # Extract report period (cover page)
            report_date_elem = root.find(".//reportCalendarOrQuarter")
            if report_date_elem is not None:
                report_date_str = report_date_elem.text.strip()
                report_date = datetime.strptime(report_date_str, "%m-%d-%Y").date()
            else:
                # Fallback: use filing date
                report_date = filing_date

        # Extract holdings from informationTable
        # Use namespace-aware or local-name() based queries
        holdings = []

        # Try with namespace first
        if nsmap:
            ns_prefix = list(nsmap.keys())[0]
            info_tables = root.findall(f".//{{{nsmap[ns_prefix]}}}infoTable")
        else:
            # Fall back to local-name() for namespace-agnostic search
            info_tables = root.xpath(".//*[local-name()='infoTable']")

        for info_table in info_tables:
            # Extract fields (namespace-agnostic using local-name)
            name_elem = info_table.xpath(".//*[local-name()='nameOfIssuer']")
            cusip_elem = info_table.xpath(".//*[local-name()='cusip']")
            value_elem = info_table.xpath(".//*[local-name()='value']")
            shares_elem = info_table.xpath(".//*[local-name()='sshPrnamt']")
            type_elem = info_table.xpath(".//*[local-name()='sshPrnamtType']")

            # xpath returns lists, extract first element
            name_elem = name_elem[0] if name_elem else None
            cusip_elem = cusip_elem[0] if cusip_elem else None
            value_elem = value_elem[0] if value_elem else None
            shares_elem = shares_elem[0] if shares_elem else None
            type_elem = type_elem[0] if type_elem else None

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

        # Data quality validation: Flag suspicious outliers
        # Typical discretionary macro managers: $500M - $50B AUM
        # Flag if total_value > $100B (100,000,000K) as potential unit error
        if total_value > 100_000_000:
            logger.warning(
                f"Suspicious 13F total value detected: ${total_value:,.0f}K (${total_value/1_000:,.1f}M). "
                f"This is likely a unit conversion error in the filing. "
                f"Expected range: $500M - $50B for typical macro managers."
            )

        return Filing(
            cik=cik,
            filing_date=filing_date,
            report_date=report_date,
            total_value=total_value,
            holdings_count=len(holdings),
            holdings=holdings,
        )
