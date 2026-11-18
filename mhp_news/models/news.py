import hashlib
import logging
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from lxml import html

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


def web_url(value, base=''):
    value = urljoin(base, (value or '').strip())
    parts = urlsplit(value)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username:
        return ''
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ''))


def extract_articles(content, base, xpath, limit):
    tree = html.fromstring(content)
    result, seen = [], set()
    automatic = not xpath
    candidates = tree.xpath(xpath or '//a[@href][.//img or ancestor::h2 or ancestor::h3]')
    if not isinstance(candidates, list):
        raise ValueError('XPath phải trả về danh sách thẻ liên kết.')
    for anchor in candidates:
        if not isinstance(anchor, html.HtmlElement) or anchor.tag != 'a':
            continue
        url = web_url(anchor.get('href'), base)
        if not url or urlsplit(url).hostname != urlsplit(base).hostname or url in seen:
            continue
        images = anchor.xpath('.//img')
        image = images[0] if images else None
        title = anchor.get('title') or (image.get('alt') if image is not None else '')
        title = ' '.join((title or anchor.text_content()).split())
        if len(title) < 12:
            continue
        if automatic:
            parts = urlsplit(url)
            path = parts.path.lower()
            # Exclude menus, author/tag pages and promotional blocks.
            if path.rstrip('/') == urlsplit(base).path.rstrip('/') or any(
                word in path.split('/') for word in (
                    'tag', 'tags', 'tac-gia', 'author', 'login', 'dang-nhap',
                    'lien-he', 'contact', 'quang-cao', 'advertising')):
                continue
            if anchor.xpath('ancestor::nav | ancestor::header | ancestor::footer'):
                continue
            article_path = bool(re.search(r'(?:\.(?:html?|ldo)|/\d{4}/\d{1,2}/|\d{5,})', path))
            heading = bool(anchor.xpath('ancestor::h2 | ancestor::h3 | .//h2 | .//h3'))
            slug = path.rstrip('/').rsplit('/', 1)[-1]
            if not (article_path or heading or (slug.count('-') >= 3 and len(slug) >= 25)):
                continue
        if image is None and automatic:
            # Many sites put the image link and headline link side by side.
            for parent in list(anchor.iterancestors())[:3]:
                matching = parent.xpath('.//a[@href]')
                sibling = next((node for node in matching
                                if web_url(node.get('href'), base) == url and node.xpath('.//img')), None)
                if sibling is not None:
                    image = sibling.xpath('.//img')[0]
                    break
        image_url = ''
        if image is not None:
            image_url = web_url(image.get('data-src') or image.get('data-original') or image.get('src'), base)
        seen.add(url)
        result.append({'name': title[:512], 'url': url, 'image_url': image_url})
        if len(result) >= limit:
            break
    return result


