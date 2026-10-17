"""Plain-language report content; original screenshots remain unchanged."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


FINDINGS = [
    {
        'name': 'SQL injection', 'id': 'V01',
        'found': 'We entered a database condition into the sign-in form instead of a normal username. The website treated it as part of its database query and let us enter an administrator account without the correct password. This showed that the login form was trusting user input too much.',
        'fixed': 'We changed the login so that the database treats a username as text rather than an instruction. The password is checked separately, and unexpected input is rejected. We also added a Web Application Firewall to filter suspicious requests. When we repeated the attack, it no longer gave us administrator access.',
        'before_images': [('V01-before-http.png', 'The sign-in request selected the administrator account.'), ('V01-before-admin.png', 'The website opened the administrator workspace.')],
        'after_extra': None,
    },
    {
        'name': 'Stored cross site scripting', 'id': 'V02',
        'found': 'We posted a comment containing browser code and opened the ticket again. The website ran the code as part of the page. The comment changed its own content, showing that a saved message could affect what another user sees.',
        'fixed': 'We changed how comments are displayed so that user content appears as text and cannot become part of the page code. We also added browser security rules and WAF filtering. The repeated request was blocked, and a separate application check showed that the same comment stayed as harmless text.',
        'before_images': [('V02-before-http.png', 'The saved comment was returned as page code.'), ('V02-before-browser.png', 'The browser ran the comment code inside the conversation.')],
        'after_extra': ('v2-xss-encoded.png', 'The application displays the comment as text.'),
    },
    {
        'name': 'Access to other employee tickets', 'id': 'V03',
        'found': 'We signed in as an employee and changed the ticket identifier in a request. The website opened a ticket belonging to someone else and displayed private payroll information. It checked that we were signed in, but did not check whether we were allowed to see that ticket.',
        'fixed': 'We added an ownership check whenever a ticket is opened or a comment is posted. Employees can work with their own tickets, while administrators keep their intended access. When we repeated the request using the same employee account, the private ticket was denied and the employee could still open their own ticket.',
        'before_images': [('V03-before-http.png', 'Changing the requested ticket exposed private employee information.'), ('V03-before-browser.png', 'The signed-in employee could read a ticket owned by someone else.')],
        'after_extra': ('v2-idor-denied.png', 'The hardened website denies access to another employee ticket.'),
    },
    {
        'name': 'Weak authentication and sessions', 'id': 'V04',
        'found': 'We changed the identity value stored in the browser cookie. The website trusted the changed value and gave us administrator access. We also found that the original account passwords were stored in a readable form. A person who could copy those records would not need to guess the passwords.',
        'fixed': 'We replaced the trusted identity cookie with a random session that the server checks. Sessions are replaced at sign-in, expire when no longer valid, and stop working after sign-out. Passwords are now stored as hashes instead of readable text. Changing the old cookie no longer creates an administrator session, and an employee account still cannot open administration.',
        'before_images': [('V04-before-http.png', 'The changed cookie was accepted as an administrator identity.'), ('V04-before-forged.png', 'The administrator page opened after the identity cookie was changed.')],
        'after_extra': None,
    },
    {
        'name': 'Cross site request forgery', 'id': 'V05',
        'found': 'While an employee was signed in, we submitted a contact form from a separate page. It changed the employee email address without using the account form inside the portal. The website accepted the browser session without checking where the change came from.',
        'fixed': 'We added a security token to forms that change account or website data. The server checks that the token belongs to the current session and that the request comes from the portal. We also strengthened cookie handling. Repeating the outside request was rejected, and the account email stayed unchanged.',
        'before_images': [('V05-before-http.png', 'The outside request changed the account email.'), ('V05-before-account.png', 'The account showed the changed email after the request.')],
        'after_extra': None,
    },
    {
        'name': 'Path traversal in file downloads', 'id': 'V06',
        'found': 'We changed the filename in a download request so that it pointed outside the public downloads folder. The website returned an internal configuration file instead of the employee handbook. This showed that the download feature could expose files that were meant to stay private.',
        'fixed': 'We changed the download feature to accept only approved filenames, each linked to a fixed file chosen by the application. Users must also be signed in before downloading. The WAF adds another check for suspicious file requests. The private-file request was denied, while the employee handbook still downloaded normally.',
        'before_images': [('V06-before-http.png', 'The download request reached a private configuration file.'), ('V06-before-browser.png', 'The internal file contents appeared in the browser.')],
        'after_extra': None,
    },
    {
        'name': 'Exposed internal information', 'id': 'V07',
        'found': 'We opened a diagnostic page without signing in. It revealed account details, readable passwords and information about how the application worked. We also found that the website was missing browser security headers and showed more error information than a visitor needed.',
        'fixed': 'We removed the public diagnostic page and replaced detailed public errors with simple messages. We added secure response headers and HTTPS to protect how the browser loads and handles the website. The diagnostic request now returns a missing-page response without exposing account information.',
        'before_images': [('V07-before-http.png', 'The public diagnostic page exposed account information.'), ('V07-before-browser.png', 'Internal account records were visible without signing in.')],
        'after_extra': None,
    },
    {
        'name': 'Repeated requests and resource use', 'id': 'V08',
        'found': 'We repeatedly requested the activity report and watched how the website responded. The original version accepted every request and repeated the report work each time. A visitor could keep asking for the same expensive operation without being slowed down.',
        'fixed': 'We added rate limiting and connection controls at the reverse proxy, along with user-based checks inside the application. Recently generated reports are reused instead of being rebuilt unnecessarily. The hardened website rejected excess requests while still allowing normal use. This showed that the application could control repeated work more effectively.',
        'before_images': [('V08-before-http.png', 'The original website kept accepting repeated report requests.')],
        'after_extra': None,
    },
]


def architecture(path):
    font='/System/Library/Fonts/Supplemental/Arial.ttf'
    large=ImageFont.truetype(font,27); small=ImageFont.truetype(font,23)
    image=Image.new('RGB',(1500,350),'white'); draw=ImageDraw.Draw(image)
    nodes=[('Browser','Employee request'),('Reverse proxy','Traffic control'),('WAF','Request filtering'),('Web application','User and data checks'),('Database','Protected records')]
    for index,(title,detail) in enumerate(nodes):
        left=20+index*300
        draw.rectangle((left,70,left+260,200),fill='#f3f3f3',outline='#333333',width=2)
        draw.text((left+15,100),title,font=large,fill='black')
        draw.text((left+15,154),detail,font=small,fill='black')
        if index<4:
            draw.line((left+260,135,left+294,135),fill='black',width=3)
            draw.polygon([(left+294,135),(left+283,128),(left+283,142)],fill='black')
    draw.text((20,255),'Each layer checks the request before it reaches the next part of the website.',font=large,fill='black')
    image.save(path)


def build_report(Writer, root, figures, captures):
    writer=Writer('Web Application Attack Simulation and Layered Security Hardening',show_header=False)
    writer.p('WAF Rate Limiting and Defensive Controls','Subtitle')
    writer.h('Project overview')
    writer.p('We created a vulnerable web application to understand how common attacks affect a website and the people who use it. We then built a separate hardened version and added security controls to address the problems we found. By repeating the same attacks, we could see how the changes protected information and improved the way the website handled suspicious requests.')
    writer.p('The project follows a simple process: find a weakness, observe what happens, apply a fix and try the same request again. It shows how application changes, a Web Application Firewall and traffic controls work together to improve security.')
    writer.h('Team members')
    writer.table(['Team member','Roll number'],[
        ['Siddharth Kamat','1601-01-242126'],['',''],['',''],['','']],[3.7,3.3])

    writer.page('About the website')
    writer.p('LegacyDesk is an employee service portal. Employees can sign in, raise support tickets, follow conversations, update their contact details and download useful resources. An administrator can access the administration page to view basic portal information.')
    writer.p('The website was designed to look and behave like a normal service portal. Its original version contained weaknesses in login, ticket access, comments, account changes, downloads and request handling. These features gave us practical ways to observe how an application can fail when it trusts requests without enough checking.')
    writer.p('We kept the original website available and created a separate hardened version. This allowed us to compare the same features before and after adding protection.')
    writer.h('Objectives')
    for objective in [
        'Create a vulnerable website that demonstrates common web security problems.',
        'Understand how attacks can expose private information, change account details or cause unnecessary server work.',
        'Fix the weaknesses in the application and add protective layers around it.',
        'Repeat the same attacks and confirm that ordinary employee features still work.',
    ]: writer.p(objective,'List Bullet')

    writer.page('System architecture and defensive layers')
    architecture(figures/'architecture-simple.png')
    writer.image(figures/'architecture-simple.png','Requests pass through the protective layers before reaching application data.',2.3)
    writer.p('The hardened website receives requests through an Nginx reverse proxy. The proxy handles the secure connection and controls repeated traffic. The WAF checks requests for common attack patterns before passing them to the application. The application then checks the user, validates the input and decides whether the requested action is allowed.')
    writer.table(['Layer','What we added'],[
        ['Secure connection','HTTPS protects the connection between the browser and the website.'],
        ['Reverse proxy','Request and connection controls reduce unnecessary traffic reaching the application.'],
        ['Web Application Firewall','Suspicious requests are checked and common attack patterns are blocked.'],
        ['Application','Safer database queries, output encoding, permission checks and stronger sessions protect website features.'],
        ['Request handling','User-based controls and report caching reduce repeated work.'],
        ['Logging','Security events help us understand which requests were accepted or rejected.'],
    ],[1.65,5.35])
    writer.p('The layers support each other. We fixed the application itself and also added controls at the proxy, WAF and browser level.')

    for index,finding in enumerate(FINDINGS):
        if index==0:
            writer.page('What we found')
            writer.h(finding['name'])
        else: writer.page(finding['name'])
        writer.p(finding['found'])
        for filename,caption in finding['before_images']:
            writer.image(captures/filename,caption,4.0 if filename.endswith('-http.png') else 3.15)

    for index,finding in enumerate(FINDINGS):
        if index==0:
            writer.page('How we fixed the vulnerabilities')
            writer.h(finding['name'])
        else: writer.page('Fixing '+finding['name'].lower())
        writer.p(finding['fixed'])
        writer.image(captures/(finding['id']+'-after-http.png'),'The repeated request was handled by the hardened website.',4.7)
        if finding['after_extra']:
            filename,caption=finding['after_extra']
            writer.image(root/'v2/output/playwright'/filename,caption,2.7)

    writer.page('Normal website use after the changes')
    writer.p('After adding the security controls, we checked the features an employee would use every day. Signing in, creating a ticket, adding a normal comment and downloading the handbook continued to work. The website also remained usable on a smaller screen.')
    writer.image(root/'v2/output/playwright/v2-ticket-created.png','An employee creates a support ticket on the hardened website.',3.6)
    writer.image(root/'v2/output/playwright/v2-mobile-ticket.png','The ticket remains usable on a smaller screen.',3.6)
    writer.p('The comparison showed that the same service portal could keep its normal features while rejecting the harmful requests we had demonstrated.')
    writer.save('CFLIA_Final_Report','FINAL_REPORT.md')
