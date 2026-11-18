from odoo import http
from odoo.http import request


class NewsWebsite(http.Controller):
    @http.route(['/tin-tuc', '/tin-tuc/page/<int:page>'], type='http',
                auth='public', website=True, sitemap=True)
    def news(self, page=1, **kwargs):
        Article = request.env['mhp.news.article'].sudo()
        domain = [('is_published', '=', True), ('source_id.active', '=', True)]
        pager = request.website.pager(url='/tin-tuc', total=Article.search_count(domain),
                                      page=max(page, 1), step=24)
        articles = Article.search(domain, limit=24, offset=pager['offset'])
        return request.render('mhp_news.news_page', {'articles': articles, 'pager': pager})
