from __future__ import annotations


TAB_ROLE_SELECTOR = '[role="radio"], label.el-radio-button, [role="tab"]'
TAB_CLASS_PATTERN = "radio|tab"
ONE_KEY_TEXT = "一键领链"
PRICE_TEXT = "到手价"
COMMISSION_TEXT = "佣金"
PRICE_PATTERN = r"到手价\s*[￥¥]\s*([0-9]+(?:\.[0-9]+)?)"
COMMISSION_RATE_PATTERN = r"佣金比例\s*([0-9]+(?:\.[0-9]+)?%)"
ESTIMATED_INCOME_PATTERN = r"预估收益\s*[￥¥]\s*([0-9]+(?:\.[0-9]+)?)"
SOLD_OUT_TEXT = "已抢光"
DELISTED_TEXT = "已下架"
NOT_PROMOTABLE_TEXTS = ("暂不支持推广", "不可推广")
DISABLED_CARD_CLASS = "card-disabled"

TAB_SCORE_SCRIPT = """
el => {
  const cls = typeof el.className === 'string' ? el.className : '';
  let score = 0;
  if (el.matches('[role="radio"], label.el-radio-button, [role="tab"]')) score += 30;
  if (/radio|tab/i.test(cls)) score += 20;
  if (getComputedStyle(el).cursor === 'pointer') score += 10;
  return score;
}
"""

BODY_TEXT_SCRIPT = "() => document.body ? (document.body.innerText || '') : ''"

CARD_COLLECTION_SCRIPT = """
() => {
  const compact = value => (value || '').replace(/\s+/g, '').trim();
  const buttons = Array.from(document.querySelectorAll('button,a,span,div'))
    .filter(element => compact(element.innerText || element.textContent) === '一键领链');
  const output = [];
  const seen = new Set();
  for (const button of buttons) {
    let current = button;
    let root = null;
    for (let depth = 0; depth < 16 && current; depth += 1, current = current.parentElement) {
      const rectangle = current.getBoundingClientRect();
      const raw = current.innerText || current.textContent || '';
      const text = compact(raw);
      if (
        rectangle.width >= 160 &&
        rectangle.height >= 100 &&
        text.includes('一键领链') &&
        (text.includes('到手价') || text.includes('佣金'))
      ) {
        root = current;
        break;
      }
    }
    if (!root) continue;
    const links = Array.from(root.querySelectorAll('a[href]')).map(anchor => anchor.href || '');
    const itemUrl = links.find(href => /item\.jd\.com\/(\d+)\.html/.test(href));
    const match = itemUrl && itemUrl.match(/item\.jd\.com\/(\d+)\.html/);
    const sku = match ? match[1] : '';
    if (!sku || seen.has(sku)) continue;
    seen.add(sku);
    const images = Array.from(root.querySelectorAll('img'))
      .map(image => image.currentSrc || image.src || '')
      .filter(Boolean);
    output.push({
      sku,
      itemUrl,
      imageUrl: images[0] || '',
      raw_text: root.innerText || root.textContent || '',
    });
  }
  return output;
}
"""
