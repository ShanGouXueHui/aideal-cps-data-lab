import re
import json
import time
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

OUT = Path("reports/hz11_high_commission_dom_probe_latest.json")
URL = "https://union.jd.com/proManager/realTimeRankings"
PORT = 19229

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def norm(s):
    return re.sub(r"\s+", "", s or "")

def pick_page(browser):
    pages = []
    for ctx in browser.contexts:
        pages.extend(ctx.pages)
    union_pages = [p for p in pages if "union.jd.com" in (p.url or "")]
    if union_pages:
        return union_pages[-1]
    if pages:
        return pages[-1]
    return browser.contexts[0].new_page()

def click_short_text(page, text):
    return page.evaluate(
        """
        (text) => {
          const norm = s => (s || '').replace(/\\s+/g, '').trim();
          const target = norm(text);
          const nodes = Array.from(document.querySelectorAll('button,a,span,div,li'));
          const matched = nodes
            .map((el, idx) => ({el, idx, txt: norm(el.innerText || el.textContent)}))
            .filter(x => (x.txt === target || x.txt.includes(target)) && x.txt.length <= 40)
            .filter(x => {
              const r = x.el.getBoundingClientRect();
              return r.width > 0 && r.height > 0 && r.top >= 0 && r.top < window.innerHeight;
            })
            .sort((a, b) => {
              const ae = a.txt === target ? 0 : 1;
              const be = b.txt === target ? 0 : 1;
              if (ae !== be) return ae - be;
              return a.txt.length - b.txt.length;
            });
          if (!matched.length) return {ok:false, reason:'not_found', text};
          matched[0].el.click();
          return {ok:true, clicked:matched[0].txt, index:matched[0].idx};
        }
        """,
        text,
    )

def hover_grid(page):
    points = [
        (340, 560), (810, 560), (1260, 560),
        (340, 730), (810, 730), (1260, 730),
        (340, 900), (810, 900), (1260, 900),
    ]
    for x, y in points:
        page.mouse.move(x, y)
        page.wait_for_timeout(450)
    return points

def dom_snapshot(page):
    return page.evaluate(
        """
        () => {
          const norm = s => (s || '').replace(/\\s+/g, ' ').trim();
          const short = s => norm(s).slice(0, 700);

          const bodyText = document.body ? document.body.innerText || '' : '';

          const links = Array.from(document.querySelectorAll('a[href]')).map((a, idx) => {
            const r = a.getBoundingClientRect();
            return {
              idx,
              href: a.href || '',
              text: short(a.innerText || a.textContent),
              visible: r.width > 0 && r.height > 0 && r.top >= 0 && r.top < window.innerHeight,
              rect: {x:r.x, y:r.y, w:r.width, h:r.height}
            };
          }).filter(x =>
            x.href.includes('jd.com') ||
            /sku|item|ware|material|union|jdc/i.test(x.href) ||
            /一键领链|我要推广|更多信息/.test(x.text)
          ).slice(0, 120);

          const buttons = Array.from(document.querySelectorAll('button,a,span,div')).map((el, idx) => {
            const r = el.getBoundingClientRect();
            return {
              idx,
              tag: el.tagName,
              cls: String(el.className || '').slice(0, 180),
              text: short(el.innerText || el.textContent),
              visible: r.width > 0 && r.height > 0 && r.top >= 0 && r.top < window.innerHeight,
              rect: {x:r.x, y:r.y, w:r.width, h:r.height}
            };
          }).filter(x =>
            /一键领链|我要推广|更多信息|加入选品库|批量推广/.test(x.text) &&
            x.text.length <= 100
          ).slice(0, 160);

          const imgs = Array.from(document.images).map((img, idx) => {
            const r = img.getBoundingClientRect();
            let parent = img.parentElement;
            let cardText = '';
            let depth = 0;
            while (parent && depth < 7) {
              const t = norm(parent.innerText || parent.textContent);
              if (t && /到手价|佣金|佣金率|券/.test(t) && t.length > cardText.length) {
                cardText = t;
              }
              parent = parent.parentElement;
              depth += 1;
            }
            const a = img.closest('a[href]');
            return {
              idx,
              src: img.currentSrc || img.src || '',
              alt: img.alt || '',
              visible: r.width > 0 && r.height > 0 && r.top >= -200 && r.top < window.innerHeight + 300,
              rect: {x:r.x, y:r.y, w:r.width, h:r.height},
              link: a ? a.href : '',
              card_text: short(cardText)
            };
          }).filter(x => x.visible && (x.card_text || x.link || x.src)).slice(0, 80);

          const divCards = Array.from(document.querySelectorAll('div')).map((el, idx) => {
            const r = el.getBoundingClientRect();
            const t = norm(el.innerText || el.textContent);
            return {
              idx,
              tag: el.tagName,
              cls: String(el.className || '').slice(0, 180),
              text: short(t),
              visible: r.width > 80 && r.height > 60 && r.top >= -100 && r.top < window.innerHeight + 400,
              rect: {x:r.x, y:r.y, w:r.width, h:r.height}
            };
          }).filter(x =>
            x.visible &&
            /到手价/.test(x.text) &&
            /佣金/.test(x.text) &&
            x.text.length >= 30 &&
            x.text.length <= 900
          ).slice(0, 120);

          return {
            url: location.href,
            title: document.title,
            body_len: bodyText.length,
            markers: {
              realtime: bodyText.includes('实时榜单'),
              high_commission: bodyText.includes('高佣榜'),
              one_key_count: (bodyText.match(/一键领链/g) || []).length,
              promote_count: (bodyText.match(/我要推广/g) || []).length,
              more_info_count: (bodyText.match(/更多信息/g) || []).length,
              next_page: bodyText.includes('下一页')
            },
            body_sample: short(bodyText).slice(0, 1200),
            links,
            buttons,
            imgs,
            divCards
          };
        }
        """
    )

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}", timeout=15000)
    page = pick_page(browser)
    page.set_default_timeout(15000)
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(4000)

    tab_click = click_short_text(page, "高佣榜")
    page.wait_for_timeout(2500)

    points = hover_grid(page)
    snap = dom_snapshot(page)

    report = {
        "ts": now(),
        "port": PORT,
        "url": page.url,
        "tab_click": tab_click,
        "hover_points": points,
        "snapshot": snap,
        "diagnosis": {
            "has_card_text": len(snap.get("divCards") or []) > 0,
            "has_visible_buttons": len(snap.get("buttons") or []) > 0,
            "has_links": len(snap.get("links") or []) > 0,
            "one_key_count": snap.get("markers", {}).get("one_key_count"),
            "promote_count": snap.get("markers", {}).get("promote_count"),
        }
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "out": str(OUT),
        "has_card_text": report["diagnosis"]["has_card_text"],
        "has_visible_buttons": report["diagnosis"]["has_visible_buttons"],
        "has_links": report["diagnosis"]["has_links"],
        "one_key_count": report["diagnosis"]["one_key_count"],
        "promote_count": report["diagnosis"]["promote_count"],
        "divCards": len(snap.get("divCards") or []),
        "buttons": len(snap.get("buttons") or []),
        "links": len(snap.get("links") or []),
        "imgs": len(snap.get("imgs") or []),
    }, ensure_ascii=False, indent=2))
