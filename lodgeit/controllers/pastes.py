# -*- coding: utf-8 -*-
"""
    lodgeit.controllers.pastes
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    The paste controller

    :copyright: 2007-2008 by Armin Ronacher, Christopher Grebs.
    :license: BSD
"""
from werkzeug import redirect, Response
from werkzeug.exceptions import NotFound

from lodgeit.utils import ctx, render_template
from lodgeit.i18n import list_languages, _
from lodgeit.controllers import BaseController
from lodgeit.database import session, Paste
from lodgeit.lib import antispam
from lodgeit.lib.highlighting import LANGUAGES, STYLES, get_style
from lodgeit.lib.pagination import generate_pagination
from lodgeit.lib.captcha import check_hashed_solution, Captcha


class PasteController(BaseController):
    """Provides all the handler callback for paste related stuff."""

    def new_paste(self):
        """The 'create a new paste' view."""
        code = error = ''
        language = 'text'
        show_captcha = private = False
        parent = None
        getform = ctx.request.form.get

        if ctx.request.method == 'POST':
            code = getform('code')
            language = getform('language')

            parent_id = getform('parent')
            if parent_id is not None:
                parent = Paste.get(parent_id)

            spam = ctx.request.form.get('webpage') or antispam.is_spam(code)
            if spam:
                error = _('your paste contains spam')
                captcha = getform('captcha')
                if captcha:
                    if check_hashed_solution(captcha):
                        error = None
                    else:
                        error += _(' and the CAPTCHA solution was incorrect')
                show_captcha = True
            if code and language and not error:
                paste = Paste(code, language, parent, ctx.request.user_hash,
                              'private' in ctx.request.form)
                session.flush()
                return redirect(paste.url)

        else:
            parent_id = ctx.request.args.get('reply_to')
            if parent_id is not None:
                parent = Paste.get(parent_id)
                if parent is not None:
                    code = parent.code
                    language = parent.language
                    private = parent.private

        return render_template('new_paste.html',
            languages=LANGUAGES,
            parent=parent,
            code=code,
            language=language,
            error=error,
            show_captcha=show_captcha,
            private=private
        )

    def show_paste(self, identifier, raw=False):
        """Show an existing paste."""
        linenos = ctx.request.args.get('linenos') != 'no'
        paste = Paste.get(identifier)
        if paste is None:
            raise NotFound()
        if raw:
            return Response(paste.code, mimetype='text/plain; charset=utf-8')

        style, css = get_style(ctx.request)
        return render_template('show_paste.html',
            paste=paste,
            style=style,
            css=css,
            styles=STYLES,
            linenos=linenos,
        )

    def raw_paste(self, identifier):
        """Show an existing paste in raw mode."""
        return self.show_paste(identifier, raw=True)

    def show_tree(self, identifier):
        """Display the tree of some related pastes."""
        paste = Paste.resolve_root(identifier)
        if paste is None:
            raise NotFound()
        return render_template('paste_tree.html',
            paste=paste,
            current=identifier
        )

    def show_all(self, page=1):
        """Paginated list of pages."""

        def link(page):
            if page == 1:
                return '/all/'
            return '/all/%d' % page

        all = Paste.find_all()
        pastes = all.limit(10).offset(10 * (page -1)).all()
        if not pastes and page != 1:
            raise NotFound()

        return render_template('show_all.html',
            pastes=pastes,
            pagination=generate_pagination(page, 10, all.count(), link),
            css=get_style(ctx.request)[1]
        )

    def compare_paste(self, new_id=None, old_id=None):
        """Render a diff view for two pastes."""
        # redirect for the compare form box
        if old_id is None:
            old_id = ctx.request.form.get('old', '-1').lstrip('#')
            new_id = ctx.request.form.get('new', '-1').lstrip('#')
            return redirect('/compare/%s/%s' % (old_id, new_id))

        old = Paste.get(old_id)
        new = Paste.get(new_id)
        if old is None or new is None:
            raise NotFound()

        return render_template('compare_paste.html',
            old=old,
            new=new,
            diff=old.compare_to(new, template=True)
        )

    def unidiff_paste(self, new_id=None, old_id=None):
        """Render an udiff for the two pastes."""
        old = Paste.get(old_id)
        new = Paste.get(new_id)

        if old is None or new is None:
            raise NotFound()

        return Response(old.compare_to(new), mimetype='text/plain')

    def set_colorscheme(self):
        """Minimal view that updates the style session cookie. Redirects
        back to the page the user is coming from.
        """
        style_name = ctx.request.form.get('style')
        resp = redirect(ctx.request.environ.get('HTTP_REFERER') or '/')
        if style_name in STYLES:
            resp.set_cookie('style', style_name)
        return resp

    def set_language(self, lang='en'):
        """Minimal view that set's a different language. Redirects
        back to the page the user is coming from."""
        resp = redirect(ctx.request.environ.get('HTTP_REFERER') or '/')
        if lang in [x[0] for x in list_languages()]:
            ctx.application.set_locale(lang)
        return resp

    def show_captcha(self):
        """Show a captcha."""
        return Captcha().get_response(set_cookie=True)


controller = PasteController
