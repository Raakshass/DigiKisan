"""
KisanMitra AI — ICAR-CRIDA Contingency Plan Scraper
==================================================
Scrapes district-level agricultural contingency plans from ICAR-CRIDA
and the Department of Agriculture & Farmers Welfare (DAC) portals.

Data sources (in priority order):
1. DAC Portal: https://agriwelfare.gov.in/en/Agriculture_Contingency_Plan
   - Lists states → districts → PDF download links
   - More structured HTML, easier to parse

2. ICAR-CRIDA: http://www.icar-crida.res.in/Crop_Contingency_Plan.html
   - Original source of all 650+ district plans
   - Uses JS-rendered content, harder to scrape

Content extracted per district:
- District agricultural profile (agro-climatic zones, soil types)
- Contingency strategies for drought, flood, cyclone, heat/cold waves
- Crop-specific advice (varieties, timing, fertilizer adjustments)
- Livestock and fisheries contingency measures

Output:
- One IngestedDocument per district
- Tagged with state, district, category="contingency"
"""
import asyncio
import io
import os
import re
import tempfile
import time
import traceback
from typing import List, Optional, Dict, Tuple
from urllib.parse import urljoin, quote

import httpx
from bs4 import BeautifulSoup

from app.services.data_ingestion.base_source import DataSource, IngestedDocument
from app.core.state_mappings import STATE_CONFIG, get_state_config

# Conditional import — PyMuPDF
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("⚠️ PyMuPDF not installed. Run: pip install PyMuPDF")


