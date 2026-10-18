"""Four fictional CTF answers. Only the Render V1 image enables this module."""
import html


PASSPHRASES = {
    "ticket": "PAYROLL-BEYOND-THE-DOOR",
    "admin": "CROWN-WITHOUT-A-SEAL",
    "traversal": "ONE-LEVEL-TOO-FAR",
    "debug": "SECRETS-IN-PLAIN-SIGHT",
}
FLAG = "FLAG{legacydesk_four_doors_unlocked}"


def valid_submission(data):
    """Require four distinct answers, in any order; ignore case and edge spaces."""
    answers = [data.get(f"passphrase_{i}", [""]) for i in range(1, 5)]
    if any(len(values) != 1 for values in answers):
        return False
    supplied = {values[0].strip().casefold() for values in answers}
    return supplied == {value.casefold() for value in PASSPHRASES.values()}


def reveal(key):
    return (f'<div class="notice"><strong>Passphrase recovered</strong><br>'
            f'<code>{html.escape(PASSPHRASES[key])}</code><br>'
            '<a class="text-link" href="/challenge">Enter it at the flag vault ↗</a></div>')


def content(data=None):
    message = ""
    if data is not None:
        if valid_submission(data):
            message = (f'<section class="notice" role="status"><h2>Flag unlocked</h2>'
                       f'<p>You recovered all four passphrases.</p>'
                       f'<pre class="challenge-flag">{html.escape(FLAG)}</pre></section>')
        else:
            message = ('<div class="notice danger" role="alert">The vault is still locked. '
                       'Enter all four different passphrases and try again.</div>')
    fields = "".join(
        f'<label>Passphrase {i}<input name="passphrase_{i}" required maxlength="120" '
        f'autocomplete="off" autocapitalize="off" spellcheck="false" '
        f'value="{html.escape((data or {}).get(f"passphrase_{i}", [""])[0], quote=True)}" '
        'placeholder="Enter a recovered passphrase"></label>'
        for i in range(1, 5)
    )
    return f'''<div class="page-heading"><p class="eyebrow">LEGACYDESK / V1 CHALLENGE</p>
        <h1>Four doors. One flag.</h1><p>Explore the portal, recover four hidden passphrases,
        and bring them here to unlock the flag.</p></div>
        <div class="challenge-layout"><section class="panel">{message}
        <h2>Unlock the flag</h2><p class="muted">Use each passphrase once, in any order.
        Capitalization and surrounding spaces do not matter.</p>
        <form method="post" action="/challenge" autocomplete="off">{fields}
        <button class="button full">Unlock flag <span>↗</span></button></form></section>
        <aside class="panel challenge-clues"><p class="eyebrow">FOLLOW THE CLUES</p>
        <h2>The portal holds four secrets.</h2>
        <ol><li>A colleague’s request tells more than it should.</li>
        <li>The administrator’s door trusts a fragile identity.</li>
        <li>A download can wander beyond its shelf.</li>
        <li>A forgotten diagnostic page speaks too freely.</li></ol>
        <p class="muted">Start as <code>alice</code> / <code>alice123</code>.
        Keep the challenge within this fictional V1 portal.</p></aside></div>'''