class NewsSource(models.Model):
    _name = 'mhp.news.source'
    _description = 'Nguồn tin tức'
    _order = 'name'

    name = fields.Char('Tên nguồn', required=True)
    active = fields.Boolean(default=True)
    url = fields.Char('URL trang lấy tin', required=True)
    link_xpath = fields.Char('XPath tùy chỉnh',
        help='Để trống để tự nhận diện bài viết. Chỉ nhập khi cần chọn chính xác vùng tin của trang.')
    fetch_limit = fields.Integer('Số bài tối đa mỗi lần', default=40, required=True)
    last_fetch = fields.Datetime('Lần thử gần nhất', readonly=True)
    last_success = fields.Datetime('Lần thành công gần nhất', readonly=True)
    last_error = fields.Text('Lỗi gần nhất', readonly=True)
    last_result = fields.Text('Kết quả gần nhất', readonly=True)

    @api.constrains('url', 'link_xpath', 'fetch_limit')
    def _check_configuration(self):
        from lxml import etree
        for source in self:
            if not web_url(source.url):
                raise ValidationError('URL phải sử dụng HTTP hoặc HTTPS.')
            if not 1 <= source.fetch_limit <= 100:
                raise ValidationError('Số bài mỗi lần phải từ 1 đến 100.')
            try:
                if source.link_xpath:
                    etree.XPath(source.link_xpath)
            except etree.XPathError as exc:
                raise ValidationError('XPath không hợp lệ: %s' % exc) from exc

    def action_fetch(self):
        self.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s)', [18006117])
        if not self.env.cr.fetchone()[0]:
            return {'type': 'ir.actions.client', 'tag': 'reload'}
        for source in self:
            try:
                with self.env.cr.savepoint():
                    source._fetch_news()
            except Exception as exc:
                _logger.exception('Không lấy được tin từ %s', source.url)
                source.write({'last_fetch': fields.Datetime.now(), 'last_error': str(exc)[:2000]})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _fetch_news(self):
        self.ensure_one()
        with requests.Session() as session:
            session.headers['User-Agent'] = 'MHP-News/1.0'
            response = session.get(self.url, timeout=(10, 25), stream=True)
            # Lao Dong sends a small cookie initialization page on first visit.
            # Accept only the known hexadecimal cookie, never execute scripts.
            if urlsplit(response.url).hostname == 'laodong.vn' and int(response.headers.get('Content-Length') or 0) < 2048:
                initial = response.raw.read(2048, decode_content=True)
                match = re.search(rb'document.cookie="D1N=([a-fA-F0-9]{1,128})"', initial)
                response.close()
                if match:
                    session.cookies.set('D1N', match.group(1).decode('ascii'), domain='laodong.vn', path='/')
                response = session.get(self.url, timeout=(10, 25), stream=True)
            with response:
                articles = self._read_response(response)
            if not articles:
                raise ValidationError('Không nhận diện được bài viết. Hãy cấu hình XPath tùy chỉnh hoặc kiểm tra trang có chặn truy cập/tải tin bằng JavaScript không.')
        Article = self.env['mhp.news.article']
        # Reverse page order so the first headline is newest in the local listing.
        for values in reversed(articles):
            key = hashlib.sha256(values['url'].encode()).hexdigest()
            existing = Article.search([('url_key', '=', key)], limit=1)
            if not existing:
                Article.create(dict(values, source_id=self.id, url_key=key))
        self.write({'last_fetch': fields.Datetime.now(),
                    'last_success': fields.Datetime.now(), 'last_error': False,
                    'last_result': 'Đọc được %s bài từ trang nguồn.' % len(articles)})

    def _read_response(self, response):
        return extract_articles(self._response_content(response), response.url, self.link_xpath, self.fetch_limit)

    def _response_content(self, response):
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 5 * 1024 * 1024:
                raise ValidationError('Trang nguồn vượt quá giới hạn 5 MB.')
            chunks.append(chunk)
        return b''.join(chunks)

    @api.model
    def _cron_fetch(self):
        self.search([]).action_fetch()


class NewsArticle(models.Model):
    _name = 'mhp.news.article'
    _description = 'Tin tổng hợp'
    _order = 'id desc'

    name = fields.Char('Tiêu đề', required=True)
    source_id = fields.Many2one('mhp.news.source', required=True, ondelete='cascade', index=True)
    url = fields.Char('Link gốc', required=True)
    url_key = fields.Char(required=True, index=True)
    image_url = fields.Char('URL ảnh')
    publication_date = fields.Date('Ngày đăng (Việt Nam)', index=True, readonly=True)
    is_published = fields.Boolean('Hiển thị công khai', default=True)
    _sql_constraints = [('unique_url', 'unique(url_key)', 'Bài viết đã tồn tại.')]

    @api.constrains('url', 'image_url')
    def _check_urls(self):
        for article in self:
            if not web_url(article.url) or (article.image_url and not web_url(article.image_url)):
                raise ValidationError('Link bài viết và ảnh phải sử dụng HTTP hoặc HTTPS.')