class CRIDAScraper(DataSource):
    """
    Scrapes ICAR-CRIDA district contingency plan PDFs.

    Flow:
    1. Fetch state index page → find district PDF links
    2. Download each PDF (with polite delays)
    3. Extract text via PyMuPDF
    4. Clean and structure into markdown
    5. Return as IngestedDocument list
    """

    name = "crida"
    category = "contingency"
    refresh_interval_days = 30  # Monthly re-check
    max_docs_per_state = 20    # Cap at 20 districts per state (key ones)
    request_timeout = 60       # PDFs can be large, give more time
    request_delay = 2.0        # Be respectful to government servers

    # Primary source: DAC/Agriculture Ministry portal
    _DAC_BASE = "https://agriwelfare.gov.in"
    _DAC_CONTINGENCY_URL = "https://agriwelfare.gov.in/en/Agriculture_Contingency_Plan"

    # Fallback: ICAR-CRIDA
    _CRIDA_BASE = "http://www.icar-crida.res.in"
    _CRIDA_CONTINGENCY_URL = "http://www.icar-crida.res.in/Crop_Contingency_Plan.html"

    # Known PDF URL patterns (hand-verified from portal research)
    # Format: base_url/CCP/{state_name}/{district_name}.pdf
    _CRIDA_PDF_PATTERNS = [
        "http://www.icar-crida.res.in/Contingency%20Plan/{state}/{district}.pdf",
        "http://www.icar-crida.res.in/CCP/{state}/{district}.pdf",
    ]

    # HTTP client config
    _HEADERS = {
        "User-Agent": (
            "KisanMitra-Bot/1.0 (Agricultural Research; "
            "contact: kisanmitra.ai@example.com)"
        ),
        "Accept": "text/html,application/pdf,*/*",
    }

    async def fetch_documents(self, state: str) -> List[IngestedDocument]:
        """
        Fetch contingency plan PDFs for all key districts in a state.

        Strategy:
        1. Try to scrape the DAC portal for PDF links
        2. If that fails, try known CRIDA URL patterns
        3. Download and extract text from each PDF
        4. Convert to structured markdown
        """
        if not PYMUPDF_AVAILABLE:
            print(f"   ❌ PyMuPDF not installed — cannot extract PDF text")
            return []

        state_cfg = get_state_config(state)
        if not state_cfg:
            print(f"   ❌ Unknown state code: {state}")
            return []

        state_name = state_cfg["full_name"]
        districts = state_cfg["key_districts"]
        documents = []

        print(f"   📋 Target districts: {len(districts)}")

        # Step 1: Try to discover PDF URLs from DAC portal
        discovered_urls = await self._discover_pdf_urls(state_name)

        # Step 2: For each district, try to get the PDF
        for i, district in enumerate(districts):
            if len(documents) >= self.max_docs_per_state:
                print(f"   ⚠️ Reached max docs limit ({self.max_docs_per_state})")
                break

            try:
                print(f"   [{i+1}/{len(districts)}] Processing: {district}")

                # Try discovered URL first, then known patterns
                pdf_url = self._find_pdf_url(
                    district, state_name, discovered_urls
                )

                if not pdf_url:
                    print(f"      ℹ️ No PDF URL found for {district} — skipping")
                    continue

                # Download PDF
                pdf_bytes = await self._download_pdf(pdf_url)
                if not pdf_bytes:
                    continue

                # Extract text
                text = self._extract_pdf_text(pdf_bytes)
                if not text or len(text) < 200:
                    print(f"      ⚠️ Extracted text too short ({len(text or '')} chars)")
                    continue

                # Convert to structured markdown
                markdown = self._to_markdown(
                    text, state, state_name, district, pdf_url
                )

                doc = IngestedDocument(
                    content=markdown,
                    filename=self.sanitize_filename(
                        f"{district}_contingency"
                    ),
                    state=state,
                    district=district,
                    category=self.category,
                    source=self.name,
                    metadata={
                        "source_url": pdf_url,
                        "pdf_size_bytes": len(pdf_bytes),
                        "text_length": len(text),
                        "state_name": state_name,
                    },
                )
                documents.append(doc)
                print(f"      ✅ Extracted {len(text)} chars → {doc.filename}")

                # Polite delay between requests
                await asyncio.sleep(self.request_delay)

            except Exception as e:
                print(f"      ❌ Error processing {district}: {e}")
                traceback.print_exc()
                continue

        return documents

    # -------------------------------------------------------------------
    # PDF URL Discovery
    # -------------------------------------------------------------------
    async def _discover_pdf_urls(
        self, state_name: str
    ) -> Dict[str, str]:
        """
        Try to scrape the DAC portal for district PDF download links.
        Returns {district_name_lower: pdf_url} dict.
        """
        urls: Dict[str, str] = {}

        try:
            async with httpx.AsyncClient(
                timeout=self.request_timeout,
                follow_redirects=True,
                headers=self._HEADERS,
            ) as client:
                # Fetch the main contingency page
                resp = await client.get(self._DAC_CONTINGENCY_URL)
                if resp.status_code != 200:
                    print(f"   ℹ️ DAC portal returned {resp.status_code}")
                    return urls

                soup = BeautifulSoup(resp.text, "html.parser")

                # Find all PDF links on the page
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    text = link.get_text(strip=True).lower()

                    if href.lower().endswith(".pdf"):
                        # Check if this link relates to our state
                        if state_name.lower() in text or state_name.lower() in href.lower():
                            # Try to extract district name from link text or URL
                            district = self._extract_district_from_link(
                                text, href
                            )
                            if district:
                                full_url = urljoin(self._DAC_BASE, href)
                                urls[district.lower()] = full_url

                # Also look for state-specific sub-pages
                for link in soup.find_all("a", href=True):
                    text = link.get_text(strip=True).lower()
                    if state_name.lower() in text and "click" in text:
                        sub_url = urljoin(self._DAC_BASE, link["href"])
                        sub_urls = await self._scrape_state_subpage(
                            client, sub_url
                        )
                        urls.update(sub_urls)

        except Exception as e:
            print(f"   ℹ️ DAC portal scrape failed: {e}")

        if urls:
            print(f"   📎 Discovered {len(urls)} PDF URLs from DAC portal")

        return urls

    async def _scrape_state_subpage(
        self, client: httpx.AsyncClient, url: str
    ) -> Dict[str, str]:
        """Scrape a state-specific sub-page for district PDF links."""
        urls: Dict[str, str] = {}
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return urls

            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if href.lower().endswith(".pdf"):
                    text = link.get_text(strip=True)
                    district = self._extract_district_from_link(text, href)
                    if district:
                        full_url = urljoin(url, href)
                        urls[district.lower()] = full_url

        except Exception as e:
            print(f"      ℹ️ Sub-page scrape failed: {e}")

        return urls

    def _find_pdf_url(
        self,
        district: str,
        state_name: str,
        discovered_urls: Dict[str, str],
    ) -> Optional[str]:
        """
        Find the PDF URL for a specific district.
        Tries discovered URLs first, then known CRIDA patterns.
        """
        # 1. Check discovered URLs
        district_lower = district.lower()
        if district_lower in discovered_urls:
            return discovered_urls[district_lower]

        # Check partial matches
        for key, url in discovered_urls.items():
            if district_lower in key or key in district_lower:
                return url

        # 2. Try known CRIDA URL patterns
        for pattern in self._CRIDA_PDF_PATTERNS:
            url = pattern.format(
                state=quote(state_name),
                district=quote(district),
            )
            return url  # Return the first pattern — will be validated on download

        return None

    @staticmethod
    def _extract_district_from_link(text: str, href: str) -> Optional[str]:
        """Extract district name from a link's text or URL."""
        # Try from the filename in URL
        filename = href.split("/")[-1].replace(".pdf", "").replace("%20", " ")
        if filename and len(filename) > 2:
            # Clean up common prefixes/suffixes
            name = re.sub(r"(?i)(contingency|plan|district|_|-)", " ", filename)
            name = " ".join(name.split()).strip()
            if name:
                return name.title()

        # Try from link text
        if text and len(text) > 2:
            name = re.sub(r"(?i)(click here|download|pdf|contingency|plan)", " ", text)
            name = " ".join(name.split()).strip()
            if name:
                return name.title()

        return None

    # -------------------------------------------------------------------
    # PDF Download
    # -------------------------------------------------------------------
    async def _download_pdf(self, url: str) -> Optional[bytes]:
        """Download a PDF file. Returns bytes or None."""
        try:
            async with httpx.AsyncClient(
                timeout=self.request_timeout,
                follow_redirects=True,
                headers=self._HEADERS,
            ) as client:
                resp = await client.get(url)

                if resp.status_code == 404:
                    print(f"      ℹ️ PDF not found (404): {url}")
                    return None

                if resp.status_code != 200:
                    print(f"      ⚠️ PDF download HTTP {resp.status_code}: {url}")
                    return None

                content_type = resp.headers.get("content-type", "")
                if "pdf" not in content_type and "octet" not in content_type:
                    # Might be an HTML error page
                    if b"%PDF" not in resp.content[:10]:
                        print(f"      ⚠️ Response is not a PDF ({content_type})")
                        return None

                # Safety: cap at 50 MB
                if len(resp.content) > 50 * 1024 * 1024:
                    print(f"      ⚠️ PDF too large ({len(resp.content)} bytes)")
                    return None

                print(f"      📥 Downloaded {len(resp.content) // 1024} KB")
                return resp.content

        except httpx.TimeoutException:
            print(f"      ⚠️ PDF download timed out: {url}")
            return None
        except Exception as e:
            print(f"      ❌ PDF download error: {e}")
            return None

    # -------------------------------------------------------------------
    # PDF Text Extraction (PyMuPDF)
    # -------------------------------------------------------------------
    def _extract_pdf_text(self, pdf_bytes: bytes) -> Optional[str]:
        """Extract text from PDF using PyMuPDF (fitz)."""
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            pages_text = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                if text and text.strip():
                    pages_text.append(text.strip())

            doc.close()

            if not pages_text:
                return None

            full_text = "\n\n".join(pages_text)

            # Basic cleanup
            full_text = self._clean_extracted_text(full_text)

            return full_text

        except Exception as e:
            print(f"      ❌ PDF extraction error: {e}")
            return None

    @staticmethod
    def _clean_extracted_text(text: str) -> str:
        """Clean raw extracted PDF text."""
        # Remove excessive whitespace
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        # Remove page numbers
        text = re.sub(r"\n\s*\d+\s*\n", "\n", text)
        # Remove common PDF artifacts
        text = re.sub(r"[^\S\n]{3,}", " ", text)
        # Remove form feed characters
        text = text.replace("\x0c", "\n\n")
        return text.strip()

    # -------------------------------------------------------------------
    # Markdown Conversion
    # -------------------------------------------------------------------
    def _to_markdown(
        self,
        raw_text: str,
        state_code: str,
        state_name: str,
        district: str,
        source_url: str,
    ) -> str:
        """
        Convert extracted PDF text into structured markdown
        with metadata header for RAG ingestion.
        """
        # Build header
        header = self.build_document_header(
            title=f"District Contingency Plan — {district}, {state_name}",
            state=state_code,
            district=district,
            source_url=source_url,
        )

        # Extract key sections from the text
        sections = self._extract_sections(raw_text)

        # Build markdown body
        body_parts = []

        if sections.get("profile"):
            body_parts.append(f"## District Agricultural Profile\n\n{sections['profile']}")

        if sections.get("contingency"):
            body_parts.append(f"## Contingency Strategies\n\n{sections['contingency']}")

        if sections.get("drought"):
            body_parts.append(f"### Drought Response\n\n{sections['drought']}")

        if sections.get("flood"):
            body_parts.append(f"### Flood Response\n\n{sections['flood']}")

        if sections.get("livestock"):
            body_parts.append(f"## Livestock Contingency\n\n{sections['livestock']}")

        # If no sections detected, just include the full text
        if not body_parts:
            # Truncate to 15000 chars for RAG (avoid massive docs)
            truncated = raw_text[:15000]
            if len(raw_text) > 15000:
                truncated += f"\n\n[... Truncated. Full document: {len(raw_text)} chars]"
            body_parts.append(truncated)

        body = "\n\n".join(body_parts)

        return f"{header}{body}"

    @staticmethod
    def _extract_sections(text: str) -> Dict[str, str]:
        """
        Try to extract named sections from contingency plan text.
        CRIDA plans follow a standard template with known section headers.
        """
        sections: Dict[str, str] = {}

        # Common section patterns in CRIDA contingency plans
        section_patterns = {
            "profile": [
                r"(?i)(?:district\s+agriculture\s+profile|agro[\s-]*climatic\s+zone)",
                r"(?i)(?:agriculture\s+profile|district\s+profile)",
            ],
            "contingency": [
                r"(?i)(?:contingency\s+(?:strategies|measures|plan))",
                r"(?i)(?:weather\s+based\s+contingency)",
            ],
            "drought": [
                r"(?i)(?:drought|dry\s+spell|delayed\s+(?:onset|monsoon))",
            ],
            "flood": [
                r"(?i)(?:flood|excess\s+rainfall|waterlog)",
            ],
            "livestock": [
                r"(?i)(?:livestock|poultry|fisheries)",
            ],
        }

        for section_name, patterns in section_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    start = match.start()
                    # Extract ~3000 chars after the match
                    end = min(start + 3000, len(text))
                    sections[section_name] = text[start:end].strip()
                    break

        return sections
