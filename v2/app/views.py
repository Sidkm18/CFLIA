import html

def esc(value):
    return html.escape(str(value), quote=True)

class Renderer:
    def page(self, title, content, active="overview", user=None):
            nav = [("overview", "/", "◫", "Overview"), ("tickets", "/tickets", "▤", "Support tickets"),
                   ("knowledge", "/knowledge", "◇", "Knowledge base"), ("account", "/account", "◎", "My account")]
            links = "".join(f'<a class="nav-link {"active" if key == active else ""}" href="{url}"><span>{icon}</span>{label}</a>' for key, url, icon, label in nav)
            identity = f'<span class="avatar">{esc(user["name"][0])}</span><div><strong>{esc(user["name"])}</strong><small>{esc(user["role"].title())}</small></div>' if user else '<span class="avatar">?</span><div><strong>Guest visitor</strong><small>Employee portal</small></div>'
            return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · LegacyDesk</title><link rel="stylesheet" href="/static/style.css"></head><body>
            <aside class="sidebar"><a class="brand" href="/"><span class="brand-icon">L<span>↗</span></span><div>LegacyDesk<small>EMPLOYEE SERVICE PORTAL</small></div></a><div class="nav-label">WORKSPACE</div><nav>{links}</nav><div class="sidebar-bottom"><p class="muted">Need a hand?</p><a class="nav-link" href="/tickets#new"><span>＋</span>Contact the service desk</a></div></aside>
            <div class="workspace"><header><div class="breadcrumb">Workspace <span>/</span> {esc(title)}</div><div class="identity">{identity}{'<form class="logout-form" method="post" action="/logout"><button class="quiet-link">Sign out</button></form>' if user else '<a class="quiet-link" href="/login">Sign in</a>'}</div></header><main>{content}</main><footer>LegacyDesk service portal <span>Employee support &amp; resources</span></footer></div></body></html>'''

    def ticket_table(self, tickets):
            rows = "".join(f'<tr><td><a href="/ticket?id={t["id"]}"><strong>{esc(t["subject"])}</strong><small>#{t["id"]}</small></a></td><td>{esc(t["category"])}</td><td><span class="pill {t["status"].lower()}">{esc(t["status"])}</span></td><td><a aria-label="Open ticket {t["id"]}" class="arrow-link" href="/ticket?id={t["id"]}">↗</a></td></tr>' for t in tickets)
            return '<div class="table-scroll"><table><thead><tr><th>REQUEST</th><th>CATEGORY</th><th>STATUS</th><th></th></tr></thead><tbody>' + (rows or '<tr><td colspan="4" class="empty">No matching tickets.</td></tr>') + '</tbody></table></div>'
