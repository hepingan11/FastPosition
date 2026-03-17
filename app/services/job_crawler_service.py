from html import unescape
import json
import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.models.models import CompanyLink, Position
from app.services.llm_service import llm_service

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:
    PlaywrightTimeoutError = Exception
    sync_playwright = None


class JobCrawlerService:
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )
    JOB_KEYWORDS = (
        "职位",
        "岗位",
        "招聘",
        "工作地点",
        "任职要求",
        "岗位职责",
        "校招",
        "社招",
        "实习",
        "工程师",
        "开发",
        "算法",
        "产品",
        "测试",
        "运营",
    )
    PAGINATION_LABELS = ("下一页", "下页", "next", "more", "加载更多", "更多职位")
    PREFERRED_API_PATTERNS = (
        "searchposition",
        "/position/search",
        "/positions/search",
        "/job/search",
        "/jobs/search",
        "/position/list",
        "/jobs/list",
        "/campus/position",
        "/recruit/position",
    )
    REJECT_API_PATTERNS = (
        "dictionary",
        "config",
        "filter",
        "family",
        "positionfamily",
        "postfamily",
        "category",
        "city",
        "workcity",
        "workcities",
        "locationlist",
        "enum",
        "metadata",
        "projectlist",
        "postlist",
    )
    LLM_REVIEW_LIMIT = 5

    def is_rejected_api(self, url: str) -> bool:
        url_lower = (url or "").lower()
        return any(token in url_lower for token in self.REJECT_API_PATTERNS)

    def score_job_api_candidate(self, url: str, data) -> tuple[int, list[dict]]:
        url_lower = (url or "").lower()
        if self.is_rejected_api(url_lower):
            return -100, []
        if not any(token in url_lower for token in ("job", "position", "career", "campus", "recruit")):
            return -50, []

        positions = self.extract_positions_from_json(data, base_url=url)
        if positions and not self.looks_like_real_job_list(positions, base_url=url):
            return -40, []
        score = 0
        if any(pattern in url_lower for pattern in self.PREFERRED_API_PATTERNS):
            score += 50
        if "search" in url_lower:
            score += 20
        if "position" in url_lower or "job" in url_lower:
            score += 10
        score += len(positions) * 5
        if not positions:
            score -= 20
        return score, positions

    def looks_like_real_job_list(self, positions: list[dict], base_url: str = "") -> bool:
        if not positions:
            return False

        sample = positions[: min(len(positions), 10)]
        rich_items = 0
        detail_links = 0
        filled_locations = 0
        filled_descriptions = 0

        for item in sample:
            extras = 0
            if item.get("location"):
                filled_locations += 1
                extras += 1
            if item.get("salary"):
                extras += 1
            if item.get("jd"):
                filled_descriptions += 1
                extras += 1
            link = item.get("link")
            if link and link != base_url:
                detail_links += 1
                extras += 1
            if extras >= 1:
                rich_items += 1

        # 城市/枚举接口通常只有 name，没有地点、详情链接、JD 这些职位特征
        if rich_items == 0:
            return False
        if detail_links == 0 and filled_locations == 0 and filled_descriptions == 0:
            return False
        return True

    def review_api_candidates_with_llm(self, candidates: list[dict]) -> list[dict]:
        if not candidates:
            return candidates

        payload = []
        for index, candidate in enumerate(candidates[: self.LLM_REVIEW_LIMIT], start=1):
            payload.append(
                {
                    "index": index,
                    "url": candidate["url"],
                    "rule_score": candidate["score"],
                    "sample": (
                        json.dumps(candidate["data"], ensure_ascii=False)[:2000]
                        if isinstance(candidate["data"], (dict, list))
                        else str(candidate["data"])[:2000]
                    ),
                }
            )

        prompt = f"""
You are evaluating web API responses to determine which one is the real job listing API.
Return JSON only in this format:
{{
  "best_index": 1,
  "candidates": [
    {{"index": 1, "is_job_api": true, "confidence": 90, "reason": "..." }}
  ]
}}

Judging rules:
1. A real job API should contain repeated job records, not dictionary/config/filter metadata.
2. Job records usually include fields like name/title/postName/positionName and often location/salary/id/url/description.
3. Prefer APIs that look like search/list result APIs over dictionary/enumeration APIs.
4. If none are real job APIs, set best_index to 0.

Candidates:
{json.dumps(payload, ensure_ascii=False)}
"""

        try:
            response = llm_service.chat(prompt)
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start < 0 or json_end <= json_start:
                return candidates
            decision = json.loads(response[json_start:json_end])
        except Exception:
            return candidates

        candidate_reviews = {
            item.get("index"): item
            for item in decision.get("candidates", [])
            if isinstance(item, dict)
        }

        for index, candidate in enumerate(candidates[: self.LLM_REVIEW_LIMIT], start=1):
            review = candidate_reviews.get(index)
            if not review:
                continue
            confidence = int(review.get("confidence", 0) or 0)
            is_job_api = bool(review.get("is_job_api"))
            reason = str(review.get("reason", ""))[:500]
            candidate["llm_reason"] = reason
            candidate["llm_confidence"] = confidence
            candidate["llm_is_job_api"] = is_job_api
            negative_reason_tokens = (
                "分类",
                "筛选",
                "枚举",
                "字典",
                "城市",
                "不是具体职位",
                "非直接展示职位",
                "not direct job",
                "filter",
                "category",
                "dictionary",
            )
            if any(token in reason.lower() for token in negative_reason_tokens):
                candidate["score"] -= max(confidence, 40)
            elif is_job_api:
                candidate["score"] += min(confidence, 30)
            else:
                candidate["score"] -= max(confidence, 20)

        candidates.sort(key=lambda item: item["score"], reverse=True)
        return candidates

    def normalize_job_item(self, item: dict, base_url: str = "") -> dict | None:
        if not isinstance(item, dict):
            return None

        name_keys = (
            "name",
            "title",
            "positionName",
            "jobName",
            "recruitName",
            "postName",
        )
        location_keys = (
            "location",
            "city",
            "workLocation",
            "address",
            "jobCity",
            "locationName",
            "cityName",
        )
        salary_keys = ("salary", "salaryDesc", "salaryRange", "pay", "salaryName")
        link_keys = (
            "link",
            "url",
            "positionUrl",
            "jobUrl",
            "applyUrl",
            "redirectUrl",
            "postUrl",
            "pcUrl",
        )
        jd_keys = (
            "jd",
            "description",
            "jobDescription",
            "requirement",
            "responsibility",
            "summary",
            "positionDetail",
            "postDescription",
        )
        id_keys = ("id", "positionId", "postId", "jobId")

        def pick(keys):
            for key in keys:
                value = item.get(key)
                if value is None:
                    continue
                value = str(value).strip()
                if value:
                    return value
            return ""

        name = pick(name_keys)
        if not name:
            return None

        link = pick(link_keys)
        item_id = pick(id_keys)
        if link:
            link = urljoin(base_url, link)
        elif item_id and "join.qq.com" in base_url:
            link = f"https://join.qq.com/post.html?query={item_id}"
        return {
            "name": name,
            "location": pick(location_keys) or None,
            "salary": pick(salary_keys) or None,
            "link": link or base_url or None,
            "jd": pick(jd_keys) or None,
        }

    def extract_positions_from_json(self, data, base_url: str = "") -> list[dict]:
        positions = []

        def walk(node):
            if len(positions) >= 50:
                return
            if isinstance(node, list):
                normalized_batch = [self.normalize_job_item(item, base_url) for item in node]
                normalized_batch = [item for item in normalized_batch if item]
                if normalized_batch:
                    positions.extend(normalized_batch)
                    return
                for item in node:
                    walk(item)
                return
            if isinstance(node, dict):
                normalized = self.normalize_job_item(node, base_url)
                if normalized:
                    positions.append(normalized)
                    return
                for value in node.values():
                    walk(value)

        walk(data)

        unique = []
        seen = set()
        for item in positions:
            signature = (item["name"], item.get("location"), item.get("link"))
            if signature in seen:
                continue
            seen.add(signature)
            unique.append(item)
            if len(unique) >= 20:
                break
        return unique

    def normalize_text(self, raw_text: str) -> str:
        text = unescape(raw_text or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def html_to_text(self, html: str) -> str:
        clean_text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
        clean_text = re.sub(r"<style[\s\S]*?</style>", " ", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"<[^>]+>", " ", clean_text)
        return self.normalize_text(clean_text)

    def route_resource(self, route) -> None:
        if route.request.resource_type in {"image", "media", "font"}:
            route.abort()
            return
        route.continue_()

    def collect_job_snippets(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        snippets = []
        seen = set()

        candidates = soup.find_all(["li", "div", "section", "article", "tr", "a"])
        for node in candidates:
            text = self.normalize_text(node.get_text(" ", strip=True))
            if len(text) < 20:
                continue
            if not any(keyword in text for keyword in self.JOB_KEYWORDS):
                continue

            link = ""
            anchor = node.find("a", href=True)
            if anchor:
                link = urljoin(base_url, anchor["href"])

            snippet = {
                "text": text[:1000],
                "html": str(node)[:2000],
                "link": link,
            }
            signature = f"{snippet['text'][:200]}::{snippet['link']}"
            if signature in seen:
                continue
            seen.add(signature)
            snippets.append(json.dumps(snippet, ensure_ascii=False))
            if len(snippets) >= 30:
                break

        return snippets

    def add_debug_step(self, debug_steps: list[str], message: str, progress_callback=None) -> None:
        debug_steps.append(message)
        if progress_callback:
            progress_callback(debug_steps)

    def click_pagination(self, page, debug_steps: list[str], progress_callback=None) -> bool:
        for label in self.PAGINATION_LABELS:
            locator = page.get_by_text(label).first
            try:
                locator.wait_for(timeout=1500)
                if locator.is_visible():
                    locator.click(timeout=3000)
                    page.wait_for_load_state("domcontentloaded", timeout=8000)
                    time.sleep(1)
                    self.add_debug_step(debug_steps, f"Triggered pagination: {label}", progress_callback)
                    return True
            except Exception:
                continue
        return False

    def fetch_page_payload(self, url: str, progress_callback=None) -> dict:
        if sync_playwright is None:
            raise RuntimeError("Playwright is not installed")

        debug_steps = [f"Start crawling with Playwright: {url}"]
        if progress_callback:
            progress_callback(debug_steps)
        api_candidates = []

        def handle_response(response):
            content_type = (response.headers or {}).get("content-type", "").lower()
            response_url = response.url
            if "json" not in content_type and not response_url.lower().endswith(".json"):
                return
            try:
                data = response.json()
            except Exception:
                return
            score, positions = self.score_job_api_candidate(response_url, data)
            if score <= 0:
                return
            api_candidates.append(
                {
                    "url": response_url,
                    "data": data,
                    "score": score,
                    "positions": positions,
                }
            )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=self.USER_AGENT,
                locale="zh-CN",
                viewport={"width": 1440, "height": 2200},
            )
            page = context.new_page()
            page.route("**/*", self.route_resource)
            page.on("response", handle_response)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                self.add_debug_step(debug_steps, "Page opened and first render completed", progress_callback)
            except PlaywrightTimeoutError:
                self.add_debug_step(debug_steps, "Page open timed out, continue with loaded content", progress_callback)

            for step in range(4):
                page.mouse.wheel(0, 1800)
                time.sleep(1)
                self.add_debug_step(debug_steps, f"Scroll load step {step + 1}", progress_callback)

            pages_html = [page.content()]
            clicked = self.click_pagination(page, debug_steps, progress_callback)
            if clicked:
                for step in range(3):
                    page.mouse.wheel(0, 1800)
                    time.sleep(1)
                    self.add_debug_step(debug_steps, f"Post-pagination scroll step {step + 1}", progress_callback)
                pages_html.append(page.content())

            time.sleep(2)

            context.close()
            browser.close()

        final_html = "\n".join(pages_html)
        page_text = self.html_to_text(final_html)[:20000]
        snippets = self.collect_job_snippets(final_html, url)
        api_positions = []
        api_preview = ""
        api_url = ""
        api_candidates.sort(key=lambda item: item["score"], reverse=True)
        api_candidates = self.review_api_candidates_with_llm(api_candidates)
        for candidate in api_candidates:
            parsed_positions = candidate["positions"]
            if parsed_positions:
                api_positions = parsed_positions
                api_url = candidate["url"]
                self.add_debug_step(debug_steps, f"API candidate score {candidate['score']}: {api_url}", progress_callback)
                if candidate.get("llm_reason"):
                    self.add_debug_step(
                        debug_steps,
                        f"LLM API review: is_job_api={candidate.get('llm_is_job_api')} "
                        f"confidence={candidate.get('llm_confidence')} reason={candidate.get('llm_reason')}",
                        progress_callback,
                    )
                api_preview = json.dumps(candidate["data"], ensure_ascii=False)[:5000]
                break

        if api_positions:
            self.add_debug_step(debug_steps, f"Captured job API response: {api_url}", progress_callback)
            self.add_debug_step(debug_steps, f"Parsed jobs directly from API: {len(api_positions)}", progress_callback)
        self.add_debug_step(debug_steps, f"Page text normalized, length: {len(page_text)}", progress_callback)
        self.add_debug_step(debug_steps, f"Job snippets collected: {len(snippets)}", progress_callback)
        return {
            "api_positions": api_positions,
            "api_response_preview": api_preview,
            "api_url": api_url,
            "page_text": page_text,
            "snippets": snippets,
            "debug_steps": debug_steps,
        }

    def extract_positions(
        self, company_link: CompanyLink, snippets: list[str], page_text: str
    ) -> tuple[list[dict], str]:
        snippet_text = "\n\n".join(snippets[:20])
        fallback_text = page_text[:4000]
        prompt = f"""
You are a job information extraction assistant. Extract jobs for this company and return a JSON array only.

Company: {company_link.company_name}
Entry URL: {company_link.link}
Recruitment type: {company_link.type or "other"}

Use "job snippets" first. Use "page text summary" only as fallback.

Output fields:
- name
- location
- salary
- link
- jd

Rules:
1. Return JSON array only.
2. At most 20 items.
3. If there are no clear jobs, return [].
4. Every item must have name.
5. If link is missing, use {company_link.link}.

Job snippets:
{snippet_text}

Page text summary:
{fallback_text}
"""

        response = llm_service.chat(prompt)
        json_start = response.find("[")
        json_end = response.rfind("]") + 1
        if json_start < 0 or json_end <= json_start:
            return [], response

        try:
            data = json.loads(response[json_start:json_end])
        except json.JSONDecodeError:
            return [], response

        if not isinstance(data, list):
            return [], response

        positions = []
        for item in data[:20]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            positions.append(
                {
                    "name": name,
                    "location": str(item.get("location", "")).strip() or None,
                    "salary": str(item.get("salary", "")).strip() or None,
                    "link": str(item.get("link", "")).strip() or company_link.link,
                    "jd": str(item.get("jd", "")).strip() or None,
                }
            )
        return positions, response

    def prepare_crawl_result(self, company_link: CompanyLink, progress_callback=None) -> dict:
        payload = self.fetch_page_payload(company_link.link, progress_callback)
        debug_steps = payload["debug_steps"]
        api_positions = payload.get("api_positions", [])
        snippets = payload["snippets"]
        page_text = payload["page_text"]

        llm_raw_response = ""
        if api_positions:
            positions = api_positions
            self.add_debug_step(debug_steps, "Skipped LLM extraction because API data was available", progress_callback)
            llm_raw_response = payload.get("api_response_preview", "")
        else:
            positions, llm_raw_response = self.extract_positions(company_link, snippets, page_text)
            self.add_debug_step(debug_steps, f"LLM extraction completed, jobs found: {len(positions)}", progress_callback)

        if not positions:
            self.add_debug_step(debug_steps, "No valid jobs parsed from snippets", progress_callback)
            return {
                "message": "No job information was parsed from the page",
                "debug_steps": debug_steps,
                "page_text_preview": page_text[:3000],
                "llm_raw_response": llm_raw_response[:5000] if llm_raw_response else "",
                "extracted_positions": [],
            }

        return {
            "message": f"Crawl completed, parsed {len(positions)} jobs",
            "debug_steps": debug_steps,
            "page_text_preview": page_text[:3000],
            "llm_raw_response": llm_raw_response[:5000] if llm_raw_response else "",
            "extracted_positions": positions,
        }

    def upsert_positions(self, db, company_link: CompanyLink, positions: list[dict]) -> tuple[int, int]:
        inserted = 0
        updated = 0

        for item in positions:
            existing = db.query(Position).filter(
                Position.company == company_link.company_name,
                Position.name == item["name"],
                Position.location == item["location"],
            ).first()

            if existing:
                existing.jd = item["jd"] or existing.jd
                existing.salary = item["salary"] or existing.salary
                existing.link = item["link"] or existing.link
                existing.source = company_link.type or existing.source or "company_link_crawl"
                updated += 1
                continue

            db.add(
                Position(
                    name=item["name"],
                    location=item["location"],
                    jd=item["jd"],
                    salary=item["salary"],
                    link=item["link"],
                    company=company_link.company_name,
                    source=company_link.type or "company_link_crawl",
                )
            )
            inserted += 1

        return inserted, updated


job_crawler_service = JobCrawlerService()
