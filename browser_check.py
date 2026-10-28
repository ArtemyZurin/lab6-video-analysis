"""Необязательная проверка интерфейса в установленном Edge через Playwright."""
import argparse
from pathlib import Path

from video_lab.common import ROOT, read_json, save_json, sha256
from video_lab.semantics import tokens


def main():
    from playwright.sync_api import sync_playwright
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--url", default="http://127.0.0.1:8006")
    args = parser.parse_args()
    index = read_json(args.results / "index.json")
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until="networkidle")
        actual = page.request.get(args.url + "/api/videos").json()
        assert [v['id'] for v in actual] == [v['id'] for v in index['videos']], "Сервер открыл другой набор"
        page.wait_for_function("n => document.querySelectorAll('.card').length === n", arg=len(actual))
        page.wait_for_function("document.querySelector('#player').readyState >= 1")
        page.locator("#query").fill("человек")
        page.get_by_role("button", name="Найти момент").click()
        page.wait_for_function("document.querySelector('#hitsTitle').textContent.includes('Результаты')")
        hit_count = page.locator(".hit").count()
        assert hit_count > 0
        expected = page.request.get(args.url + "/api/search", params={"q": "человек"}).json()[0]
        page.locator(".hit").first.click()
        page.wait_for_function("t => Math.abs(document.querySelector('#player').currentTime - t) < 2", arg=expected['start'])
        player_time = page.locator("#player").evaluate("el => el.currentTime")
        page.locator("#player").evaluate("el => el.pause()")
        # Выбираем слово из реального транскрипта другого видео, без привязки к старому демо.
        current_title = page.locator('#title').inner_text()
        candidate = next(v for v in index['videos'] if v['title'] != current_title and v['segments'])
        speech_query = next(w for s in candidate['segments'] for w in tokens(s['text'], remove_stop=True) if len(w) >= 5)
        expected_speech = page.request.get(args.url + "/api/search", params={"q": speech_query}).json()[0]
        page.locator("#query").fill(speech_query)
        page.get_by_role("button", name="Найти момент").click()
        page.wait_for_function("q => document.querySelector('.hit')?.textContent.toLowerCase().includes(q)", arg=speech_query)
        page.locator(".hit").first.click()
        page.wait_for_function("e => document.querySelector('#title').textContent === e.title && Math.abs(document.querySelector('#player').currentTime - e.start) < 2", arg=expected_speech)
        speech_time = page.locator("#player").evaluate("el => el.currentTime")
        page.locator("#player").evaluate("el => el.pause()")
        page.screenshot(path=str(args.results / "interface.png"), full_page=True)
        # Переключение ролика из результатов и отдельный клик на временной шкале.
        page.locator(".card").last.click()
        page.wait_for_function("document.querySelector('.card:last-child').classList.contains('active')")
        timeline_events = [e for kind in ('object', 'speech', 'scene', 'audio')
                           for e in index['videos'][-1]['events'] if e['type'] == kind]
        target, event = next((i, e) for i, e in enumerate(timeline_events) if e['start'] > 2)
        page.locator(".event").nth(target).click(force=True)
        page.wait_for_function("t => Math.abs(document.querySelector('#player').currentTime - t) < 2", arg=event['start'])
        page.locator("#query").fill("zzzzzz_no_match")
        page.get_by_role("button", name="Найти момент").click()
        page.wait_for_function("document.querySelector('#hits').textContent.includes('Совпадений нет')")
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert not errors, errors
        browser.close()
    save_json(args.results / "browser_check.json", {"passed": True, "index_sha256": sha256(args.results / 'index.json'), "videos": len(actual), "search_hits": hit_count,
              "time_after_click": player_time, "speech_time_after_click": speech_time, "javascript_errors": errors,
              "speech_query": speech_query,
              "checks": ["video cards", "Russian object search", "seek from result", "speech search and cross-video seek", "timeline click", "empty search", "mobile width"]})
    print("OK: поиск, плеер, временная шкала, мобильная ширина; ошибок JavaScript нет.")


if __name__ == "__main__":
    main()
